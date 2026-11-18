package com.wen.gaia.gaia

import android.Manifest
import android.app.Activity
import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanFilter
import android.companion.BluetoothLeDeviceFilter
import android.companion.CompanionDeviceManager
import android.content.Context
import android.content.ComponentName
import android.content.Intent
import android.content.IntentSender
import android.os.Build
import android.os.Looper
import android.os.PersistableBundle
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.FlutterEngineCache
import io.flutter.embedding.engine.dart.DartExecutor
import io.flutter.embedding.engine.loader.FlutterLoader
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.FlutterException
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.StandardMethodCodec
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.shadow.api.Shadow
import org.robolectric.shadows.ShadowPowerManager
import org.robolectric.shadows.ShadowBluetoothManager
import org.robolectric.util.ReflectionHelpers
import java.lang.ref.WeakReference
import java.nio.ByteBuffer
import java.time.Duration

/** Real Bridge/Service/receiver/job orchestration. Only OS and embedding edges are fake. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [26, 31, 34], instrumentedPackages = ["io.flutter"], shadows = [
    CompanionEngineBoundary::class, CompanionDartBoundary::class, CompanionLoaderBoundary::class,
    CompanionBluetoothBoundary::class])
class CompanionIntegrationTest {
    private lateinit var app: Application
    private var host: ActivityController<CompanionChooserActivity>? = null
    private val address = "aa:bb:cc:dd:ee:ff"
    private val revision = "revision-1"
    private val key = DeviceOtaKey("companion_test", 1, CompanionBridge.deviceToken(address), "b".repeat(64))
    private val cache get() = FlutterEngineCache.getInstance()
    private val manager get() = app.getSystemService(CompanionDeviceManager::class.java)
    private val prefs get() = CompanionBridge.preferences(app)
    private val engine get() = cache.get(DeviceOtaBridge.ENGINE_ID)!!
    private val dart get() = Shadow.extract<CompanionDartBoundary>(engine.dartExecutor)
    private val messages get() = dart.messages

    @Before fun setUp() {
        app = RuntimeEnvironment.getApplication()
        prefs.edit().clear().commit()
        CompanionEngineBoundary.created = 0
        // Model a fresh process at the test boundary, not inside any exercised operation.
        ReflectionHelpers.setField(CompanionBridge, "activity", WeakReference<Activity>(null))
        ReflectionHelpers.setField(CompanionBridge, "foreground", false)
        shadowOf(app).grantPermissions(Manifest.permission.BLUETOOTH, Manifest.permission.BLUETOOTH_SCAN,
            Manifest.permission.BLUETOOTH_CONNECT, Manifest.permission.POST_NOTIFICATIONS)
        shadowOf(app.getSystemService(BluetoothManager::class.java).adapter).setState(BluetoothAdapter.STATE_ON)
        shadowOf(app.getSystemService(NotificationManager::class.java)).setNotificationsEnabled(true)
    }

    @After fun tearDown() {
        CompanionBridge.activityResult(app, CompanionBridge.ASSOCIATION_REQUEST, Activity.RESULT_CANCELED)
        DeviceOtaService.active?.onDestroy()
        CompanionService.active?.onDestroy()
        cache.get(DeviceOtaBridge.ENGINE_ID)?.destroy()
        host?.let { CompanionBridge.lifecycle(it.get(), false); it.pause().stop().destroy() }
        cache.clear()
    }

    private fun associated(enabled: Boolean = true) {
        shadowOf(manager).addAssociation(address)
        prefs.edit().putString("address", address).putString("revision", revision)
            .putBoolean("enabled", enabled).commit()
        assertTrue(CompanionBridge.associated(app))
    }

    private fun ui(): CompanionChooserActivity {
        CompanionBridge.ensureEngine(app)
        val controller = Robolectric.buildActivity(CompanionChooserActivity::class.java).setup()
        host = controller
        CompanionBridge.install(engine, app, controller.get())
        CompanionBridge.lifecycle(controller.get(), true)
        return controller.get()
    }

    private fun incoming(method: String, arguments: Any? = null, channel: String = CompanionBridge.CHANNEL) =
        messages.incoming(channel, method, arguments)

    private fun start(reason: String = "recovery"): CompanionService {
        assertTrue(CompanionService.start(app, reason))
        val intent = shadowOf(app).nextStartedService!!
        assertEquals(CompanionService::class.java.name, intent.component!!.className)
        assertEquals(reason, intent.getStringExtra("reason"))
        val service = Robolectric.buildService(CompanionService::class.java).create().get()
        service.onStartCommand(intent, 0, 1)
        assertNotNull("Headless startup: ${prefs.getString("lastResult", null)}", cache.get(DeviceOtaBridge.ENGINE_ID))
        return service
    }

    private fun ready(service: CompanionService) {
        incoming("ready").requireSuccess()
        val wake = messages.sent.last { it.call.method == "wake" }
        assertEquals(service.runtimeId, (wake.call.arguments as Map<*, *>)["runtimeId"])
        wake.answer(true)
        assertTrue(service.healthy())
    }

    private fun linked(service: CompanionService) {
        val bluetooth = app.getSystemService(BluetoothManager::class.java)
        shadowOf(bluetooth).addDevice(BluetoothProfile.GATT, BluetoothProfile.STATE_CONNECTED,
            bluetooth.adapter.getRemoteDevice(address.uppercase()))
        assertEquals(true, incoming("state", state(service)).requireSuccess())
    }

    private fun state(service: CompanionService, status: String = "CONNECTED") = mapOf(
        "runtimeId" to service.runtimeId, "revision" to revision, "status" to status,
        "connected" to true, "busy" to false, "deviceToken" to key.deviceToken)

    private fun job(id: Int, extras: PersistableBundle = PersistableBundle()): JobParameters = Shadow.newInstanceOf(JobParameters::class.java).also {
        ReflectionHelpers.setField(it, "jobId", id)
        ReflectionHelpers.setField(it, "extras", extras)
    }

    private fun offerOta(service: CompanionService, runtime: String = service.runtimeId) = incoming(
        "acquireCompanion", key.map() + mapOf("companionRuntimeId" to runtime,
            "revision" to 1L, "phase" to "transferring", "label" to "Firmware transfer", "totalBytes" to 8192,
            "durableBytes" to 0, "receivedBytes" to 0, "canCancel" to true), "trace/device_ota")

    @Test fun realAdmissionRejectsMissingAssociationPermissionRadioAndChannels() {
        assertEquals("ASSOCIATION_REQUIRED", CompanionBridge.problem(app))
        associated()
        assertNull(CompanionBridge.problem(app))
        val permission = if (Build.VERSION.SDK_INT >= 31) Manifest.permission.BLUETOOTH_CONNECT else Manifest.permission.BLUETOOTH
        shadowOf(app).denyPermissions(permission)
        assertEquals("BLUETOOTH_PERMISSION_DENIED", CompanionBridge.problem(app))
        assertFalse(CompanionService.start(app, "recovery"))
        assertEquals(0, CompanionEngineBoundary.created)
        shadowOf(app).grantPermissions(permission)
        if (Build.VERSION.SDK_INT >= 31) {
            shadowOf(app).denyPermissions(Manifest.permission.BLUETOOTH_SCAN)
            assertEquals("BLUETOOTH_SCAN_PERMISSION_DENIED", CompanionBridge.problem(app))
            shadowOf(app).grantPermissions(Manifest.permission.BLUETOOTH_SCAN)
        }
        val bluetooth = app.getSystemService(BluetoothManager::class.java).adapter
        shadowOf(bluetooth).setState(BluetoothAdapter.STATE_OFF)
        assertEquals("BLUETOOTH_OFF", CompanionBridge.problem(app))
        shadowOf(bluetooth).setState(BluetoothAdapter.STATE_ON)
        val notifications = app.getSystemService(NotificationManager::class.java)
        shadowOf(notifications).setNotificationsEnabled(false)
        assertEquals("NOTIFICATIONS_DISABLED", CompanionBridge.problem(app))
        shadowOf(notifications).setNotificationsEnabled(true)
        notifications.deleteNotificationChannel(CompanionBridge.NOTIFICATION_CHANNEL)
        notifications.createNotificationChannel(NotificationChannel(CompanionBridge.NOTIFICATION_CHANNEL,
            "Disabled companion", NotificationManager.IMPORTANCE_NONE))
        assertEquals("COMPANION_CHANNEL_DISABLED", CompanionBridge.problem(app))
        assertFalse(CompanionService.start(app, "periodic"))
        assertEquals(0, CompanionEngineBoundary.created)
    }

    @Test fun launcherAndApplicationResolveTheSameExplicitBrandedIcon() {
        val info = app.packageManager.getActivityInfo(ComponentName(app, MainActivity::class.java), 0)
        assertEquals(R.mipmap.e_track_launcher, app.applicationInfo.icon)
        assertEquals(R.mipmap.e_track_launcher, info.icon)
        assertNotEquals(R.mipmap.ic_launcher, info.icon)
        assertNotNull(app.packageManager.getApplicationIcon(app.packageName))
        assertNotNull(app.packageManager.getActivityIcon(ComponentName(app, MainActivity::class.java)))
    }

    @Test @Config(sdk = [34]) fun notificationRuntimeRevocationIsNotAChannelGrant() {
        associated()
        shadowOf(app).denyPermissions(Manifest.permission.POST_NOTIFICATIONS)
        assertEquals("NOTIFICATION_PERMISSION_DENIED", CompanionBridge.problem(app))
        assertFalse(CompanionService.start(app, "presence"))
        assertNull(shadowOf(app).nextStartedService)
    }

    @Test fun chooserNeedsForegroundAndConfirmedSystemAssociation() {
        assertFalse(BluetoothAdapter.checkBluetoothAddress(address))
        assertTrue(BluetoothAdapter.checkBluetoothAddress(address.uppercase()))
        CompanionBridge.ensureEngine(app)
        val rejected = incoming("associate", mapOf("address" to address))
        assertEquals("APP_NOT_FOREGROUND", rejected.errorMessage)
        val activity = ui()
        val selection = incoming("associate", mapOf("address" to address))
        assertEquals(0, selection.replies)
        val request = shadowOf(manager).lastAssociationRequest
        assertTrue(request.isSingleDevice)
        val filters = ReflectionHelpers.callInstanceMethod<List<BluetoothLeDeviceFilter>>(request, "getDeviceFilters")
        val scanFilter = ReflectionHelpers.callInstanceMethod<ScanFilter>(filters.single(), "getScanFilter")
        assertEquals(address.uppercase(), scanFilter.deviceAddress)
        val callback = shadowOf(manager).lastAssociationCallback
        val sender = PendingIntent.getActivity(app, 51, Intent("test.chooser"), PendingIntent.FLAG_IMMUTABLE).intentSender
        callback.onDeviceFound(sender)
        if (Build.VERSION.SDK_INT >= 33) callback.onAssociationPending(sender)
        assertEquals(1, activity.prompts)
        assertNull(CompanionBridge.address(app))
        assertFalse(CompanionBridge.enabled(app))
        shadowOf(manager).addAssociation(address)
        CompanionBridge.activityResult(app, CompanionBridge.ASSOCIATION_REQUEST, Activity.RESULT_OK)
        if (Build.VERSION.SDK_INT >= 33) {
            assertEquals("Activity OK alone is not modern CDM confirmation", 0, selection.replies)
            callback.onAssociationCreated(manager.myAssociations.single())
        }
        assertEquals(true, (selection.requireSuccess() as Map<*, *>)["associated"])
        assertEquals(address, CompanionBridge.address(app))
        assertFalse(CompanionBridge.enabled(app))
        callback.onFailure("late duplicate")
        assertEquals(1, selection.replies)
    }

    @Test fun chooserCancelTimeoutAndOldCallbacksCannotSelectTheNextDevice() {
        ui()
        val cancelled = incoming("associate", mapOf("address" to address))
        val old = shadowOf(manager).lastAssociationCallback
        CompanionBridge.activityResult(app, CompanionBridge.ASSOCIATION_REQUEST, Activity.RESULT_CANCELED)
        assertEquals(1, cancelled.replies)
        val waiting = incoming("associate", mapOf("address" to "aa:bb:cc:dd:ee:01"))
        val current = shadowOf(manager).lastAssociationCallback
        old.onFailure("late")
        val sender = PendingIntent.getActivity(app, 52, Intent("test.chooser"), PendingIntent.FLAG_IMMUTABLE).intentSender
        old.onDeviceFound(sender)
        assertEquals(0, host!!.get().prompts)
        assertEquals(0, waiting.replies)
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(181))
        assertEquals(1, waiting.replies)
        current.onDeviceFound(sender)
        current.onFailure("late timeout")
        assertEquals(1, waiting.replies)
        assertNull(CompanionBridge.address(app))
        assertFalse(CompanionBridge.enabled(app))
    }

    @Test fun chooserCannotTrustOkWithoutMatchingAssociation() {
        ui()
        val selection = incoming("associate", mapOf("address" to address))
        if (Build.VERSION.SDK_INT >= 33) {
            shadowOf(manager).addAssociation("aa:bb:cc:dd:ee:01")
            shadowOf(manager).lastAssociationCallback.onAssociationCreated(manager.myAssociations.single())
            assertEquals(false, (selection.requireSuccess() as Map<*, *>)["associated"])
        } else {
            CompanionBridge.activityResult(app, CompanionBridge.ASSOCIATION_REQUEST, Activity.RESULT_OK)
            assertEquals("ASSOCIATION_UNCONFIRMED", selection.errorCode)
        }
        assertNull(CompanionBridge.address(app))
        assertFalse(CompanionBridge.enabled(app))
    }

    @Test fun configureSettingsAndResumeDoNotManufactureAuthorization() {
        val activity = ui()
        assertEquals(true, incoming("settings", mapOf("kind" to "permissions")).requireSuccess())
        assertNotNull(shadowOf(activity).nextStartedActivity)
        val args = mapOf("enabled" to true, "intervalHours" to 12, "wifiOnly" to true)
        assertEquals("ASSOCIATION_REQUIRED", incoming("configure", args).errorMessage)
        assertFalse(CompanionBridge.enabled(app))
        associated(enabled = false)
        CompanionBridge.lifecycle(activity, false)
        assertEquals("APP_NOT_FOREGROUND", incoming("configure", args).errorMessage)
        CompanionBridge.lifecycle(activity, true)
        val configured = incoming("configure", args).requireSuccess() as Map<*, *>
        assertEquals(true, configured["enabled"])
        assertEquals(false, configured["serviceRunning"])
        assertEquals("unknown", configured["vendorAutostart"])
        assertEquals(12, prefs.getInt("intervalHours", 0))
        assertEquals("foreground", shadowOf(app).nextStartedService!!.getStringExtra("reason"))
        assertEquals("INVALID_INTERVAL", incoming("configure", args + ("intervalHours" to 1)).errorMessage)
        assertEquals(12, prefs.getInt("intervalHours", 0))
        incoming("configure", args + ("enabled" to false)).requireSuccess()
        assertTrue(app.getSystemService(JobScheduler::class.java).allPendingJobs.isEmpty())
    }

    @Test fun bootAndPackageReplacementRequestImmediateRecoveryWithoutLaunchingUi() {
        associated()
        prefs.edit().putInt("intervalHours", 6).putBoolean("checkPending", true).commit()
        for (action in listOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED)) {
            CompanionBootReceiver().onReceive(app, Intent(action))
            val scheduler = app.getSystemService(JobScheduler::class.java)
            assertEquals(2, scheduler.allPendingJobs.size)
            val check = checkNotNull(scheduler.getPendingJob(CompanionBridge.CHECK_JOB))
            val recovery = checkNotNull(scheduler.getPendingJob(CompanionBridge.RECOVERY_JOB))
            assertEquals(6 * 3600000L, check.intervalMillis)
            assertTrue(check.isPersisted)
            assertEquals(android.app.job.JobInfo.NETWORK_TYPE_ANY, check.networkType)
            assertEquals(15 * 60000L, recovery.intervalMillis)
            assertTrue(prefs.getBoolean("checkPending", false))
            assertNull(shadowOf(app).nextStartedActivity)
            val requested = checkNotNull(shadowOf(app).nextStartedService)
            assertEquals(CompanionService::class.java.name, requested.component!!.className)
            assertEquals("recovery", requested.getStringExtra("reason"))
            assertFalse("A service request is not runtime ownership", CompanionService.active?.healthy() == true)
            assertEquals(0, CompanionEngineBoundary.created)
        }
        prefs.edit().putBoolean("enabled", false).commit()
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        assertTrue(app.getSystemService(JobScheduler::class.java).allPendingJobs.isEmpty())
        assertNull(shadowOf(app).nextStartedService)
    }

    @Test @Config(sdk = [33]) fun realBootRequestStartsHeadlessRuntimeAndDoesNotDuplicateHealthyOwnership() {
        associated()
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        val requested = checkNotNull(shadowOf(app).nextStartedService)
        val service = Robolectric.buildService(CompanionService::class.java).create().get()
        service.onStartCommand(requested, 0, 1)
        assertEquals(1, CompanionEngineBoundary.created)
        assertEquals(listOf("main"), dart.entrypoints)
        ready(service); linked(service)
        assertTrue(service.healthy())
        assertNull(shadowOf(app).nextStartedActivity)
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        assertNull(shadowOf(app).nextStartedService)
        assertEquals(1, CompanionEngineBoundary.created)
    }

    @Test fun bootRecoveryWaitsBrieflyForRadioInsteadOfThePeriodicJob() {
        associated()
        val bluetooth = app.getSystemService(BluetoothManager::class.java).adapter
        shadowOf(bluetooth).setState(BluetoothAdapter.STATE_OFF)
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        assertNull(shadowOf(app).nextStartedService)
        val scheduler = app.getSystemService(JobScheduler::class.java)
        val pending = checkNotNull(scheduler.getPendingJob(CompanionBridge.STARTUP_JOB))
        assertFalse(pending.isPersisted)
        assertEquals(5000L, pending.minLatencyMillis)
        assertEquals(15000L, pending.maxExecutionDelayMillis)
        assertEquals("BLUETOOTH_OFF", prefs.getString("lastResult", null))
        shadowOf(bluetooth).setState(BluetoothAdapter.STATE_ON)
        val jobs = Robolectric.buildService(CompanionJobService::class.java).create().get()
        assertFalse(jobs.onStartJob(job(CompanionBridge.STARTUP_JOB, pending.extras)))
        assertEquals("recovery", checkNotNull(shadowOf(app).nextStartedService).getStringExtra("reason"))
        assertNull(scheduler.getPendingJob(CompanionBridge.STARTUP_JOB))
        assertNotNull(scheduler.getPendingJob(CompanionBridge.RECOVERY_JOB))
        jobs.onDestroy()
    }

    @Test fun startupRetryRetainsItsDeadlineAndStopsWhenExpiredOrDisabled() {
        associated()
        shadowOf(app.getSystemService(BluetoothManager::class.java).adapter).setState(BluetoothAdapter.STATE_OFF)
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        val scheduler = app.getSystemService(JobScheduler::class.java)
        val pending = checkNotNull(scheduler.getPendingJob(CompanionBridge.STARTUP_JOB))
        val jobs = Robolectric.buildService(CompanionJobService::class.java).create().get()
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(5))
        assertFalse(jobs.onStartJob(job(CompanionBridge.STARTUP_JOB, pending.extras)))
        assertEquals(pending.extras.getLong(CompanionBridge.STARTUP_DEADLINE),
            checkNotNull(scheduler.getPendingJob(CompanionBridge.STARTUP_JOB)).extras.getLong(CompanionBridge.STARTUP_DEADLINE))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(CompanionBridge.STARTUP_WINDOW_MS))
        assertFalse(jobs.onStartJob(job(CompanionBridge.STARTUP_JOB, pending.extras)))
        assertNull(shadowOf(app).nextStartedService)
        assertNull(scheduler.getPendingJob(CompanionBridge.STARTUP_JOB))
        assertEquals("STARTUP_RECOVERY_TIMEOUT", prefs.getString("lastResult", null))
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        assertNotNull(scheduler.getPendingJob(CompanionBridge.STARTUP_JOB))
        prefs.edit().putBoolean("enabled", false).commit()
        CompanionBridge.restore(app)
        assertTrue(scheduler.allPendingJobs.isEmpty())
        jobs.onDestroy()
    }

    @Test fun bootPermissionDenialDoesNotStartOrCreateAStartupRetryLoop() {
        associated()
        val permission = if (Build.VERSION.SDK_INT >= 31) Manifest.permission.BLUETOOTH_CONNECT else Manifest.permission.BLUETOOTH
        shadowOf(app).denyPermissions(permission)
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_BOOT_COMPLETED))
        assertNull(shadowOf(app).nextStartedService)
        assertNull(shadowOf(app).nextStartedActivity)
        assertNull(app.getSystemService(JobScheduler::class.java).getPendingJob(CompanionBridge.STARTUP_JOB))
        assertEquals("BLUETOOTH_PERMISSION_DENIED", prefs.getString("lastResult", null))
        assertEquals(0, CompanionEngineBoundary.created)
    }

    @Test fun lostAssociationCancelsRestoredJobs() {
        associated()
        CompanionBridge.restore(app)
        assertEquals(2, app.getSystemService(JobScheduler::class.java).allPendingJobs.size)
        if (Build.VERSION.SDK_INT >= 33) manager.disassociate(manager.myAssociations.single().id)
        else manager.disassociate(address)
        CompanionBootReceiver().onReceive(app, Intent(Intent.ACTION_MY_PACKAGE_REPLACED))
        assertTrue(app.getSystemService(JobScheduler::class.java).allPendingJobs.isEmpty())
        assertFalse(CompanionService.start(app, "recovery"))
        assertEquals(0, CompanionEngineBoundary.created)
    }

    @Test fun periodicAndRecoveryJobsRespectBackoffAndRetainPendingWork() {
        associated()
        val jobs = Robolectric.buildService(CompanionJobService::class.java).create().get()
        prefs.edit().putLong("nextAttempt", System.currentTimeMillis() + 60000).commit()
        assertFalse(jobs.onStartJob(job(CompanionBridge.CHECK_JOB)))
        assertTrue(prefs.getBoolean("checkPending", false))
        assertNull(shadowOf(app).nextStartedService)
        prefs.edit().putLong("nextAttempt", 0).commit()
        assertFalse(jobs.onStartJob(job(CompanionBridge.RECOVERY_JOB)))
        val requested = shadowOf(app).nextStartedService!!
        assertEquals("recovery", requested.getStringExtra("reason"))
        assertTrue(prefs.getBoolean("checkPending", false))
        assertEquals("Scheduling is not acknowledged runtime ownership", 0, CompanionEngineBoundary.created)
        jobs.onDestroy()
    }

    @Test fun headlessStartNeedsReadyWakeAndRealGattBeforeOtaAdmission() {
        associated()
        val service = start()
        assertEquals(1, CompanionEngineBoundary.created)
        assertEquals(listOf("main"), dart.entrypoints)
        assertEquals(false, incoming("hasActivity").requireSuccess())
        assertNotNull(shadowOf(service).lastForegroundNotification)
        assertFalse(service.healthy())
        assertEquals("COMPANION_NOT_OWNED", (offerOta(service).requireSuccess() as Map<*, *>)["reason"])
        incoming("ready").requireSuccess()
        assertFalse(service.healthy())
        messages.sent.last { it.call.method == "wake" }.answer(true)
        assertTrue(service.healthy())
        assertEquals("Dart cannot invent GATT", false, incoming("state", state(service)).requireSuccess())
        linked(service)
        assertTrue(service.ownsDevice(key, service.runtimeId))
        assertEquals("COMPANION_NOT_OWNED", (offerOta(service, "old-runtime").requireSuccess() as Map<*, *>)["reason"])
        val acquired = offerOta(service)
        assertEquals(0, acquired.replies)
        val intent = shadowOf(app).nextStartedService!!
        assertEquals(DeviceOtaService::class.java.name, intent.component!!.className)
        val ota = Robolectric.buildService(DeviceOtaService::class.java).create().get()
        ota.onStartCommand(intent, 0, 1)
        val result = acquired.requireSuccess() as Map<*, *>
        assertEquals(result.toString(), "ACQUIRED", result["status"])
        assertTrue(ota.owns(key))
        assertNull(shadowOf(app).nextStartedActivity)
        ota.onDestroy()
    }

    @Test fun liveHeadlessOwnerReusesOneEngineWhenUiReturns() {
        associated()
        val service = start()
        ready(service); linked(service)
        val original = engine
        val activity = ui()
        CompanionBridge.lifecycle(activity, false)
        CompanionBridge.ensureEngine(app)
        CompanionBridge.lifecycle(activity, true)
        assertSame(original, engine)
        assertEquals(1, CompanionEngineBoundary.created)
        assertEquals(listOf("main"), dart.entrypoints)
        assertTrue(messages.sent.any { it.call.method == "attachUi" })
        assertTrue(service.healthy())
        assertTrue(service.ownsDevice(key, service.runtimeId))
    }

    @Test fun permissionRevocationIsCheckedAtRealAdmissionAndHeartbeat() {
        associated()
        val service = start()
        ready(service); linked(service)
        val permission = if (Build.VERSION.SDK_INT >= 31) Manifest.permission.BLUETOOTH_CONNECT else Manifest.permission.BLUETOOTH
        shadowOf(app).denyPermissions(permission)
        assertFalse(service.ownsDevice(key, service.runtimeId))
        assertEquals(if (Build.VERSION.SDK_INT >= 31) "BLUETOOTH_PERMISSION_DENIED" else "COMPANION_NOT_OWNED",
            (offerOta(service).requireSuccess() as Map<*, *>)["reason"])
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(31))
        assertFalse(service.healthy())
        assertEquals("PERMISSION_OR_ASSOCIATION_LOST", prefs.getString("lastResult", null))
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        assertTrue(messages.sent.any { it.call.method == "lost" })
    }

    @Test fun headlessEngineLossAndRecoveryRejectOldStateAndReusePersistedConfiguration() {
        associated()
        prefs.edit().putBoolean("checkPending", true).commit()
        val old = start()
        ready(old); linked(old)
        val oldState = state(old)
        engine.destroy()
        assertFalse(old.healthy())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        old.onDestroy()
        val recovered = start()
        assertNotEquals(old.runtimeId, recovered.runtimeId)
        assertEquals(2, CompanionEngineBoundary.created)
        assertEquals(false, incoming("state", oldState).requireSuccess())
        ready(recovered)
        val wake = messages.sent.last { it.call.method == "wake" }.call.arguments as Map<*, *>
        assertEquals(true, wake["checkPending"])
        assertEquals(address, wake["address"])
        assertEquals(revision, wake["revision"])
        assertFalse("Old connection state is not restored consent", recovered.ownsDevice(key, recovered.runtimeId))
        linked(recovered)
        assertTrue(recovered.ownsDevice(key, recovered.runtimeId))
        assertTrue(prefs.getBoolean("checkPending", false))
    }

    @Test fun lateWakeAfterHeadlessStartupTimeoutCannotResurrectOwnership() {
        associated()
        val service = start()
        incoming("ready").requireSuccess()
        val pending = messages.sent.last { it.call.method == "wake" }
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(21))
        assertEquals("RUNTIME_START_TIMEOUT", prefs.getString("lastResult", null))
        pending.answer(true)
        assertFalse(service.healthy())
        assertFalse(ShadowPowerManager.getLatestWakeLock().isHeld)
        assertEquals(false, incoming("state", state(service)).requireSuccess())
    }

    @Test fun healthyRecoveryJobDoesNotStartDuplicateWorkUnlessCheckIsPending() {
        associated()
        val service = start()
        ready(service); linked(service)
        val jobs = Robolectric.buildService(CompanionJobService::class.java).create().get()
        assertFalse(jobs.onStartJob(job(CompanionBridge.RECOVERY_JOB)))
        assertNull(shadowOf(app).nextStartedService)
        assertFalse(jobs.onStartJob(job(CompanionBridge.CHECK_JOB)))
        assertEquals("periodic", shadowOf(app).nextStartedService!!.getStringExtra("reason"))
        assertTrue(prefs.getBoolean("checkPending", false))
        assertEquals(1, CompanionEngineBoundary.created)
        jobs.onDestroy()
    }
}

class CompanionChooserActivity : Activity() {
    var prompts = 0
    override fun startIntentSenderForResult(sender: IntentSender, requestCode: Int,
        fillInIntent: Intent?, flagsMask: Int, flagsValues: Int, extraFlags: Int) {
        assertEquals(CompanionBridge.ASSOCIATION_REQUEST, requestCode)
        prompts++
    }
}

// Android 8 calls Binder directly, bypassing the stock shadow's matching method.
// Keep the same Robolectric GATT state instead of faking project admission.
@Implements(BluetoothManager::class)
class CompanionBluetoothBoundary : ShadowBluetoothManager() {
    @Implementation(minSdk = 26, maxSdk = 30)
    protected fun getConnectedDevices(profile: Int): List<BluetoothDevice> =
        getDevicesMatchingConnectionStates(profile, intArrayOf(BluetoothProfile.STATE_CONNECTED))
}

/** JNI/Dart VM are external to this host test; all project method handlers remain real. */
// Delegated constructors run before a Context-only shadow hook. Never enter JNI.
@Implements(value = FlutterEngine::class, isInAndroidSdk = false, callThroughByDefault = false)
class CompanionEngineBoundary {
    private val executor = Shadow.newInstanceOf(DartExecutor::class.java)
    private val listeners = mutableListOf<FlutterEngine.EngineLifecycleListener>()
    @Implementation fun __constructor__(context: Context) { created++ }
    @Implementation fun getDartExecutor() = executor
    @Implementation fun addEngineLifecycleListener(listener: FlutterEngine.EngineLifecycleListener) { listeners.add(listener) }
    @Implementation fun destroy() {
        listeners.toList().forEach { it.onEngineWillDestroy() }
        listeners.clear()
        Shadow.extract<CompanionDartBoundary>(executor).executing = false
    }
    companion object { var created = 0 }
}

@Implements(value = FlutterLoader::class, isInAndroidSdk = false, callThroughByDefault = false)
class CompanionLoaderBoundary {
    @Implementation fun initialized() = true
    @Implementation fun findAppBundlePath() = "flutter_assets"
}

@Implements(value = DartExecutor::class, isInAndroidSdk = false, callThroughByDefault = false)
class CompanionDartBoundary {
    val messages = CompanionMessenger()
    val entrypoints = mutableListOf<String>()
    var executing = false
    @Implementation fun getBinaryMessenger(): BinaryMessenger = messages
    @Implementation fun isExecutingDart() = executing
    @Implementation fun executeDartEntrypoint(entry: DartExecutor.DartEntrypoint) {
        entrypoints.add(entry.dartEntrypointFunctionName)
        executing = true
    }
}

class CompanionReply {
    var replies = 0
    var value: Any? = null
    var errorCode: String? = null
    var errorMessage: String? = null
    fun receive(bytes: ByteBuffer?) {
        replies++
        try { value = bytes?.let { StandardMethodCodec.INSTANCE.decodeEnvelope(it.apply { flip() }) } }
        catch (error: FlutterException) { errorCode = error.code; errorMessage = error.message }
    }
    fun requireSuccess(): Any? { assertEquals(1, replies); assertNull(errorCode); return value }
}

class CompanionMessenger : BinaryMessenger {
    class Sent(val channel: String, val call: MethodCall, private val reply: BinaryMessenger.BinaryReply?) {
        fun answer(value: Any?) { reply?.reply(StandardMethodCodec.INSTANCE.encodeSuccessEnvelope(value).apply { flip() }) }
    }
    val sent = mutableListOf<Sent>()
    private val handlers = mutableMapOf<String, BinaryMessenger.BinaryMessageHandler>()
    override fun setMessageHandler(channel: String, handler: BinaryMessenger.BinaryMessageHandler?) {
        if (handler == null) handlers.remove(channel) else handlers[channel] = handler
    }
    override fun send(channel: String, message: ByteBuffer?) = send(channel, message, null)
    override fun send(channel: String, message: ByteBuffer?, reply: BinaryMessenger.BinaryReply?) {
        val call = StandardMethodCodec.INSTANCE.decodeMethodCall(message!!.apply { flip() })
        val request = Sent(channel, call, reply)
        sent.add(request)
        if (call.method == "probe") {
            val args = call.arguments as Map<*, *>
            request.answer(if (channel == CompanionBridge.CHANNEL) args["runtimeId"] else args + ("ownerLive" to true))
        }
    }
    fun incoming(channel: String, method: String, arguments: Any?): CompanionReply {
        val result = CompanionReply()
        val message = StandardMethodCodec.INSTANCE.encodeMethodCall(MethodCall(method, arguments)).apply { flip() }
        handlers.getValue(channel).onMessage(message, result::receive)
        return result
    }
}
