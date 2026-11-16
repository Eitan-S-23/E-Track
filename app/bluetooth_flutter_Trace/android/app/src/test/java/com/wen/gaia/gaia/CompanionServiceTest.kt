package com.wen.gaia.gaia

import android.content.Context
import android.content.Intent
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
        val events = mutableListOf<String>()
        override fun problem(context: Context) = failure
        override fun initialize(context: Context) { starts++ }
        override fun dispatch(payload: Map<String, Any>, done: (Boolean) -> Unit) { reply = done }
        override fun probe(id: String, done: (Boolean) -> Unit) { probeReply = done }
        override fun live() = engineLive
        override fun connected(context: Context) = gatt
        override fun lost(id: String) { events.add(id) }
    }

    @Before fun setUp() {
        service = Robolectric.buildService(CompanionService::class.java).create().get()
        runtime = Runtime(); service.execution = runtime
        CompanionBridge.preferences(service).edit().clear().putBoolean("enabled", true)
            .putString("revision", revision).putString("address", address).commit()
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
    @Test fun offlineResultBacksOffAndReleasesWakeLock() {
        start(); runtime.reply!!(true)
        assertTrue(service.state(state("DEVICE_OFFLINE", false)))
        assertFalse(service.healthy())
        val prefs = CompanionBridge.preferences(service)
        assertEquals(1, prefs.getInt("failures", 0))
        assertTrue(prefs.getLong("nextAttempt", 0) > System.currentTimeMillis())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
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
}
