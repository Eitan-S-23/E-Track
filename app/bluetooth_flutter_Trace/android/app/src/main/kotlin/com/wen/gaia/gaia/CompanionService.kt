package com.wen.gaia.gaia

import android.app.PendingIntent
import android.app.Service
import android.app.job.JobParameters
import android.app.job.JobService
import android.companion.CompanionDeviceService
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import java.util.UUID

class CompanionService : Service() {
    companion object {
        const val NOTIFICATION_ID = 2410
        var active: CompanionService? = null
            private set

        fun start(context: Context, reason: String): Boolean {
            if (!CompanionBridge.enabled(context)) return false
            val problem = CompanionBridge.problem(context)
            if (problem != null) {
                CompanionBridge.preferences(context).edit().putString("lastResult", problem).apply()
                return false
            }
            return try {
                ContextCompat.startForegroundService(context, Intent(context, CompanionService::class.java)
                    .putExtra("reason", reason))
                true
            } catch (_: Exception) {
                CompanionBridge.preferences(context).edit().putString("lastResult", "BACKGROUND_START_REJECTED").apply()
                false
            }
        }
    }

    val runtimeId: String = UUID.randomUUID().toString()
    private val handler = Handler(Looper.getMainLooper())
    private var closed = false
    private var foregroundStarted = false
    private var runtimeAcknowledged = false
    private var lastProbe = 0L
    private var linkedToken: String? = null
    private var revision = ""
    private var reason = "recovery"
    private var dispatching = false
    private var wakeLock: PowerManager.WakeLock? = null
    private val startupDeadline = Runnable {
        if (!runtimeAcknowledged) stopCompanion("RUNTIME_START_TIMEOUT")
    }
    private val heartbeat = object : Runnable {
        override fun run() {
            if (closed) return
            if (CompanionBridge.problem(this@CompanionService) != null || !CompanionBridge.enabled(this@CompanionService)) {
                stopCompanion("PERMISSION_OR_ASSOCIATION_LOST"); return
            }
            var settled = false
            val deadline = Runnable { if (!settled) { settled = true; stopCompanion("RUNTIME_PROBE_TIMEOUT") } }
            handler.postDelayed(deadline, 5000)
            CompanionBridge.probe(runtimeId) { ok ->
                if (settled || closed) return@probe
                settled = true
                handler.removeCallbacks(deadline)
                if (!ok) stopCompanion("RUNTIME_LOST") else {
                    lastProbe = SystemClock.elapsedRealtime()
                    handler.postDelayed(this, 30000)
                }
            }
        }
    }

    override fun onCreate() { super.onCreate(); active = this }
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (closed) return START_NOT_STICKY
        if (!CompanionBridge.enabled(this) || CompanionBridge.problem(this) != null) {
            stopCompanion("START_PRECONDITION_FAILED"); return START_NOT_STICKY
        }
        reason = intent?.getStringExtra("reason") ?: "recovery"
        if (reason !in listOf("foreground", "manual", "periodic", "presence", "recovery")) {
            stopCompanion("INVALID_START_REASON"); return START_NOT_STICKY
        }
        revision = CompanionBridge.revision(this)
        try {
            val open = PendingIntent.getActivity(this, NOTIFICATION_ID,
                Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = NotificationCompat.Builder(this, CompanionBridge.NOTIFICATION_CHANNEL)
                .setSmallIcon(R.drawable.ic_stat_e_track).setContentTitle("E-Track companion")
                .setContentText("Device connection and firmware checks enabled")
                .setOngoing(true).setOnlyAlertOnce(true).setContentIntent(open).build()
            ServiceCompat.startForeground(this, NOTIFICATION_ID, notification,
                if (Build.VERSION.SDK_INT >= 29) ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE else 0)
            foregroundStarted = true
            if (wakeLock == null) wakeLock = getSystemService(PowerManager::class.java)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ETrack:companion-start").apply { setReferenceCounted(false) }
            wakeLock?.acquire(120000)
            CompanionBridge.ensureEngine(this)
            handler.removeCallbacks(startupDeadline)
            handler.postDelayed(startupDeadline, 20000)
            dispatch()
        } catch (_: Exception) { stopCompanion("FOREGROUND_RUNTIME_FAILED") }
        return START_NOT_STICKY
    }

    fun dispatch() {
        if (closed || !foregroundStarted || dispatching) return
        val target = CompanionBridge.address(this) ?: return
        dispatching = true
        CompanionBridge.dispatch(mapOf("runtimeId" to runtimeId, "revision" to revision,
            "address" to target, "reason" to reason,
            "checkPending" to CompanionBridge.preferences(this).getBoolean("checkPending", false))) { ok ->
            dispatching = false
            if (closed || !ok) return@dispatch
            runtimeAcknowledged = true
            lastProbe = SystemClock.elapsedRealtime()
            handler.removeCallbacks(startupDeadline)
            handler.removeCallbacks(heartbeat)
            handler.postDelayed(heartbeat, 30000)
        }
    }

    fun healthy(): Boolean = !closed && foregroundStarted && runtimeAcknowledged &&
        DeviceOtaBridge.engineLive() && SystemClock.elapsedRealtime() - lastProbe < 60000 &&
        revision == CompanionBridge.revision(this)

    fun ownsDevice(key: DeviceOtaKey, requestedRuntime: String?): Boolean =
        requestedRuntime == runtimeId && healthy() && linkedToken == key.deviceToken &&
            CompanionBridge.enabled(this) && CompanionBridge.problem(this) == null &&
            CompanionBridge.gattConnected(this)

    fun state(value: Map<*, *>?): Boolean {
        if (closed || value?.get("runtimeId") != runtimeId || value["revision"] != revision) return false
        val status = value["status"] as? String ?: return false
        if (!Regex("[A-Z_]{1,64}").matches(status)) return false
        val connected = value["connected"] == true
        val target = CompanionBridge.address(this) ?: return false
        if (connected && (value["deviceToken"] != CompanionBridge.deviceToken(target) || !CompanionBridge.gattConnected(this))) return false
        linkedToken = if (connected) CompanionBridge.deviceToken(target) else null
        val prefs = CompanionBridge.preferences(this)
        prefs.edit().putString("lastResult", status).apply()
        if (value["checkFinished"] == true) prefs.edit().putBoolean("checkPending", false).apply()
        if (connected) {
            prefs.edit().putInt("failures", 0).putLong("nextAttempt", 0).apply()
            if (value["busy"] != true && wakeLock?.isHeld == true) wakeLock?.release()
        } else if (value["busy"] != true && DeviceOtaService.active?.hasTask() != true) {
            val failures = (prefs.getInt("failures", 0) + 1).coerceAtMost(6)
            val delay = (60000L * (1L shl failures)).coerceAtMost(3600000L)
            prefs.edit().putInt("failures", failures).putLong("nextAttempt", System.currentTimeMillis() + delay).apply()
            stopCompanion(status)
        }
        return true
    }

    fun stopCompanion(reason: String) {
        if (closed) return
        closed = true
        linkedToken = null
        handler.removeCallbacksAndMessages(null)
        if (wakeLock?.isHeld == true) wakeLock?.release()
        CompanionBridge.preferences(this).edit().putString("lastResult", reason).apply()
        CompanionBridge.runtimeLost(runtimeId)
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        stopCompanion("SERVICE_STOPPED")
        if (active === this) active = null
        super.onDestroy()
    }
}

class CompanionJobService : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        if (!CompanionBridge.enabled(this)) return false
        val prefs = CompanionBridge.preferences(this)
        val check = params.jobId == CompanionBridge.CHECK_JOB
        if (check) prefs.edit().putBoolean("checkPending", true).apply()
        if (!check && CompanionService.active?.healthy() == true) return false
        if (System.currentTimeMillis() < prefs.getLong("nextAttempt", 0)) return false
        // The short system job hands off to an acknowledged connectedDevice owner.
        // A start request is deliberately not recorded as a completed firmware check.
        CompanionService.start(this, if (check) "periodic" else "recovery")
        return false
    }
    override fun onStopJob(params: JobParameters): Boolean = false
}

class CompanionBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            try { CompanionBridge.restore(context) }
            catch (_: Exception) { CompanionBridge.preferences(context).edit().putString("lastResult", "BOOT_RESTORE_FAILED").apply() }
        }
    }
}

@Suppress("DEPRECATION")
class TrackCompanionDeviceService : CompanionDeviceService() {
    override fun onDeviceAppeared(address: String) {
        if (address.equals(CompanionBridge.address(this), true)) CompanionService.start(this, "presence")
    }
    override fun onDeviceDisappeared(address: String) {
        // BLE/OTA observes the actual link. A radio presence hint must not abort apply.
    }
}
