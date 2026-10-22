package com.wen.gaia.gaia

import android.app.Notification
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Looper
import io.flutter.embedding.android.FlutterActivity
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.StandardMethodCodec
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.annotation.RealObject
import org.robolectric.shadows.ShadowPowerManager
import java.time.Duration
import java.nio.ByteBuffer

/** Real Android Service/notification/PowerManager under Robolectric, not Dart. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], shadows = [OtaEmbeddingBoundary::class])
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

    @Test fun initialRevisionAlsoFencesLateProgress() {
        runtime.initial = snapshot("applying", 20, false)
        start(); runtime.answer(true)
        assertTrue(service.publish(key, snapshot("transferring", 19)))
        service.onStartCommand(key.put(Intent().setAction(DeviceOtaBridge.CANCEL)), 0, 2)
        assertFalse(runtime.events.contains("cancel"))
    }

    @Test fun engineLossReleasesWakeLockAndService() {
        start(); runtime.answer(true)
        service.runtimeLost()
        assertFalse(service.hasTask())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        assertTrue(runtime.events.contains("ENGINE_LOST"))
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

    private fun openIntent(task: DeviceOtaKey = key) = task.put(Intent(
        DeviceOtaBridge.OPEN, Uri.parse(
            "trace-device-ota://task/${task.taskId}/${task.generation}/open")))

    private fun deliverNewIntent(activity: MainActivity, intent: Intent) {
        // FlutterActivity keeps this lifecycle callback protected; reflection
        // preserves the production access level while exercising the real
        // MainActivity -> embedding boundary.
        MainActivity::class.java.getDeclaredMethod("onNewIntent", Intent::class.java).apply {
            isAccessible = true
            invoke(activity, intent)
        }
    }

    private fun withOpenChannel(test: (List<MethodCall>) -> Unit) {
        val calls = mutableListOf<MethodCall>()
        val messenger = object : BinaryMessenger {
            override fun send(channel: String, message: ByteBuffer?) {
                send(channel, message, null)
            }
            override fun send(channel: String, message: ByteBuffer?, reply: BinaryMessenger.BinaryReply?) {
                if (message != null) {
                    val bytes = message.duplicate()
                    bytes.flip()
                    calls.add(StandardMethodCodec.INSTANCE.decodeMethodCall(bytes))
                }
            }
            override fun setMessageHandler(channel: String, handler: BinaryMessenger.BinaryMessageHandler?) {}
        }
        val field = DeviceOtaBridge::class.java.getDeclaredField("channel").apply { isAccessible = true }
        val previous = field.get(null)
        field.set(null, MethodChannel(messenger, "trace/device_ota"))
        OtaEmbeddingBoundary.initialUris.clear()
        OtaEmbeddingBoundary.newUris.clear()
        try { test(calls) } finally { field.set(null, previous) }
    }

    @Test fun internalNewIntentIsSanitizedBeforeEmbeddingAndOpensExactlyOnce() {
        start(); runtime.answer(true)
        withOpenChannel { calls ->
            val activity = Robolectric.buildActivity(MainActivity::class.java).create().get()
            deliverNewIntent(activity, openIntent())
            assertEquals(listOf<String?>(null), OtaEmbeddingBoundary.newUris)
            assertNull(activity.intent.data)
            assertEquals(listOf("open"), calls.map { it.method })
            assertEquals(key, DeviceOtaKey.from(calls.single().arguments))
        }
    }

    @Test fun staleOrMalformedNotificationNeverReachesEitherRoute() {
        start(); runtime.answer(true)
        withOpenChannel { calls ->
            val activity = Robolectric.buildActivity(MainActivity::class.java).create().get()
            deliverNewIntent(activity, openIntent(key.copy(generation = 2)))
            deliverNewIntent(activity, openIntent(key.copy(taskId = "old_task")))
            deliverNewIntent(activity, Intent(Intent.ACTION_VIEW,
                Uri.parse("trace-device-ota://task/forged/1/open")))
            assertEquals(listOf<String?>(null, null, null), OtaEmbeddingBoundary.newUris)
            assertTrue(calls.isEmpty())
        }
    }

    @Test fun recreatedActivitySanitizesInitialIntentBeforeEmbeddingReadsIt() {
        start(); runtime.answer(true)
        withOpenChannel { calls ->
            val activity = Robolectric.buildActivity(MainActivity::class.java, openIntent()).create().get()
            assertEquals(listOf<String?>(null), OtaEmbeddingBoundary.initialUris)
            assertNull(activity.intent.dataString)
            assertEquals(listOf("open"), calls.map { it.method })
        }
    }

    @Test fun recreatedProcessRejectsOldInitialNotificationWithoutRouting() {
        withOpenChannel { calls ->
            Robolectric.buildActivity(MainActivity::class.java, openIntent()).create()
            assertEquals(listOf<String?>(null), OtaEmbeddingBoundary.initialUris)
            assertTrue(calls.isEmpty())
        }
    }

    @Test fun externalTraceLinksStillReachEmbeddingUnchanged() {
        withOpenChannel { calls ->
            val external = "trace://share/existing-link"
            val activity = Robolectric.buildActivity(MainActivity::class.java,
                Intent(Intent.ACTION_VIEW, Uri.parse(external))).create().get()
            deliverNewIntent(activity, Intent(Intent.ACTION_VIEW, Uri.parse(external)))
            assertEquals(listOf(external), OtaEmbeddingBoundary.initialUris)
            assertEquals(listOf(external), OtaEmbeddingBoundary.newUris)
            assertEquals(external, activity.intent.dataString)
            assertTrue(calls.isEmpty())
        }
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

/** Capture the actual MainActivity -> embedding entry, without loading libflutter.
 * Flutter's automatic routing consumes these Intent data values before Dart.
 * The service and key validation above remain real; only the embedding is shadowed.
 */
@Implements(FlutterActivity::class)
class OtaEmbeddingBoundary {
    @RealObject lateinit var activity: FlutterActivity

    @Implementation fun onCreate(state: Bundle?) { initialUris.add(activity.intent?.dataString) }
    @Implementation fun onNewIntent(intent: Intent) { newUris.add(intent.dataString) }

    companion object {
        val initialUris = mutableListOf<String?>()
        val newUris = mutableListOf<String?>()
    }
}
