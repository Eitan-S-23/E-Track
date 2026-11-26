package com.wen.gaia.gaia

import android.content.Context
import android.content.Intent
import android.app.Notification
import android.app.NotificationManager
import android.app.Service
import android.app.AlarmManager
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import org.robolectric.shadows.ShadowPowerManager
import org.robolectric.shadows.ShadowSystemClock
import org.json.JSONObject
import java.io.FileDescriptor
import java.io.PrintWriter
import java.io.StringWriter
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
@LooperMode(LooperMode.Mode.PAUSED)
class CompanionServiceTest {
    private lateinit var service: CompanionService
    private lateinit var runtime: Runtime
    private val address = "aa:bb:cc:dd:ee:ff"
    private val revision = "revision-1"
    private val key = DeviceOtaKey("process_1", 1, CompanionBridge.deviceToken(address), "b".repeat(64))

    private class Runtime : CompanionExecution {
        var failure: String? = null
        var engineLive = true
        var gatt = true
        var reply: ((Boolean) -> Unit)? = null
        var probeReply: ((Boolean) -> Unit)? = null
        var starts = 0
        var dispatches = 0
        val payloads = mutableListOf<Map<String, Any>>()
        var autoProbe = false
        val events = mutableListOf<String>()
        override fun problem(context: Context) = failure
        override fun initialize(context: Context) { starts++ }
        override fun dispatch(payload: Map<String, Any>, done: (Boolean) -> Unit) { dispatches++; payloads.add(payload); reply = done }
        override fun probe(id: String, done: (Boolean) -> Unit) { probeReply = done; if (autoProbe) done(true) }
        override fun live() = engineLive
        override fun connected(context: Context) = gatt
        override fun lost(id: String) { events.add(id) }
    }

    @Before fun setUp() {
        // ServiceController.create() drains posted work even on a paused looper.
        // Attach first, prepare dependencies, then exercise the real callbacks.
        shadowOf(Looper.getMainLooper()).pause()
        service = Robolectric.buildService(CompanionService::class.java).get()
        runtime = Runtime(); service.execution = runtime
        CompanionBridge.preferences(service).edit().clear().putBoolean("enabled", true)
            .putString("revision", revision).putString("address", address).commit()
        Settings.Global.putInt(service.contentResolver, Settings.Global.BOOT_COUNT, 7)
        service.getSharedPreferences("companion_diagnostics_v1", Context.MODE_PRIVATE).edit().clear().commit()
        service.onCreate()
    }
    @After fun tearDown() { service.onDestroy() }
    private fun start() { service.onStartCommand(Intent().putExtra("reason", "foreground"), 0, 1) }
    private fun state(status: String = "CONNECTED", connected: Boolean = true, busy: Boolean = false) =
        mapOf("runtimeId" to service.runtimeId, "revision" to revision,
            "deviceToken" to CompanionBridge.deviceToken(address), "status" to status,
            "connected" to connected, "busy" to busy)

    private fun enterBackoff(status: String = "DEVICE_OFFLINE"): Pair<Long, Long> {
        runtime.gatt = false
        runtime.autoProbe = true
        start(); runtime.reply!!(true)
        for (seconds in listOf(2L, 4L, 8L)) {
            assertTrue(service.state(state(status, false)))
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(seconds))
            runtime.reply!!(true)
        }
        val before = SystemClock.elapsedRealtime() to System.currentTimeMillis()
        assertTrue(service.state(state(status, false)))
        assertTrue(service.waitingForRecovery())
        return before
    }

    private fun assertWakeDeadline(before: Pair<Long, Long>, next: Long) {
        val after = SystemClock.elapsedRealtime() to System.currentTimeMillis()
        val scheduled = shadowOf(service.getSystemService(AlarmManager::class.java)).scheduledAlarms.single().triggerAtMs
        // Bracket time spent in real preferences/OS calls, rather than assuming they take zero milliseconds.
        assertTrue(scheduled >= before.first + (next - after.second))
        assertTrue(scheduled <= after.first + (next - before.second))
        assertEquals(scheduled, CompanionBridge.preferences(service).getLong("recoveryWakeElapsed", 0))
    }

    @Test fun enabledServiceRequestsStickySystemRecreationWithoutOpeningUi() {
        assertEquals(Service.START_STICKY,
            service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 1))
        assertEquals(1, runtime.starts)
        assertEquals(1, runtime.dispatches)
        assertNull(shadowOf(service.applicationContext as android.app.Application).nextStartedActivity)
    }

    @Test fun pendingCheckDuringInitialDispatchIsQueuedWithoutReinitializingOrResettingRecovery() {
        start()
        CompanionBridge.preferences(service).edit().putBoolean("checkPending", true).commit()
        service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 2)
        assertEquals(1, runtime.starts)
        assertEquals(1, runtime.dispatches)
        runtime.reply!!(true)
        assertEquals(2, runtime.dispatches)
        assertEquals(true, runtime.payloads.last()["checkPending"])
        assertEquals("periodic", runtime.payloads.last()["reason"])
        assertEquals(1, runtime.starts)
    }

    @Test fun heartbeatClaimsAnElapsedCheckAfterSleepWithoutItsAlarmOrAJob() {
        runtime.autoProbe = true
        start(); runtime.reply!!(true)
        assertTrue(service.state(state()))
        assertTrue(CompanionCheckWake.schedule(service, System.currentTimeMillis() + 60000))
        val uptime = SystemClock.uptimeMillis()
        val elapsed = SystemClock.elapsedRealtime()
        ShadowSystemClock.simulateDeepSleep(Duration.ofMinutes(2))
        assertEquals(uptime, SystemClock.uptimeMillis())
        assertEquals(elapsed + 120000L, SystemClock.elapsedRealtime())
        // Robolectric 4.14.1 idleFor discards deep sleep by resetting elapsed to uptime.
        // Advance both clocks without losing sleep, then deliver the real due Handler work.
        SystemClock.sleep(31000)
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(uptime + 31000L, SystemClock.uptimeMillis())
        assertEquals(elapsed + 151000L, SystemClock.elapsedRealtime())
        assertEquals(2, runtime.dispatches)
        assertEquals(true, runtime.payloads.last()["checkPending"])
        assertEquals("periodic", runtime.payloads.last()["reason"])
        assertEquals(1, runtime.starts)
        assertEquals(false, CompanionCheckWake.snapshot(service)["pending"])
    }
    @Test fun rejectedStartDoesNotRequestStickyRecreation() {
        runtime.failure = "BLUETOOTH_OFF"
        assertEquals(Service.START_NOT_STICKY, service.onStartCommand(null, 0, 1))
        assertEquals(0, runtime.starts)
        assertFalse(service.waitingForRecovery())
    }
    @Test fun stickyRecreationRetainsCooldownWithoutStartingTheEngineOrTakingAWakeLock() {
        val prefs = CompanionBridge.preferences(service)
        val next = System.currentTimeMillis() + 60000
        prefs.edit().putLong("nextAttempt", next).commit()
        assertEquals(Service.START_STICKY, service.onStartCommand(null, 0, 1))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(21))
        assertTrue(service.waitingForRecovery())
        assertFalse(service.healthy())
        assertFalse(service.linkReady())
        assertEquals(0, runtime.starts)
        assertEquals(0, runtime.dispatches)
        service.dispatch()
        assertEquals(0, runtime.dispatches)
        assertFalse(ShadowPowerManager.getLatestWakeLock()?.isHeld == true)
        val output = StringWriter()
        service.dump(FileDescriptor(), PrintWriter(output), emptyArray())
        val snapshot = JSONObject(output.toString())
        assertFalse(snapshot.getBoolean("closed"))
        assertTrue(snapshot.getBoolean("recoveryWaiting"))
        assertEquals(next, snapshot.getLong("nextRecoveryAt"))
        assertFalse(snapshot.getBoolean("runtimeAcknowledged"))
        assertFalse(output.toString().contains(address))
    }
    @Test fun stickyRecreationStartsAtCooldownExpiryWithoutAnotherIntentOrSystemJob() {
        val prefs = CompanionBridge.preferences(service)
        prefs.edit().putLong("nextAttempt", System.currentTimeMillis() + 60000).commit()
        service.onStartCommand(null, 0, 1)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(59))
        assertEquals(0, runtime.dispatches)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(1, runtime.starts)
        assertEquals(1, runtime.dispatches)
        runtime.reply!!(true)
        assertTrue(service.state(state()))
        assertTrue(service.linkReady())
        assertEquals(0L, prefs.getLong("nextAttempt", 0))
    }
    @Test fun creationOnlyBootstrapAlsoHonorsPersistedCooldown() {
        CompanionBridge.preferences(service).edit().putLong("nextAttempt", System.currentTimeMillis() + 60000).commit()
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(service.waitingForRecovery())
        assertEquals(0, runtime.starts)
        assertEquals(0, runtime.dispatches)
    }
    @Test fun radioPermissionLossWhileColdWaitingStopsWithoutStartingTheEngine() {
        CompanionBridge.preferences(service).edit().putLong("nextAttempt", System.currentTimeMillis() + 3600000).commit()
        service.onStartCommand(null, 0, 1)
        runtime.failure = "BLUETOOTH_PERMISSION_DENIED"
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(31))
        assertFalse(service.waitingForRecovery())
        assertEquals(0, runtime.starts)
        assertEquals(0, runtime.dispatches)
        assertEquals(1, runtime.events.size)
    }

    @Test fun recreatedServiceStartsWithoutAnotherIntentOrPeriodicJob() {
        assertEquals(0, runtime.starts)
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(1, runtime.starts)
        assertEquals(1, runtime.dispatches)
        assertEquals("\u6b63\u5728\u542f\u52a8\u8bbe\u5907\u8fde\u63a5",
            shadowOf(service).lastForegroundNotification.extras.getString(Notification.EXTRA_TEXT))
        assertFalse(service.healthy())
        assertFalse(service.ownsDevice(key, service.runtimeId))
        runtime.reply!!(true)
        assertTrue(service.healthy())
        assertFalse(service.ownsDevice(key, service.runtimeId))
        assertTrue(service.state(state()))
        assertTrue(service.ownsDevice(key, service.runtimeId))
    }
    @Test fun explicitStartConsumesTheCreationBootstrapWithoutDoubleDispatch() {
        start()
        runtime.reply!!(true)
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(1, runtime.starts)
        assertEquals(1, runtime.dispatches)
    }
    @Test fun creationBootstrapHonorsDisableAndPermissionGuards() {
        runtime.failure = "BLUETOOTH_PERMISSION_DENIED"
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(0, runtime.starts)
        assertEquals(0, runtime.dispatches)
        assertFalse(service.healthy())
    }
    @Test fun disabledRecreatedServiceCannotInitializeTheEngine() {
        CompanionBridge.preferences(service).edit().putBoolean("enabled", false).commit()
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(0, runtime.starts)
        assertFalse(service.healthy())
    }
    @Test fun destructionBeforeBootstrapCannotResurrectTheService() {
        service.onDestroy()
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals(0, runtime.starts)
        assertEquals(0, runtime.dispatches)
    }
    @Test fun creationBootstrapRetainsTheExistingRuntimeDeadline() {
        shadowOf(Looper.getMainLooper()).idle()
        val late = runtime.reply!!
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(21))
        assertFalse(service.healthy())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        late(true)
        assertFalse(service.healthy())
        assertEquals(1, runtime.starts)
    }
    @Test fun serviceDumpDistinguishesLifecycleFromTheRealLinkWithoutPrivateIdentifiers() {
        val output = StringWriter()
        service.dump(FileDescriptor(), PrintWriter(output), emptyArray())
        val snapshot = JSONObject(output.toString())
        assertFalse(snapshot.getBoolean("foregroundStarted"))
        assertFalse(snapshot.getBoolean("runtimeAcknowledged"))
        assertFalse(snapshot.getBoolean("linkAcknowledged"))
        assertEquals("INITIALIZING", snapshot.getString("status"))
        assertTrue(snapshot.has("diagnostics"))
        assertFalse(output.toString().contains(address))
        assertFalse(output.toString().contains(key.deviceToken))
        assertEquals(0, runtime.starts)
    }

    @Test fun notificationAndStartAreNotRuntimeOwnership() {
        start()
        assertNotNull(shadowOf(service).lastForegroundNotification)
        assertFalse(service.healthy())
        assertFalse(service.ownsDevice(key, service.runtimeId))
        runtime.reply!!(true)
        assertTrue(service.healthy())
        assertFalse(service.ownsDevice(key, service.runtimeId))
        assertTrue(service.state(state()))
        assertTrue(service.ownsDevice(key, service.runtimeId))
        assertFalse(service.ownsDevice(key, "old-runtime"))
        assertFalse(service.ownsDevice(key.copy(deviceToken = "0".repeat(64)), service.runtimeId))
    }
    @Test fun startupTimeoutReleasesEverythingAndFencesLateReply() {
        start(); val late = runtime.reply!!
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(21))
        assertFalse(service.healthy())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        late(true); assertFalse(service.healthy())
        assertEquals(1, runtime.events.size)
    }
    @Test fun permissionLossAndStaleStateCannotKeepOwnerAlive() {
        start(); runtime.reply!!(true)
        assertFalse(service.state(state() + ("revision" to "old")))
        runtime.failure = "BLUETOOTH_PERMISSION_DENIED"
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(31))
        assertFalse(service.healthy())
        assertFalse(service.state(state()))
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun missingProbeStopsService() {
        start(); runtime.reply!!(true)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(36))
        assertFalse(service.healthy())
        runtime.probeReply!!(true); assertFalse(service.healthy())
    }
    @Test fun connectionAndRevisionAreCheckedAgainAtOtaAdmission() {
        start(); runtime.reply!!(true); service.state(state())
        runtime.gatt = false; assertFalse(service.ownsDevice(key, service.runtimeId))
        assertFalse(service.state(state()))
        runtime.gatt = true
        CompanionBridge.preferences(service).edit().putString("revision", "replacement").commit()
        assertFalse(service.healthy()); assertFalse(service.ownsDevice(key, service.runtimeId))
    }
    @Test fun offlineResultRetriesAtTwoFourEightSecondsBeforeBackingOffOnce() {
        start(); runtime.reply!!(true)
        service.state(state("CONNECTING", false, true))
        val prefs = CompanionBridge.preferences(service)
        for ((index, delay) in listOf(2L, 4L, 8L).withIndex()) {
            assertTrue(service.state(state("DEVICE_OFFLINE", false)))
            assertTrue(service.healthy())
            assertEquals(0, prefs.getInt("failures", 0))
            assertTrue(ShadowPowerManager.getLatestWakeLock().isHeld)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(delay * 1000 - 1))
            assertEquals(index + 1, runtime.dispatches)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1))
            assertEquals(index + 2, runtime.dispatches)
            runtime.reply!!(true)
        }
        assertTrue(service.state(state("DEVICE_OFFLINE", false)))
        assertTrue(service.healthy())
        assertTrue(service.waitingForRecovery())
        assertFalse(service.linkReady())
        assertEquals(1, prefs.getInt("failures", 0))
        assertTrue(prefs.getLong("nextAttempt", 0) > System.currentTimeMillis())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        assertEquals(1, runtime.starts)
        assertTrue(runtime.events.isEmpty())
    }

    @Test fun cooldownResumesTheSameOwnerWithoutWaitingForThePeriodicJob() {
        enterBackoff()
        val original = service.runtimeId
        assertEquals(4, runtime.dispatches)
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(119))
        assertEquals(4, runtime.dispatches)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(5, runtime.dispatches)
        assertEquals(original, service.runtimeId)
        assertTrue(runtime.events.isEmpty())
        assertTrue(ShadowPowerManager.getLatestWakeLock().isHeld)
        runtime.reply!!(true)
        runtime.gatt = true
        assertTrue(service.state(state()))
        assertTrue(service.linkReady())
        assertFalse(service.waitingForRecovery())
        assertEquals(0, CompanionBridge.preferences(service).getInt("failures", 0))
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun timeoutAlsoKeepsARecoveryOwnerThroughCooldown() {
        enterBackoff("CONNECTION_TIMEOUT")
        assertTrue(service.healthy())
        assertTrue(runtime.events.isEmpty())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun cooldownIsStillCappedAtSixtyMinutes() {
        val prefs = CompanionBridge.preferences(service)
        prefs.edit().putInt("failures", 5).commit()
        enterBackoff()
        val remaining = prefs.getLong("nextAttempt", 0) - System.currentTimeMillis()
        assertTrue(remaining > 59 * 60000L)
        assertTrue(remaining <= 60 * 60000L)
        assertEquals(6, prefs.getInt("failures", 0))
    }
    @Test fun cooldownRegistersOneInexactIdleWakeWithoutHoldingTheCpu() {
        val before = enterBackoff()
        val manager = shadowOf(service.getSystemService(AlarmManager::class.java))
        val alarm = manager.scheduledAlarms.single()
        assertEquals(AlarmManager.ELAPSED_REALTIME_WAKEUP, alarm.type)
        assertTrue(alarm.allowWhileIdle)
        assertNotEquals(0L, alarm.windowLengthMs)
        val next = CompanionBridge.preferences(service).getLong("nextAttempt", 0)
        assertTrue(next >= before.second + 120000L)
        assertTrue(next <= System.currentTimeMillis() + 120000L)
        assertWakeDeadline(before, next)
        val intent = shadowOf(alarm.operation!!).savedIntent
        assertEquals(CompanionRecoveryReceiver::class.java.name, intent.component!!.className)
        assertEquals(CompanionRecoveryWake.ACTION, intent.action)
        assertFalse(intent.toString().contains(address))
        service.onStartCommand(Intent().putExtra("reason", "periodic"), 0, 2)
        assertEquals(alarm.operation, manager.scheduledAlarms.single().operation)
        assertEquals(alarm.triggerAtMs, manager.scheduledAlarms.single().triggerAtMs)
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun elapsedSleepExpiresCooldownWithoutRunningTheUptimeTimer() {
        enterBackoff()
        val uptime = SystemClock.uptimeMillis()
        ShadowSystemClock.simulateDeepSleep(Duration.ofMinutes(61))
        assertEquals(uptime, SystemClock.uptimeMillis())
        assertEquals(4, runtime.dispatches)
        assertEquals(0L, CompanionRecoveryWake.remainingMs(service))
        service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 2)
        assertEquals(5, runtime.dispatches)
        assertFalse(service.waitingForRecovery())
        assertTrue(shadowOf(service.getSystemService(AlarmManager::class.java)).scheduledAlarms.isEmpty())
        service.onStartCommand(Intent().putExtra("reason", "presence"), 0, 3)
        service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 4)
        assertEquals(5, runtime.dispatches)
    }
    @Test fun explicitColdRecoveryAlsoHonorsThePersistedDeadline() {
        val before = SystemClock.elapsedRealtime() to System.currentTimeMillis()
        val next = System.currentTimeMillis() + 60000
        CompanionBridge.preferences(service).edit().putLong("nextAttempt", next).commit()
        service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 1)
        assertEquals(0, runtime.starts)
        assertTrue(service.waitingForRecovery())
        assertWakeDeadline(before, next)
        assertEquals(1, shadowOf(service.getSystemService(AlarmManager::class.java)).scheduledAlarms.size)
    }
    @Test fun destructionPreservesAnEnabledCooldownButDisableCancelsIt() {
        enterBackoff()
        val manager = shadowOf(service.getSystemService(AlarmManager::class.java))
        val alarm = manager.scheduledAlarms.single()
        service.onDestroy()
        assertNull(CompanionService.active)
        assertEquals(alarm.operation, manager.scheduledAlarms.single().operation)
        assertEquals(true, CompanionRecoveryWake.snapshot(service)["pending"])
        CompanionBridge.preferences(service).edit().putBoolean("enabled", false).commit()
        CompanionRecoveryWake.restore(service)
        assertTrue(manager.scheduledAlarms.isEmpty())
        assertEquals(false, CompanionRecoveryWake.snapshot(service)["pending"])
    }
    @Test fun successfulPresenceRecoveryCancelsTheSystemWakeAsWellAsTheHandler() {
        enterBackoff()
        service.onStartCommand(Intent().putExtra("reason", "presence"), 0, 2)
        runtime.reply!!(true)
        runtime.gatt = true
        assertTrue(service.state(state()))
        assertTrue(shadowOf(service.getSystemService(AlarmManager::class.java)).scheduledAlarms.isEmpty())
        assertEquals(false, CompanionRecoveryWake.snapshot(service)["pending"])
        assertEquals(0L, CompanionRecoveryWake.remainingMs(service))
    }
    @Test fun simultaneousBackgroundStartsDoNotInitializeOrDispatchTwice() {
        start()
        service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 2)
        service.onStartCommand(Intent().putExtra("reason", "presence"), 0, 3)
        assertEquals(1, runtime.starts)
        assertEquals(1, runtime.dispatches)
        runtime.reply!!(true)
        service.onStartCommand(Intent().putExtra("reason", "recovery"), 0, 4)
        assertEquals(1, runtime.dispatches)
    }
    @Test fun lateFailureAndProgressCannotStackOrExtendCooldown() {
        enterBackoff()
        val prefs = CompanionBridge.preferences(service)
        val next = prefs.getLong("nextAttempt", 0)
        assertFalse(service.state(state("DEVICE_OFFLINE", false)))
        assertFalse(service.state(state("CONNECTING", false, true) +
            mapOf("recoveryBusy" to true, "recoveryId" to "a".repeat(32))))
        assertEquals(next, prefs.getLong("nextAttempt", 0))
        assertEquals(1, prefs.getInt("failures", 0))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(31))
        assertTrue(service.waitingForRecovery())
        assertEquals(4, runtime.dispatches)
    }
    @Test fun presenceDuringCooldownCanRecoverAndCancelsTheOldTimer() {
        enterBackoff()
        service.onStartCommand(Intent().putExtra("reason", "presence"), 0, 2)
        assertEquals(5, runtime.dispatches)
        runtime.reply!!(true)
        runtime.gatt = true
        assertTrue(service.state(state()))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(121))
        assertEquals(5, runtime.dispatches)
        assertTrue(service.linkReady())
    }
    @Test fun periodicWakeDuringCooldownCannotStartAnEarlyRecovery() {
        enterBackoff()
        val prefs = CompanionBridge.preferences(service)
        val next = prefs.getLong("nextAttempt", 0)
        service.onStartCommand(Intent().putExtra("reason", "periodic"), 0, 2)
        assertTrue(service.waitingForRecovery())
        assertEquals(next, prefs.getLong("nextAttempt", 0))
        assertEquals(4, runtime.dispatches)
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun disablingDuringCooldownCancelsRecoveryAndDoesNotResurrect() {
        enterBackoff()
        CompanionBridge.preferences(service).edit().putBoolean("enabled", false).commit()
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(121))
        assertFalse(service.waitingForRecovery())
        assertFalse(service.healthy())
        assertEquals(4, runtime.dispatches)
        assertEquals(1, runtime.events.size)
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun changedAssociationWhileWaitingCannotDispatchToTheOldDevice() {
        enterBackoff()
        CompanionBridge.preferences(service).edit().putString("revision", "replacement").commit()
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(121))
        assertFalse(service.waitingForRecovery())
        assertEquals(4, runtime.dispatches)
        assertEquals(1, runtime.events.size)
    }
    @Test fun cooldownNotificationDoesNotClaimAnEstablishedConnection() {
        enterBackoff()
        val notification = shadowOf(service.getSystemService(NotificationManager::class.java))
            .getNotification(CompanionService.NOTIFICATION_ID)
        assertEquals("\u8bbe\u5907\u672a\u8fde\u63a5\uff0c\u7b49\u5f85\u4e0b\u6b21\u91cd\u8bd5",
            notification.extras.getString(Notification.EXTRA_TEXT))
        assertFalse(service.ownsDevice(key, service.runtimeId))
        assertFalse(service.recoveryHealthy())
    }

    @Test fun verifiedOtaWithRetiredGattRecoversWithoutStoppingOrFailureBackoff() {
        start(); runtime.reply!!(true); service.state(state())
        runtime.gatt = false
        assertTrue(service.state(state("TARGET_IDENTITY_VERIFIED", false, true)))
        val prefs = CompanionBridge.preferences(service)
        assertTrue(service.healthy())
        assertFalse(service.linkReady())
        assertEquals(0, prefs.getInt("failures", 0))
        assertEquals(0L, prefs.getLong("nextAttempt", 0))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(2, runtime.dispatches)
        runtime.reply!!(true)
        runtime.gatt = true
        assertTrue(service.state(state()))
        assertTrue(service.linkReady())
        assertTrue(runtime.events.isEmpty())
        assertEquals(0L, prefs.getLong("nextAttempt", 0))
    }
    @Test fun duplicateFailureDoesNotStackRetriesAndSuccessCancelsTheTimer() {
        start(); runtime.reply!!(true)
        repeat(3) { service.state(state("DEVICE_OFFLINE", false)) }
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(2, runtime.dispatches); runtime.reply!!(true)
        service.state(state("DEVICE_IDENTITY_UNAVAILABLE", false))
        service.state(state())
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(10))
        assertEquals(2, runtime.dispatches)
        assertTrue(service.ownsDevice(key, service.runtimeId))
        assertEquals(0L, CompanionBridge.preferences(service).getLong("nextAttempt", 0))
    }
    @Test fun identityFailureRetriesWithoutReplacingTheAcknowledgedRuntime() {
        start(); runtime.reply!!(true)
        val id = service.runtimeId
        service.state(state("DEVICE_IDENTITY_UNAVAILABLE", false))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(2, runtime.dispatches); runtime.reply!!(true)
        service.state(state())
        assertEquals(id, service.runtimeId)
        assertTrue(runtime.events.isEmpty())
        assertEquals(1, runtime.starts)
    }
    @Test fun successfulConnectionResetsTheNextRecoveryWindow() {
        start(); runtime.reply!!(true)
        service.state(state("DEVICE_OFFLINE", false))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        runtime.reply!!(true); service.state(state())
        service.state(state("CONNECTING", false, true))
        service.state(state("DEVICE_OFFLINE", false))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(3, runtime.dispatches)
    }
    @Test fun laterDisconnectReacquiresABoundedLockAndSuccessReleasesIt() {
        start(); runtime.reply!!(true); service.state(state())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        service.state(state("CONNECTING", false, true))
        assertTrue(ShadowPowerManager.getLatestWakeLock().isHeld)
        service.state(state("DEVICE_OFFLINE", false))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(2, runtime.dispatches); runtime.reply!!(true)
        service.state(state())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun quickRecoveryWindowDoesNotGrowAfterSlowConnectionAttempts() {
        start(); runtime.reply!!(true); runtime.autoProbe = true
        service.state(state("CONNECTING", false, true))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(59))
        service.state(state("DEVICE_OFFLINE", false))
        assertTrue(service.healthy())
        assertTrue(service.waitingForRecovery())
        assertEquals(1, runtime.dispatches)
        assertEquals(1, CompanionBridge.preferences(service).getInt("failures", 0))
    }
    private fun stopBeforeRetry(change: () -> Unit) {
        start(); runtime.reply!!(true)
        service.state(state("DEVICE_OFFLINE", false))
        change()
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(10))
        assertFalse(service.healthy())
        assertEquals(1, runtime.dispatches)
        assertEquals(1, runtime.events.size)
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun permissionLossCancelsFastRecovery() = stopBeforeRetry {
        runtime.failure = "BLUETOOTH_PERMISSION_DENIED"
    }
    @Test fun userDisableCancelsFastRecovery() = stopBeforeRetry {
        CompanionBridge.preferences(service).edit().putBoolean("enabled", false).commit()
    }
    @Test fun associationRevisionChangeCancelsFastRecovery() = stopBeforeRetry {
        CompanionBridge.preferences(service).edit().putString("revision", "replacement").commit()
    }
    @Test fun runtimeLossCancelsFastRecovery() = stopBeforeRetry { runtime.engineLive = false }
    @Test fun terminalFailureDoesNotStartFastRecovery() {
        start(); runtime.reply!!(true)
        service.state(state("FAILED", false))
        assertFalse(service.healthy())
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(10))
        assertEquals(1, runtime.dispatches)
    }
    @Test fun newPresenceWakeReplacesPendingRetryWithoutASecondDelayedDispatch() {
        start(); runtime.reply!!(true)
        service.state(state("DEVICE_OFFLINE", false))
        service.onStartCommand(Intent().putExtra("reason", "presence"), 0, 2)
        runtime.reply!!(true); service.state(state())
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(10))
        assertEquals(2, runtime.dispatches)
    }
    @Test fun failedCheckRemainsPendingButCompletedCheckClearsIt() {
        start(); runtime.reply!!(true)
        service.state(state("CHECKING", busy = true))
        service.state(state("CHECK_FAILED"))
        assertTrue(CompanionBridge.preferences(service).getBoolean("checkPending", false))
        service.state(state("NO_UPDATE") + ("checkFinished" to true))
        assertFalse(CompanionBridge.preferences(service).getBoolean("checkPending", true))
    }
    @Test fun disabledModeCannotInitializeHeadlessEngine() {
        CompanionBridge.preferences(service).edit().putBoolean("enabled", false).commit()
        start(); assertEquals(0, runtime.starts); assertFalse(service.healthy())
    }
    @Test fun cleanStopIsIdempotentAndDoesNotOwnAnotherTask() {
        start(); runtime.reply!!(true); service.state(state())
        service.stopCompanion("USER_DISABLED"); service.stopCompanion("USER_DISABLED")
        assertFalse(service.ownsDevice(key, service.runtimeId))
        assertEquals(1, runtime.events.size)
    }
    @Test fun responsiveRuntimeNeedsAConnectionOrBoundedProgressToSuppressRecovery() {
        start(); runtime.reply!!(true); runtime.autoProbe = true; runtime.gatt = false
        assertTrue(service.healthy())
        assertFalse(service.recoveryHealthy())
        assertTrue(service.state(state("INITIALIZING", false, true) + mapOf("recoveryBusy" to true, "recoveryId" to "a".repeat(32))))
        assertTrue(service.recoveryHealthy())
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(31))
        assertFalse(service.healthy())
        assertEquals("CONNECTION_PROGRESS_TIMEOUT", CompanionBridge.preferences(service).getString("lastResult", ""))
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }
    @Test fun progressStagesAndLateStateCannotExtendTheRecoveryDeadline() {
        start(); runtime.reply!!(true); runtime.autoProbe = true; runtime.gatt = false
        val recovery = mapOf("recoveryBusy" to true, "recoveryId" to "a".repeat(32))
        service.state(state("INITIALIZING", false, true) + recovery + ("stateSequence" to 1L))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(20))
        service.state(state("DISCOVERING", false, true) + recovery + ("stateSequence" to 3L))
        assertFalse(service.state(state("CONNECTING", false, true) + recovery + ("stateSequence" to 2L)))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(11))
        assertFalse(service.healthy())
    }
    @Test fun notificationIsChineseAndProjectsActualConnectedAndCheckState() {
        start(); runtime.reply!!(true)
        assertEquals("E-Track \u8bbe\u5907\u8fde\u63a5", shadowOf(service).lastForegroundNotification.extras.getString(Notification.EXTRA_TITLE))
        service.state(state("NO_UPDATE"))
        val notification = shadowOf(service.getSystemService(NotificationManager::class.java)).getNotification(CompanionService.NOTIFICATION_ID)
        assertEquals("\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u56fa\u4ef6\u5df2\u662f\u6700\u65b0\u7248\u672c", notification.extras.getString(Notification.EXTRA_TEXT))
    }
    @Test fun controlHealthDoesNotCountAsAnotherSuccessfulUpdateCheck() {
        start(); runtime.reply!!(true)
        assertTrue(service.state(state("READY_AWAITING_DEVICE_CHOICE") + ("checkFinished" to true)))
        val before = CompanionDiagnostics.snapshot(service)["quality"] as Map<*, *>
        assertTrue(service.state(state("READY_AWAITING_DEVICE_CHOICE") + ("controlOnly" to true)))
        val after = CompanionDiagnostics.snapshot(service)["quality"] as Map<*, *>
        assertEquals(before["checksSucceeded"], after["checksSucceeded"])
        assertFalse(CompanionBridge.preferences(service).getBoolean("checkPending", false))
        assertTrue(CompanionDiagnostics.snapshot(service)["history"].toString().contains("CONTROL_CHANNEL_READY"))
        val notification = shadowOf(service.getSystemService(NotificationManager::class.java)).getNotification(CompanionService.NOTIFICATION_ID)
        assertEquals("\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u6709\u53ef\u7528\u56fa\u4ef6\u66f4\u65b0", notification.extras.getString(Notification.EXTRA_TEXT))
    }
    @Test fun boundedDiagnosticsSurviveStatusChangesWithoutPrivateFields() {
        start(); runtime.reply!!(true)
        repeat(100) { CompanionDiagnostics.record(service, "RECOVERY_FAILED", service.runtimeId,
            details = mapOf("stage" to "DISCOVERING", "errorType" to "PlatformException", "errorCode" to 133,
                "address" to address, "url" to "https://private.invalid/?token=secret", "payload" to "secret")) }
        service.state(state())
        val snapshot = CompanionDiagnostics.snapshot(service)
        val history = snapshot["history"] as List<*>
        assertEquals(80, history.size)
        val text = history.toString()
        assertTrue(text.contains("133"))
        assertFalse(text.contains(address)); assertFalse(text.contains("secret")); assertFalse(text.contains("private.invalid"))
        assertTrue(text.contains("RECOVERY_FAILED"))
    }
}
