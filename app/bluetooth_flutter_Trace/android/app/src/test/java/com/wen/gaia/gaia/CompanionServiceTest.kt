package com.wen.gaia.gaia

import android.content.Context
import android.content.Intent
import android.app.Notification
import android.app.NotificationManager
import android.os.Looper
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowPowerManager
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
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
        var autoProbe = false
        val events = mutableListOf<String>()
        override fun problem(context: Context) = failure
        override fun initialize(context: Context) { starts++ }
        override fun dispatch(payload: Map<String, Any>, done: (Boolean) -> Unit) { dispatches++; reply = done }
        override fun probe(id: String, done: (Boolean) -> Unit) { probeReply = done; if (autoProbe) done(true) }
        override fun live() = engineLive
        override fun connected(context: Context) = gatt
        override fun lost(id: String) { events.add(id) }
    }

    @Before fun setUp() {
        service = Robolectric.buildService(CompanionService::class.java).create().get()
        runtime = Runtime(); service.execution = runtime
        CompanionBridge.preferences(service).edit().clear().putBoolean("enabled", true)
            .putString("revision", revision).putString("address", address).commit()
        service.getSharedPreferences("companion_diagnostics_v1", Context.MODE_PRIVATE).edit().clear().commit()
    }
    @After fun tearDown() { service.onDestroy() }
    private fun start() { service.onStartCommand(Intent().putExtra("reason", "foreground"), 0, 1) }
    private fun state(status: String = "CONNECTED", connected: Boolean = true, busy: Boolean = false) =
        mapOf("runtimeId" to service.runtimeId, "revision" to revision,
            "deviceToken" to CompanionBridge.deviceToken(address), "status" to status,
            "connected" to connected, "busy" to busy)

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
        assertFalse(service.healthy())
        assertEquals(1, prefs.getInt("failures", 0))
        assertTrue(prefs.getLong("nextAttempt", 0) > System.currentTimeMillis())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        assertEquals(1, runtime.starts)
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
        assertFalse(service.healthy())
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
