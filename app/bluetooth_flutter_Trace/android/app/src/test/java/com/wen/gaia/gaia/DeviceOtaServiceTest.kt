package com.wen.gaia.gaia

import android.app.Notification
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

/** Real Android Service/notification/PowerManager under Robolectric, not Dart. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class DeviceOtaServiceTest {
    private val key = DeviceOtaKey("process_1", 1, "a".repeat(64), "b".repeat(64))
    private lateinit var service: DeviceOtaService
    private lateinit var runtime: FakeRuntime

    private fun snapshot(phase: String = "transferring", revision: Long = 1,
        cancel: Boolean = true) = key.map() + mapOf("phase" to phase,
        "revision" to revision, "label" to "MCU durable", "totalBytes" to 8192,
        "durableBytes" to 4096, "receivedBytes" to 8192,
        "canCancel" to cancel, "targetVerified" to false)

    @Before fun setUp() {
        service = Robolectric.buildService(DeviceOtaService::class.java).create().get()
        runtime = FakeRuntime(key, snapshot())
        service.runtime = runtime
    }

    @After fun tearDown() { service.onDestroy() }

    private fun start() = service.onStartCommand(key.put(Intent()), 0, 1)

    @Test fun noAcknowledgementUntilOwnerProbe() {
        start()
        assertNotNull(shadowOf(service).lastForegroundNotification)
        assertFalse(service.owns(key))
        assertTrue(ShadowPowerManager.getLatestWakeLock().isHeld)
        runtime.answer(true)
        assertTrue(service.owns(key))
        assertEquals(listOf("acquired"), runtime.events)
    }

    @Test fun deniedProbeReleasesWakeLockAndService() {
        start()
        runtime.answer(false)
        assertFalse(service.hasTask())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        assertTrue(runtime.events.contains("OWNER_PROBE_FAILED"))
    }

    @Test fun lateProbeCannotReviveReleasedTask() {
        start()
        service.release(key)
        runtime.answer(true)
        assertFalse(service.hasTask())
        assertFalse(runtime.events.contains("acquired"))
    }

    @Test fun notificationUsesDurableNotSentBytes() {
        start()
        val n = shadowOf(service).lastForegroundNotification
        assertEquals(50, n.extras.getInt(Notification.EXTRA_PROGRESS))
        assertFalse(n.extras.getBoolean(Notification.EXTRA_PROGRESS_INDETERMINATE))
    }

    @Test fun applyingIsIndeterminateAndCannotCancel() {
        start(); runtime.answer(true)
        assertTrue(service.publish(key, snapshot("applying", 2, false)))
        val n = shadowOf(service).lastForegroundNotification
        // Updates go through NotificationManager, not a second startForeground.
        val manager = service.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
        val updated = shadowOf(manager).getNotification(DeviceOtaBridge.NOTIFICATION_ID)
        assertTrue(updated.extras.getBoolean(Notification.EXTRA_PROGRESS_INDETERMINATE))
        assertNull(updated.actions)
        assertNotNull(n)
        service.onStartCommand(key.put(Intent().setAction(DeviceOtaBridge.CANCEL)), 0, 2)
        assertFalse(runtime.events.contains("cancel"))
    }

    @Test fun staleActionsAndReleaseDoNotTouchCurrentOwner() {
        start(); runtime.answer(true)
        val old = key.copy(generation = 9)
        service.onStartCommand(old.put(Intent().setAction(DeviceOtaBridge.CANCEL)), 0, 2)
        service.release(old)
        assertTrue(service.owns(key))
        assertFalse(runtime.events.contains("cancel"))
        service.onStartCommand(key.put(Intent().setAction(DeviceOtaBridge.CANCEL)), 0, 3)
        assertTrue(runtime.events.contains("cancel"))
    }

    @Test fun oldProgressCannotOverwriteNewRevision() {
        start(); runtime.answer(true)
        assertTrue(service.publish(key, snapshot("applying", 20, false)))
        assertTrue(service.publish(key, snapshot("transferring", 19)))
        service.onStartCommand(key.put(Intent().setAction(DeviceOtaBridge.CANCEL)), 0, 2)
        assertFalse(runtime.events.contains("cancel"))
    }

    @Test fun permissionsLostAndEngineLostReleaseResources() {
        start(); runtime.answer(true)
        runtime.problem = "CHANNEL_DISABLED"
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(5))
        assertFalse(service.hasTask())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
    }

    @Test fun unverifiedCompletionFailsClosed() {
        start(); runtime.answer(true)
        assertFalse(service.publish(key, snapshot("completed", 2, false)))
        assertFalse(service.hasTask())
    }

    @Test fun processRecreationDoesNotTrustNotificationOrCache() {
        runtime.initial = null
        start()
        assertFalse(service.hasTask())
        assertFalse(service.owns(key))
        assertNull(shadowOf(service).lastForegroundNotification)
    }

    @Test fun keysRequireFullPackageAndDeviceBinding() {
        assertEquals(key, DeviceOtaKey.from(key.map()))
        assertNull(DeviceOtaKey.from(key.map() + ("packageSha256" to "b")))
        assertNotEquals(key, DeviceOtaKey.from(key.map() + ("deviceToken" to "c".repeat(64))))
        assertNotEquals(2401, DeviceOtaBridge.NOTIFICATION_ID)
        assertNotEquals("trace_update", DeviceOtaBridge.CHANNEL_ID)
    }

    private class FakeRuntime(val key: DeviceOtaKey, var initial: Map<*, *>?) : DeviceOtaRuntime {
        var problem: String? = null
        var callback: ((Boolean) -> Unit)? = null
        val events = mutableListOf<String>()
        fun answer(value: Boolean) { callback!!.invoke(value) }
        override fun initial(key: DeviceOtaKey) = if (key == this.key) initial else null
        override fun problem(context: Context) = problem
        override fun live() = true
        override fun probe(key: DeviceOtaKey, done: (Boolean) -> Unit) { callback = done }
        override fun acquired(key: DeviceOtaKey) { events.add("acquired") }
        override fun unavailable(key: DeviceOtaKey, reason: String) { events.add(reason) }
        override fun event(method: String, key: DeviceOtaKey) { events.add(method) }
    }
}
