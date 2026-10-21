package com.wen.gaia.gaia

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

internal interface DeviceOtaRuntime {
    fun initial(key: DeviceOtaKey): Map<*, *>?
    fun problem(context: android.content.Context): String?
    fun live(): Boolean
    fun probe(key: DeviceOtaKey, done: (Boolean) -> Unit)
    fun acquired(key: DeviceOtaKey)
    fun unavailable(key: DeviceOtaKey, reason: String)
    fun event(method: String, key: DeviceOtaKey)
}

internal object AndroidDeviceOtaRuntime : DeviceOtaRuntime {
    override fun initial(key: DeviceOtaKey) = DeviceOtaBridge.initial(key)
    override fun problem(context: android.content.Context) = DeviceOtaBridge.notificationProblem(context)
    override fun live() = DeviceOtaBridge.engineLive()
    override fun probe(key: DeviceOtaKey, done: (Boolean) -> Unit) = DeviceOtaBridge.probe(key, done)
    override fun acquired(key: DeviceOtaKey) = DeviceOtaBridge.acquired(key)
    override fun unavailable(key: DeviceOtaKey, reason: String) = DeviceOtaBridge.unavailable(key, reason)
    override fun event(method: String, key: DeviceOtaKey) = DeviceOtaBridge.event(method, key)
}

class DeviceOtaService : Service() {
    internal var runtime: DeviceOtaRuntime = AndroidDeviceOtaRuntime
    private val handler = Handler(Looper.getMainLooper())
    private var key: DeviceOtaKey? = null
    private var snapshot: Map<*, *>? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var acquired = false
    private var startedAt = 0L
    private var lastProbe = 0L
    private var revision = -1L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        active = this
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val requested = DeviceOtaKey.from(intent)
        if (intent?.action == DeviceOtaBridge.CANCEL) {
            if (requested != null && owns(requested) && snapshot?.get("canCancel") == true)
                runtime.event("cancel", requested)
            if (key == null) stopSelf()
            return START_NOT_STICKY
        }
        val initial = requested?.let { runtime.initial(it) }
        if (requested == null || initial == null || key != null) {
            if (key == null) stopSelf()
            return START_NOT_STICKY
        }
        key = requested
        snapshot = initial
        try {
            check(runtime.problem(this) == null)
            val notification = notification(requested, initial)
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(DeviceOtaBridge.NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
            } else {
                startForeground(DeviceOtaBridge.NOTIFICATION_ID, notification)
            }
            startedAt = SystemClock.elapsedRealtime()
            wakeLock = (getSystemService(POWER_SERVICE) as PowerManager)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "trace:DeviceOta").apply {
                    setReferenceCounted(false)
                    acquire(LEASE_MS)
                }
            // Actual service + lock + SAME engine/BLE owner must all acknowledge.
            runtime.probe(requested) { ok ->
                if (key != requested) return@probe
                if (!ok) { fail("OWNER_PROBE_FAILED"); return@probe }
                acquired = true
                lastProbe = SystemClock.elapsedRealtime()
                runtime.acquired(requested)
                scheduleProbe(requested)
            }
        } catch (_: Exception) {
            fail("FOREGROUND_SERVICE_REJECTED")
        }
        return START_NOT_STICKY
    }

    fun hasTask(): Boolean = key != null

    fun owns(requested: DeviceOtaKey): Boolean = key == requested && acquired &&
        runtime.live() && runtime.problem(this) == null &&
        SystemClock.elapsedRealtime() - lastProbe <= 10000 &&
        SystemClock.elapsedRealtime() - startedAt < LEASE_MS && wakeLock?.isHeld == true

    private fun scheduleProbe(requested: DeviceOtaKey) {
        handler.postDelayed({
            if (key != requested) return@postDelayed
            if (!owns(requested)) { fail("LEASE_OR_PERMISSION_LOST"); return@postDelayed }
            runtime.probe(requested) { ok ->
                if (key != requested) return@probe
                if (!ok) { fail("OWNER_HEARTBEAT_LOST"); return@probe }
                lastProbe = SystemClock.elapsedRealtime()
                scheduleProbe(requested)
            }
        }, 5000)
    }

    fun publish(requested: DeviceOtaKey, value: Map<*, *>): Boolean {
        if (!owns(requested)) return false
        val next = (value["revision"] as? Number)?.toLong() ?: return false
        if (next <= revision) return true
        return try {
            val notification = notification(requested, value)
            NotificationManagerCompat.from(this).notify(DeviceOtaBridge.NOTIFICATION_ID, notification)
            snapshot = value
            revision = next
            true
        } catch (_: Exception) {
            fail("NOTIFICATION_UPDATE_FAILED")
            false
        }
    }

    private fun notification(requested: DeviceOtaKey, value: Map<*, *>): Notification {
        check(DeviceOtaKey.from(value) == requested)
        val phase = value["phase"] as? String ?: error("phase missing")
        val label = value["label"] as? String ?: error("label missing")
        val total = (value["totalBytes"] as? Number)?.toLong() ?: 0
        val durable = (value["durableBytes"] as? Number)?.toLong() ?: 0
        val received = (value["receivedBytes"] as? Number)?.toLong() ?: 0
        require(total >= 0 && durable in 0..total && received in 0..total)
        require(phase != "completed" || value["targetVerified"] == true)
        val progress = when {
            total <= 0 -> -1
            phase == "transferring" -> (100L * durable / total).toInt()
            phase == "downloading" -> (100L * received / total).toInt()
            else -> -1
        }
        val open = requested.put(Intent(this, MainActivity::class.java).apply {
            action = DeviceOtaBridge.OPEN
            data = Uri.parse("trace-device-ota://task/${requested.taskId}/${requested.generation}/open")
            addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        })
        val builder = NotificationCompat.Builder(this, DeviceOtaBridge.CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Trace device OTA")
            .setContentText(if (progress >= 0) "$label: $progress%" else label)
            .setContentIntent(PendingIntent.getActivity(this, 2408, open,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .setOnlyAlertOnce(true).setOngoing(true)
            .setProgress(100, progress.coerceAtLeast(0), progress < 0)
        if (value["canCancel"] == true) {
            val cancel = requested.put(Intent(this, DeviceOtaService::class.java).apply {
                action = DeviceOtaBridge.CANCEL
                data = Uri.parse("trace-device-ota://task/${requested.taskId}/${requested.generation}/cancel")
            })
            builder.addAction(R.mipmap.ic_launcher, "Cancel device OTA",
                PendingIntent.getService(this, 2409, cancel,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        }
        return builder.build()
    }

    fun runtimeLost() { fail("ENGINE_LOST") }

    private fun fail(reason: String) {
        val old = key ?: return
        runtime.event("lost", old)
        runtime.unavailable(old, reason)
        release(old)
    }

    fun release(requested: DeviceOtaKey) {
        if (key != requested) return
        key = null
        acquired = false
        snapshot = null
        handler.removeCallbacksAndMessages(null)
        wakeLock?.takeIf { it.isHeld }?.release()
        wakeLock = null
        if (Build.VERSION.SDK_INT >= 24) stopForeground(STOP_FOREGROUND_REMOVE)
        else { @Suppress("DEPRECATION") stopForeground(true) }
        stopSelf()
    }

    override fun onDestroy() {
        val old = key
        if (old != null) {
            runtime.event("lost", old)
            runtime.unavailable(old, "SERVICE_DESTROYED")
            release(old)
        }
        handler.removeCallbacksAndMessages(null)
        wakeLock?.takeIf { it.isHeld }?.release()
        wakeLock = null
        if (active === this) active = null
        super.onDestroy()
    }

    companion object {
        const val LEASE_MS = 60L * 60L * 1000L
        var active: DeviceOtaService? = null
            private set
    }
}
