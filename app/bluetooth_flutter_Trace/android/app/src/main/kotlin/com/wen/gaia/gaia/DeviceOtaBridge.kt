package com.wen.gaia.gaia

import android.Manifest
import android.app.Activity
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.FlutterEngineCache
import io.flutter.plugin.common.MethodChannel
import java.lang.ref.WeakReference

data class DeviceOtaKey(val taskId: String, val generation: Long,
    val deviceToken: String, val packageSha256: String) {
    fun map(): Map<String, Any> = mapOf("taskId" to taskId,
        "generation" to generation, "deviceToken" to deviceToken,
        "packageSha256" to packageSha256)

    fun put(intent: Intent): Intent = intent.apply {
        putExtra("taskId", taskId)
        putExtra("generation", generation)
        putExtra("deviceToken", deviceToken)
        putExtra("packageSha256", packageSha256)
    }

    companion object {
        fun from(value: Any?): DeviceOtaKey? {
            val m = value as? Map<*, *> ?: return null
            val id = m["taskId"] as? String ?: return null
            val generation = (m["generation"] as? Number)?.toLong() ?: return null
            val device = m["deviceToken"] as? String ?: return null
            val sha = m["packageSha256"] as? String ?: return null
            if (!Regex("[a-zA-Z0-9_-]{1,100}").matches(id) || generation < 1 ||
                !Regex("[0-9a-f]{64}").matches(device) ||
                !Regex("[0-9a-f]{64}").matches(sha)) return null
            return DeviceOtaKey(id, generation, device, sha)
        }

        fun from(intent: Intent?): DeviceOtaKey? = intent?.let {
            from(mapOf("taskId" to it.getStringExtra("taskId"),
                "generation" to it.getLongExtra("generation", -1),
                "deviceToken" to it.getStringExtra("deviceToken"),
                "packageSha256" to it.getStringExtra("packageSha256")))
        }
    }
}

/** The cached UI engine is also the sole OTA/BLE runtime. No second isolate. */
object DeviceOtaBridge {
    const val ENGINE_ID = "trace-device-ota-engine"
    const val CHANNEL_ID = "trace_device_ota"
    const val NOTIFICATION_ID = 2408
    const val OPEN = "com.wen.gaia.gaia.DEVICE_OTA_OPEN"
    const val CANCEL = "com.wen.gaia.gaia.DEVICE_OTA_CANCEL"
    private val handler = Handler(Looper.getMainLooper())
    private var engine: FlutterEngine? = null
    private var channel: MethodChannel? = null
    private var activity = WeakReference<Activity>(null)
    private var foreground = false
    private var pending: MethodChannel.Result? = null
    private var pendingKey: DeviceOtaKey? = null
    private var initial: Map<*, *>? = null
    private var timeout: Runnable? = null

    fun install(engine: FlutterEngine, host: Activity) {
        activity = WeakReference(host)
        if (this.engine === engine) return
        this.engine = engine
        FlutterEngineCache.getInstance().put(ENGINE_ID, engine)
        val context = host.applicationContext
        channel = MethodChannel(engine.dartExecutor.binaryMessenger, "trace/device_ota").apply {
            setMethodCallHandler { call, result ->
                val key = DeviceOtaKey.from(call.arguments)
                if (key == null) {
                    result.error("INVALID_TASK_KEY", "Invalid device OTA identity", null)
                    return@setMethodCallHandler
                }
                when (call.method) {
                    "acquire" -> acquire(context, key,
                        call.arguments as Map<*, *>, result)
                    "check" -> result.success(DeviceOtaService.active?.owns(key) == true)
                    "publish" -> result.success(DeviceOtaService.active?.publish(key,
                        call.arguments as Map<*, *>) == true)
                    "release" -> {
                        if (pendingKey == key) unavailable(key, "RELEASED")
                        DeviceOtaService.active?.release(key)
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
        }
        engine.addEngineLifecycleListener(object : FlutterEngine.EngineLifecycleListener {
            override fun onPreEngineRestart() { DeviceOtaService.active?.runtimeLost() }
            override fun onEngineWillDestroy() { DeviceOtaService.active?.runtimeLost() }
        })
    }

    fun lifecycle(host: Activity, resumed: Boolean) {
        if (resumed || activity.get() === host) {
            activity = WeakReference(host)
            foreground = resumed
        }
    }

    fun engineLive(): Boolean = engine?.dartExecutor?.isExecutingDart == true

    fun notificationProblem(context: Context): String? {
        if (Build.VERSION.SDK_INT >= 31 && ContextCompat.checkSelfPermission(context,
                Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED)
            return "BLUETOOTH_PERMISSION_DENIED"
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context,
                Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            return "NOTIFICATION_PERMISSION_DENIED"
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled())
            return "NOTIFICATIONS_DISABLED"
        if (Build.VERSION.SDK_INT >= 26) {
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel(CHANNEL_ID,
                "Trace device firmware", NotificationManager.IMPORTANCE_LOW))
            if (manager.getNotificationChannel(CHANNEL_ID)?.importance == NotificationManager.IMPORTANCE_NONE)
                return "CHANNEL_DISABLED"
        }
        return null
    }

    private fun acquire(context: Context, key: DeviceOtaKey, snapshot: Map<*, *>,
        result: MethodChannel.Result) {
        val problem = notificationProblem(context) ?: when {
            !foreground || activity.get() == null -> "APP_NOT_FOREGROUND"
            !engineLive() -> "ENGINE_UNAVAILABLE"
            pending != null || DeviceOtaService.active?.hasTask() == true -> "OWNER_BUSY"
            else -> null
        }
        if (problem != null) {
            result.success(key.map() + mapOf("status" to "UNAVAILABLE", "reason" to problem))
            return
        }
        pending = result
        pendingKey = key
        initial = snapshot
        timeout = Runnable { unavailable(key, "ACQUIRE_TIMEOUT") }.also {
            handler.postDelayed(it, 4500)
        }
        try {
            ContextCompat.startForegroundService(context,
                key.put(Intent(context, DeviceOtaService::class.java)))
        } catch (_: Exception) {
            unavailable(key, "SERVICE_START_REJECTED")
        }
    }

    fun initial(key: DeviceOtaKey): Map<*, *>? = if (pendingKey == key) initial else null

    fun acquired(key: DeviceOtaKey) {
        if (pendingKey != key) {
            DeviceOtaService.active?.release(key)
            return
        }
        val result = pending
        clearPending()
        result?.success(key.map() + mapOf("status" to "ACQUIRED"))
    }

    fun unavailable(key: DeviceOtaKey, reason: String) {
        if (pendingKey == key) {
            val result = pending
            clearPending()
            result?.success(key.map() + mapOf("status" to "UNAVAILABLE", "reason" to reason))
        }
        DeviceOtaService.active?.release(key)
    }

    private fun clearPending() {
        timeout?.let { handler.removeCallbacks(it) }
        timeout = null
        pending = null
        pendingKey = null
        initial = null
    }

    fun probe(key: DeviceOtaKey, done: (Boolean) -> Unit) {
        if (!engineLive()) { done(false); return }
        var settled = false
        val deadline = Runnable { if (!settled) { settled = true; done(false) } }
        handler.postDelayed(deadline, 3000)
        fun settle(ok: Boolean) {
            if (settled) return
            settled = true
            handler.removeCallbacks(deadline)
            done(ok)
        }
        channel?.invokeMethod("probe", key.map(), object : MethodChannel.Result {
            override fun success(value: Any?) {
                val m = value as? Map<*, *>
                settle(DeviceOtaKey.from(m) == key && m?.get("ownerLive") == true)
            }
            override fun error(code: String, message: String?, details: Any?) { settle(false) }
            override fun notImplemented() { settle(false) }
        }) ?: settle(false)
    }

    fun event(method: String, key: DeviceOtaKey) { channel?.invokeMethod(method, key.map()) }

    fun consumeOpen(intent: Intent?): Boolean {
        if (intent?.action != OPEN) return false
        val key = DeviceOtaKey.from(intent)
        if (key != null && DeviceOtaService.active?.owns(key) == true) event("open", key)
        // A stale/recreated-process notification never restores cached progress.
        return true
    }
}
