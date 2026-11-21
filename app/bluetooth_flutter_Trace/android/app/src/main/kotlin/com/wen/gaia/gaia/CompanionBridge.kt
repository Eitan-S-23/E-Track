package com.wen.gaia.gaia

import android.Manifest
import android.app.Activity
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.job.JobInfo
import android.app.job.JobScheduler
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanFilter
import android.companion.AssociationInfo
import android.companion.AssociationRequest
import android.companion.BluetoothLeDeviceFilter
import android.companion.CompanionDeviceManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentSender
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.PersistableBundle
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.FlutterEngineCache
import io.flutter.embedding.engine.dart.DartExecutor
import io.flutter.plugin.common.MethodChannel
import java.lang.ref.WeakReference
import java.security.MessageDigest
import java.util.UUID

/** One retained engine and one association, shared by UI, jobs and presence callbacks. */
object CompanionBridge {
    const val CHANNEL = "trace/companion"
    const val NOTIFICATION_CHANNEL = "e_track_companion"
    const val ASSOCIATION_REQUEST = 2410
    const val CHECK_JOB = 2411
    const val RECOVERY_JOB = 2412
    const val STARTUP_JOB = 2413
    internal const val STARTUP_DEADLINE = "startupDeadlineElapsed"
    internal const val STARTUP_WINDOW_MS = 120000L
    private val handler = Handler(Looper.getMainLooper())
    private var activity = WeakReference<Activity>(null)
    private var foreground = false
    private var engine: FlutterEngine? = null
    private var channel: MethodChannel? = null
    private var ready = false
    private var associationResult: MethodChannel.Result? = null
    private var associationAddress: String? = null
    private var associationPrompted = false
    private var associationDeadline: Runnable? = null

    fun preferences(context: Context) = context.getSharedPreferences("e_track_companion", Context.MODE_PRIVATE)
    fun enabled(context: Context) = preferences(context).getBoolean("enabled", false)
    fun address(context: Context): String? = preferences(context).getString("address", null)
    fun revision(context: Context): String = preferences(context).getString("revision", "") ?: ""
    fun isForeground() = foreground && activity.get() != null
    fun deviceToken(address: String) = MessageDigest.getInstance("SHA-256")
        .digest(address.lowercase().toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

    @Suppress("DEPRECATION")
    fun associated(context: Context): Boolean {
        val target = address(context) ?: return false
        if (Build.VERSION.SDK_INT < 26) return false
        return try {
            val manager = context.getSystemService(CompanionDeviceManager::class.java) ?: return false
            if (Build.VERSION.SDK_INT >= 33) manager.myAssociations.any {
                it.deviceMacAddress?.toString()?.equals(target, true) == true
            } else manager.associations.any { it.equals(target, true) }
        } catch (_: Exception) { false }
    }

    fun problem(context: Context): String? = try { readProblem(context) }
        catch (_: Exception) { "PLATFORM_STATE_UNAVAILABLE" }

    private fun readProblem(context: Context): String? {
        if (Build.VERSION.SDK_INT < 26) return "ANDROID_26_REQUIRED"
        if (!associated(context)) return "ASSOCIATION_REQUIRED"
        val permission = if (Build.VERSION.SDK_INT >= 31) Manifest.permission.BLUETOOTH_CONNECT else Manifest.permission.BLUETOOTH
        if (ContextCompat.checkSelfPermission(context, permission) != PackageManager.PERMISSION_GRANTED)
            return "BLUETOOTH_PERMISSION_DENIED"
        if (Build.VERSION.SDK_INT >= 31 && ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED)
            return "BLUETOOTH_SCAN_PERMISSION_DENIED"
        val manager = context.getSystemService(BluetoothManager::class.java)
        if (manager?.adapter?.isEnabled != true) return "BLUETOOTH_OFF"
        DeviceOtaBridge.notificationProblem(context)?.let { return it }
        val notifications = context.getSystemService(NotificationManager::class.java)
        notifications.createNotificationChannel(NotificationChannel(NOTIFICATION_CHANNEL,
            "E-Track \u8bbe\u5907\u8fde\u63a5", NotificationManager.IMPORTANCE_LOW))
        if (notifications.getNotificationChannel(NOTIFICATION_CHANNEL)?.importance == NotificationManager.IMPORTANCE_NONE)
            return "COMPANION_CHANNEL_DISABLED"
        return null
    }

    fun snapshot(context: Context): Map<String, Any?> {
        val prefs = preferences(context)
        return mapOf("sdk" to Build.VERSION.SDK_INT, "enabled" to enabled(context),
            "address" to address(context), "associated" to associated(context),
            "presenceSupported" to (Build.VERSION.SDK_INT >= 31),
            "sensorBackgroundSupported" to (Build.VERSION.SDK_INT >= 31),
            "serviceRunning" to (CompanionService.active?.healthy() == true),
            "connectionHealthy" to (CompanionService.active?.recoveryHealthy() == true),
            "runtimeId" to CompanionService.active?.runtimeId,
            "revision" to revision(context), "problem" to problem(context),
            "intervalHours" to prefs.getInt("intervalHours", 12),
            "wifiOnly" to false,
            "unmetered" to (context.getSystemService(ConnectivityManager::class.java)?.isActiveNetworkMetered == false),
            "networkAvailable" to (context.getSystemService(ConnectivityManager::class.java)?.activeNetwork != null),
            "batteryUnrestricted" to context.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(context.packageName),
            "vendorAutostart" to "unknown", "lastResult" to prefs.getString("lastResult", "NOT_RUN"))
    }

    fun appInfo(context: Context): Map<String, Any> {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        @Suppress("DEPRECATION")
        val code = if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else info.versionCode.toLong()
        return mapOf("versionName" to (info.versionName ?: ""), "versionCode" to code,
            "sourceApkPath" to context.applicationInfo.sourceDir)
    }

    fun install(value: FlutterEngine, context: Context, host: Activity? = null) {
        if (host != null) activity = WeakReference(host)
        if (engine === value) {
            if (host != null && ready) channel?.invokeMethod("attachUi", null)
            return
        }
        engine = value
        ready = false
        val app = context.applicationContext
        channel = MethodChannel(value.dartExecutor.binaryMessenger, CHANNEL).apply {
            setMethodCallHandler { call, result ->
                try {
                    when (call.method) {
                        "hasActivity" -> result.success(activity.get() != null)
                        "snapshot" -> result.success(snapshot(app))
                        "diagnostics" -> CompanionJournal.query(app, call.arguments as? Map<*, *>) { answer ->
                            handler.post { answer.fold({ result.success(it) }, { result.error("JOURNAL_READ_FAILED", "Local diagnostic read failed", null) }) }
                        }
                        "diagnosticDetail" -> {
                            requireForeground()
                            CompanionJournal.detailed(call.argument<Int>("minutes") ?: 0)
                            result.success(true)
                        }
                        "diagnosticExport" -> {
                            requireForeground()
                            CompanionJournal.export(app) { answer -> handler.post {
                                answer.fold({ file ->
                                    try {
                                        requireForeground()
                                        val uri = FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", file)
                                        activity.get()!!.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND)
                                            .setType("application/zip").putExtra(Intent.EXTRA_STREAM, uri)
                                            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "E-Track diagnostics"))
                                        result.success(mapOf("bytes" to file.length(), "complete" to true))
                                    } catch (_: Exception) { result.error("EXPORT_SHARE_FAILED", "Return to the app and retry export", null) }
                                }, { result.error("JOURNAL_EXPORT_FAILED", "Local diagnostic export failed", null) })
                            } }
                        }
                        "journal" -> {
                            val values = call.arguments as? Map<*, *>
                            CompanionDiagnostics.record(app, values?.get("status") as? String ?: "UNKNOWN", details = values)
                            result.success(true)
                        }
                        "diagnostic" -> {
                            val values = call.arguments as? Map<*, *>
                            if (values == null || values["runtimeId"] != CompanionService.active?.runtimeId ||
                                values["revision"] != revision(app)) result.success(false)
                            else {
                                CompanionDiagnostics.record(app, values["status"] as? String ?: "UNKNOWN",
                                    CompanionService.active?.runtimeId, attempt = (values["attempt"] as? Number)?.toInt() ?: 0,
                                    details = values)
                                result.success(true)
                            }
                        }
                        "ready" -> {
                            ready = true
                            result.success(snapshot(app))
                            CompanionService.active?.dispatch()
                            if (activity.get() != null) channel?.invokeMethod("attachUi", null)
                        }
                        "associate" -> associate(app, call.argument<String>("address"), result)
                        "configure" -> {
                            requireForeground()
                            if (DeviceOtaService.active?.hasTask() == true) throw IllegalStateException("OTA_BUSY")
                            val enable = call.argument<Boolean>("enabled") == true
                            val hours = call.argument<Int>("intervalHours") ?: 12
                            require(hours in listOf(6, 12, 24)) { "INVALID_INTERVAL" }
                            if (enable) problem(app)?.let { throw IllegalStateException(it) }
                            val nextRevision = if (enable && enabled(app)) revision(app) else UUID.randomUUID().toString()
                            check(preferences(app).edit().putBoolean("enabled", enable).putInt("intervalHours", hours)
                                .putBoolean("wifiOnly", false)
                                .putString("revision", nextRevision).commit()) { "SETTINGS_NOT_PERSISTED" }
                            restore(app)
                            if (enable) CompanionService.start(app, "foreground") else CompanionService.active?.stopCompanion("USER_DISABLED")
                            result.success(snapshot(app))
                        }
                        "settings" -> result.success(openSettings(app, call.argument<String>("kind")))
                        "state" -> result.success(CompanionService.active?.state(call.arguments as? Map<*, *>) == true)
                        "check" -> {
                            requireForeground()
                            if (!enabled(app)) throw IllegalStateException("COMPANION_DISABLED")
                            CompanionService.start(app, "manual")
                            result.success(snapshot(app))
                        }
                        else -> result.notImplemented()
                    }
                } catch (error: Exception) {
                    result.error("COMPANION_UNAVAILABLE", error.message ?: "Platform operation failed", null)
                }
            }
        }
        value.addEngineLifecycleListener(object : FlutterEngine.EngineLifecycleListener {
            override fun onPreEngineRestart() { ready = false; CompanionService.active?.stopCompanion("ENGINE_RESTART") }
            override fun onEngineWillDestroy() {
                if (engine !== value) return
                ready = false
                engine = null
                channel?.setMethodCallHandler(null)
                channel = null
                CompanionService.active?.stopCompanion("ENGINE_LOST")
            }
        })
    }

    fun lifecycle(host: Activity, resumed: Boolean) {
        if (resumed || activity.get() === host) { activity = WeakReference(host); foreground = resumed }
        if (resumed && ready) channel?.invokeMethod("attachUi", null)
    }

    fun ensureEngine(context: Context) {
        check(Looper.myLooper() == Looper.getMainLooper())
        val existing = FlutterEngineCache.getInstance().get(DeviceOtaBridge.ENGINE_ID)
        if (existing != null) { install(existing, context); return }
        val value = FlutterEngine(context.applicationContext)
        FlutterEngineCache.getInstance().put(DeviceOtaBridge.ENGINE_ID, value)
        DeviceOtaBridge.installRuntime(value, context.applicationContext)
        install(value, context)
        MethodChannel(value.dartExecutor.binaryMessenger, "trace/app_update").setMethodCallHandler { call, result ->
            when (call.method) {
                "getAppInfo" -> result.success(appInfo(context))
                "installApk" -> result.error("APP_NOT_FOREGROUND", "Open the app to install", null)
                else -> result.notImplemented()
            }
        }
        value.dartExecutor.executeDartEntrypoint(DartExecutor.DartEntrypoint.createDefault())
    }

    fun dispatch(payload: Map<String, Any>, done: (Boolean) -> Unit) {
        if (!ready || engine?.dartExecutor?.isExecutingDart != true) { done(false); return }
        channel?.invokeMethod("wake", payload, object : MethodChannel.Result {
            override fun success(value: Any?) { done(value == true) }
            override fun error(code: String, message: String?, details: Any?) { done(false) }
            override fun notImplemented() { done(false) }
        }) ?: done(false)
    }

    fun probe(runtimeId: String, done: (Boolean) -> Unit) {
        if (!ready) { done(false); return }
        channel?.invokeMethod("probe", mapOf("runtimeId" to runtimeId), object : MethodChannel.Result {
            override fun success(value: Any?) { done(value == runtimeId) }
            override fun error(code: String, message: String?, details: Any?) { done(false) }
            override fun notImplemented() { done(false) }
        }) ?: done(false)
    }

    fun runtimeLost(runtimeId: String) { channel?.invokeMethod("lost", mapOf("runtimeId" to runtimeId)) }

    fun restore(context: Context) {
        val scheduler = context.getSystemService(JobScheduler::class.java)
        if (!enabled(context) || !associated(context)) {
            scheduler.cancel(CHECK_JOB); scheduler.cancel(RECOVERY_JOB); scheduler.cancel(STARTUP_JOB)
            if (Build.VERSION.SDK_INT >= 31) address(context)?.let {
                try { context.getSystemService(CompanionDeviceManager::class.java).stopObservingDevicePresence(it) }
                catch (_: Exception) { /* No active observation is also a stopped state. */ }
            }
            return
        }
        val prefs = preferences(context)
        val component = ComponentName(context, CompanionJobService::class.java)
        val hours = prefs.getInt("intervalHours", 12).coerceIn(6, 24)
        val network = JobInfo.NETWORK_TYPE_ANY
        val existing = scheduler.getPendingJob(CHECK_JOB)
        if (existing == null || existing.intervalMillis != hours * 3600000L || existing.networkType != network)
            check(scheduler.schedule(JobInfo.Builder(CHECK_JOB, component).setPersisted(true)
                .setPeriodic(hours * 3600000L).setRequiredNetworkType(network).build()) == JobScheduler.RESULT_SUCCESS) { "SCHEDULING_REJECTED" }
        if (scheduler.getPendingJob(RECOVERY_JOB) == null)
            check(scheduler.schedule(JobInfo.Builder(RECOVERY_JOB, component).setPersisted(true)
                .setPeriodic(15 * 60000L).build()) == JobScheduler.RESULT_SUCCESS) { "SCHEDULING_REJECTED" }
        if (Build.VERSION.SDK_INT >= 31) {
            try { context.getSystemService(CompanionDeviceManager::class.java).startObservingDevicePresence(address(context)!!) }
            catch (_: Exception) { prefs.edit().putString("lastResult", "PRESENCE_UNAVAILABLE_PERIODIC_FALLBACK").apply() }
        }
    }

    fun restoreAfterSystemRestart(context: Context) {
        restore(context)
        recoverStartup(context, SystemClock.elapsedRealtime() + STARTUP_WINDOW_MS)
    }

    internal fun recoverStartup(context: Context, deadlineElapsed: Long) {
        val scheduler = context.getSystemService(JobScheduler::class.java)
        if (!enabled(context) || !associated(context) || CompanionService.active?.healthy() == true) {
            scheduler.cancel(STARTUP_JOB)
            return
        }
        val prefs = preferences(context)
        val remaining = deadlineElapsed - SystemClock.elapsedRealtime()
        if (remaining <= 0 || remaining > STARTUP_WINDOW_MS) {
            scheduler.cancel(STARTUP_JOB)
            prefs.edit().putString("lastResult", "STARTUP_RECOVERY_TIMEOUT").apply()
            return
        }
        if (CompanionService.start(context, "recovery")) {
            scheduler.cancel(STARTUP_JOB)
            Log.i("ETrackCompanion", "System recovery requested the foreground runtime")
            return
        }
        val problem = prefs.getString("lastResult", "START_REJECTED")
        Log.i("ETrackCompanion", "System recovery deferred: $problem")
        if (problem !in listOf("BLUETOOTH_OFF", "PLATFORM_STATE_UNAVAILABLE")) {
            scheduler.cancel(STARTUP_JOB)
            return
        }
        // This non-persisted job spans radio initialization, not another boot or an endless loop.
        val extras = PersistableBundle().apply { putLong(STARTUP_DEADLINE, deadlineElapsed) }
        check(scheduler.schedule(JobInfo.Builder(STARTUP_JOB, ComponentName(context, CompanionJobService::class.java))
            .setMinimumLatency(minOf(5000L, remaining)).setOverrideDeadline(minOf(15000L, remaining))
            .setExtras(extras).build()) == JobScheduler.RESULT_SUCCESS) { "SCHEDULING_REJECTED" }
    }

    private fun requireForeground(): Activity {
        if (!isForeground()) throw IllegalStateException("APP_NOT_FOREGROUND")
        return activity.get()!!
    }

    @Suppress("DEPRECATION")
    private fun associate(context: Context, target: String?, result: MethodChannel.Result) {
        val host = requireForeground()
        require(Build.VERSION.SDK_INT >= 26) { "ANDROID_26_REQUIRED" }
        require(target != null && Regex("(?i)[0-9a-f]{2}(:[0-9a-f]{2}){5}").matches(target)) { "INVALID_DEVICE_ADDRESS" }
        check(associationResult == null && CompanionService.active == null && DeviceOtaService.active?.hasTask() != true) { "OWNER_BUSY" }
        val manager = context.getSystemService(CompanionDeviceManager::class.java)
        associationResult = result; associationAddress = target; associationPrompted = false
        associationDeadline = Runnable { finishAssociation(context, false, result) }.also { handler.postDelayed(it, 180000) }
        try {
            val request = AssociationRequest.Builder().setSingleDevice(true).addDeviceFilter(
                BluetoothLeDeviceFilter.Builder().setScanFilter(
                    ScanFilter.Builder().setDeviceAddress(target.uppercase()).build()).build()).build()
            manager.associate(request, object : CompanionDeviceManager.Callback() {
                private fun prompt(sender: IntentSender) {
                    if (associationPrompted || associationResult !== result) return
                    associationPrompted = true
                    try { host.startIntentSenderForResult(sender, ASSOCIATION_REQUEST, null, 0, 0, 0) }
                    catch (_: Exception) { finishAssociation(context, false, result) }
                }
                override fun onDeviceFound(sender: IntentSender) = prompt(sender)
                override fun onAssociationPending(sender: IntentSender) = prompt(sender)
                override fun onAssociationCreated(info: AssociationInfo) {
                    finishAssociation(context, info.deviceMacAddress?.toString()?.equals(target, true) == true, result)
                }
                override fun onFailure(error: CharSequence?) { finishAssociation(context, false, result) }
            }, handler)
        } catch (_: Exception) { finishAssociation(context, false, result) }
    }

    fun activityResult(context: Context, requestCode: Int, resultCode: Int) {
        if (requestCode != ASSOCIATION_REQUEST) return
        if (resultCode != Activity.RESULT_OK) finishAssociation(context, false)
        else if (Build.VERSION.SDK_INT < 33) finishAssociation(context, true)
    }

    private fun finishAssociation(context: Context, accepted: Boolean, expected: MethodChannel.Result? = associationResult) {
        if (associationResult !== expected) return
        val result = associationResult ?: return
        associationDeadline?.let { handler.removeCallbacks(it) }; associationDeadline = null
        val target = associationAddress
        associationResult = null; associationAddress = null
        if (!accepted || target == null) { result.success(snapshot(context)); return }
        val prefs = preferences(context)
        val old = address(context)
        if (!prefs.edit().putString("address", target.lowercase()).commit()) {
            result.error("SETTINGS_NOT_PERSISTED", "Association selection was not saved", null); return
        }
        if (!associated(context)) {
            prefs.edit().putString("address", old).commit()
            result.error("ASSOCIATION_UNCONFIRMED", "System association was not established", null)
            return
        }
        prefs.edit().putString("revision", UUID.randomUUID().toString()).commit()
        result.success(snapshot(context))
    }

    private fun openSettings(context: Context, kind: String?): Boolean {
        val host = requireForeground()
        val details = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
        val intent = when (kind) {
            "bluetooth" -> Intent(Settings.ACTION_BLUETOOTH_SETTINGS)
            "notifications" -> Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
            "battery" -> Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
            "autostart" -> {
                val component = when (Build.MANUFACTURER.lowercase()) {
                    "xiaomi" -> ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity")
                    "huawei", "honor" -> ComponentName("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity")
                    "oppo", "realme" -> ComponentName("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity")
                    "vivo" -> ComponentName("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity")
                    else -> null
                }
                if (component == null) details else Intent().setComponent(component)
            }
            else -> details
        }
        return try { host.startActivity(intent); true } catch (_: Exception) {
            try { host.startActivity(details); false } catch (_: Exception) { false }
        }
    }

    fun gattConnected(context: Context): Boolean = try {
        val target = address(context)
        context.getSystemService(BluetoothManager::class.java).getConnectedDevices(BluetoothProfile.GATT)
            .any { it.address.equals(target, true) }
    } catch (_: Exception) { false }
}
