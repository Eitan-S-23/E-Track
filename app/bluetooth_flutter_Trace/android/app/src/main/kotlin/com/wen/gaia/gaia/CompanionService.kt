package com.wen.gaia.gaia

import android.app.PendingIntent
import android.app.Service
import android.app.job.JobParameters
import android.app.job.JobService
import android.bluetooth.BluetoothAdapter
import android.companion.AssociationInfo
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
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.io.FileDescriptor
import java.io.PrintWriter
import java.util.UUID

internal interface CompanionExecution {
    fun problem(context: Context): String?
    fun initialize(context: Context)
    fun dispatch(payload: Map<String, Any>, done: (Boolean) -> Unit)
    fun probe(id: String, done: (Boolean) -> Unit)
    fun live(): Boolean
    fun connected(context: Context): Boolean
    fun lost(id: String)
}

private object AndroidCompanionExecution : CompanionExecution {
    override fun problem(context: Context) = CompanionBridge.problem(context)
    override fun initialize(context: Context) = CompanionBridge.ensureEngine(context)
    override fun dispatch(payload: Map<String, Any>, done: (Boolean) -> Unit) = CompanionBridge.dispatch(payload, done)
    override fun probe(id: String, done: (Boolean) -> Unit) = CompanionBridge.probe(id, done)
    override fun live() = DeviceOtaBridge.engineLive()
    override fun connected(context: Context) = CompanionBridge.gattConnected(context)
    override fun lost(id: String) = CompanionBridge.runtimeLost(id)
}

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
                CompanionDiagnostics.record(context, problem, trigger = reason)
                return false
            }
            return try {
                ContextCompat.startForegroundService(context, Intent(context, CompanionService::class.java)
                    .putExtra("reason", reason))
                true
            } catch (error: Exception) {
                CompanionBridge.preferences(context).edit().putString("lastResult", "BACKGROUND_START_REJECTED").apply()
                CompanionDiagnostics.record(context, "BACKGROUND_START_REJECTED", trigger = reason,
                    details = mapOf("stage" to "foreground_start", "errorType" to error.javaClass.simpleName,
                        "errorCode" to "BACKGROUND_START_REJECTED"))
                false
            }
        }
    }

    val runtimeId: String = UUID.randomUUID().toString()
    internal var execution: CompanionExecution = AndroidCompanionExecution
    private val handler = Handler(Looper.getMainLooper())
    private var closed = false
    private var foregroundStarted = false
    private var runtimeAcknowledged = false
    private var lastProbe = 0L
    private var linkedToken: String? = null
    private var revision = ""
    private var reason = "recovery"
    private var dispatching = false
    private var redispatch = false
    private var wakeLock: PowerManager.WakeLock? = null
    private var reconnectStartedAt: Long? = null
    private var reconnectAttempts = 0
    private var reconnectPending = false
    private var reconnectStatus = "DEVICE_OFFLINE"
    private var recoveryRetryAt: Long? = null
    private var recoveryProgressAt: Long? = null
    private var recoveryId: String? = null
    private var awaitingStateAt: Long? = null
    private var notificationStatus = "INITIALIZING"
    private var stateSequence = 0L
    private var networkManager: ConnectivityManager? = null
    private var networkResumeQueued = false
    private val networkResume = Runnable {
        networkResumeQueued = false
        if (!closed && notificationStatus in listOf("PACKAGE_PREPARATION_FAILED", "WAIT_UNMETERED_NETWORK", "NO_NETWORK")) {
            startRuntime("network")
        }
    }
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
            if (!capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) return
            handler.post {
                if (!closed && !networkResumeQueued && notificationStatus in listOf("PACKAGE_PREPARATION_FAILED", "WAIT_UNMETERED_NETWORK", "NO_NETWORK")) {
                    networkResumeQueued = true
                    handler.postDelayed(networkResume, 1000)
                }
            }
        }
    }
    private val reconnectWindowMs = 60000L
    private val reconnectDelays = longArrayOf(2000, 4000, 8000)
    private val creationRecovery = Runnable {
        // Some system cleaners recreate the Service without redelivering a start
        // Intent. An old foreground notification is not an initialized runtime.
        if (!closed && !foregroundStarted) startRuntime("recovery")
    }
    private val reconnect = Runnable {
        reconnectPending = false
        if (closed) return@Runnable
        if (!CompanionBridge.enabled(this) || execution.problem(this) != null ||
            revision != CompanionBridge.revision(this)) {
            stopCompanion("PERMISSION_OR_ASSOCIATION_LOST"); return@Runnable
        }
        if (!runtimeAcknowledged || !execution.live()) {
            stopCompanion("RUNTIME_LOST"); return@Runnable
        }
        if (linkedToken != null && execution.connected(this)) {
            resetReconnect(); return@Runnable
        }
        if (DeviceOtaService.active?.hasTask() == true) return@Runnable
        if (SystemClock.elapsedRealtime() - (reconnectStartedAt ?: 0) >= reconnectWindowMs) {
            backOffRecovery(reconnectStatus); return@Runnable
        }
        reason = "recovery"
        Log.i("ETrackCompanion", "Retrying device connection (${reconnectAttempts + 1}/4)")
        dispatch()
    }
    private val recoveryRetry = Runnable {
        if (closed || recoveryRetryAt == null) return@Runnable
        CompanionDiagnostics.record(this, "RECOVERY_TIMER_FIRED", runtimeId, "handler",
            details = mapOf("nextCheckAt" to recoveryRetryAt, "executedAt" to System.currentTimeMillis()))
        recoveryRetryAt = null
        startRuntime("recovery")
    }
    private val startupDeadline = Runnable {
        if (!runtimeAcknowledged) stopCompanion("RUNTIME_START_TIMEOUT")
    }
    private val connectionDeadline = Runnable {
        if (!closed && recoveryProgressAt != null && DeviceOtaService.active?.hasTask() != true) {
            stopCompanion("CONNECTION_PROGRESS_TIMEOUT")
        }
    }
    private val heartbeat = object : Runnable {
        override fun run() {
            if (closed) return
            if (execution.problem(this@CompanionService) != null || !CompanionBridge.enabled(this@CompanionService) ||
                revision != CompanionBridge.revision(this@CompanionService)) {
                stopCompanion("PERMISSION_OR_ASSOCIATION_LOST"); return
            }
            if (!runtimeAcknowledged && waitingForRecovery()) {
                handler.postDelayed(this, 30000)
                return
            }
            var settled = false
            val deadline = Runnable { if (!settled) { settled = true; stopCompanion("RUNTIME_PROBE_TIMEOUT") } }
            handler.postDelayed(deadline, 5000)
            execution.probe(runtimeId) { ok ->
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

    override fun onCreate() {
        super.onCreate()
        active = this
        CompanionDiagnostics.record(this, "SERVICE_CREATED", runtimeId)
        if (Build.VERSION.SDK_INT >= 24) {
            try {
                val manager = getSystemService(ConnectivityManager::class.java)
                manager.registerDefaultNetworkCallback(networkCallback)
                networkManager = manager
            } catch (_: Exception) { /* Periodic recovery remains available. */ }
        }
        handler.post(creationRecovery)
    }
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        handler.removeCallbacks(creationRecovery)
        startRuntime(intent?.getStringExtra("reason") ?: "recovery")
        return if (closed) START_NOT_STICKY else START_STICKY
    }

    private fun startRuntime(requestedReason: String) {
        if (closed) return
        if (!CompanionBridge.enabled(this) || execution.problem(this) != null) {
            stopCompanion("START_PRECONDITION_FAILED"); return
        }
        if (requestedReason !in listOf("foreground", "manual", "periodic", "presence", "recovery", "network")) {
            stopCompanion("INVALID_START_REASON"); return
        }
        if (foregroundStarted && revision != CompanionBridge.revision(this)) {
            stopCompanion("PERMISSION_OR_ASSOCIATION_LOST"); return
        }
        revision = CompanionBridge.revision(this)
        try {
            CompanionDiagnostics.record(this, "SERVICE_START", runtimeId, requestedReason, reconnectAttempts + 1)
            ServiceCompat.startForeground(this, NOTIFICATION_ID, notification(notificationStatus),
                if (Build.VERSION.SDK_INT >= 29) ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE else 0)
            foregroundStarted = true
            if (requestedReason in listOf("recovery", "presence") && recoveryRetryAt == null &&
                (DeviceOtaService.active?.hasTask() == true || (linkedToken != null && execution.connected(this)) ||
                    dispatching || awaitingStateAt?.let { SystemClock.elapsedRealtime() - it < 30000 } == true ||
                    recoveryProgressAt?.let { SystemClock.elapsedRealtime() - it < 30000 } == true)) {
                CompanionDiagnostics.record(this, "RECOVERY_WAKE_COALESCED", runtimeId, requestedReason,
                    details = mapOf("reason" to "owner_already_active"))
                return
            }
            reason = requestedReason
            val next = CompanionBridge.preferences(this).getLong("nextAttempt", 0)
            if (requestedReason !in listOf("foreground", "manual", "presence") && CompanionRecoveryWake.remainingMs(this) > 0) {
                waitForRecovery(next, "recovery_backoff")
                return
            }
            handler.removeCallbacks(recoveryRetry)
            recoveryRetryAt = null
            check(CompanionRecoveryWake.cancel(this, clearBackoff = true)) { "RECOVERY_FENCE_NOT_PERSISTED" }
            // A fresh wake supersedes a pending timer, without extending its retry budget.
            handler.removeCallbacks(reconnect)
            reconnectPending = false
            if (wakeLock == null) wakeLock = getSystemService(PowerManager::class.java)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ETrack:companion-start").apply { setReferenceCounted(false) }
            wakeLock?.acquire(120000)
            execution.initialize(this)
            handler.removeCallbacks(startupDeadline)
            handler.postDelayed(startupDeadline, 20000)
            dispatch()
        } catch (error: Exception) {
            CompanionDiagnostics.record(this, "FOREGROUND_RUNTIME_FAILED", runtimeId, requestedReason,
                details = mapOf("stage" to "runtime_start", "errorType" to error.javaClass.simpleName))
            stopCompanion("FOREGROUND_RUNTIME_FAILED")
        }
    }

    public override fun dump(fd: FileDescriptor, writer: PrintWriter, args: Array<out String>?) {
        if (args?.contains("--journal") == true) {
            val position = args.indexOf("--before")
            val cursor = if (position >= 0) args.getOrNull(position + 1)?.toLongOrNull() else null
            val done = java.util.concurrent.CountDownLatch(1)
            var page: Result<Map<String, Any?>>? = null
            CompanionJournal.query(this, mapOf("limit" to 200, "beforeSeq" to cursor)) { page = it; done.countDown() }
            if (done.await(5, java.util.concurrent.TimeUnit.SECONDS)) {
                page!!.fold({ writer.println(JSONObject(it).toString()) },
                    { writer.println("{\"error\":\"JOURNAL_READ_FAILED\"}") })
            } else writer.println("{\"error\":\"JOURNAL_READ_TIMEOUT\"}")
            return
        }
        // Readable through Android's existing dumpsys access, without opening UI
        // (which itself wakes the runtime and can conceal a background failure).
        writer.println(JSONObject(mapOf(
            "runtime" to runtimeId.take(8), "closed" to closed,
            "foregroundStarted" to foregroundStarted, "runtimeAcknowledged" to runtimeAcknowledged,
            "engineLive" to runCatching { execution.live() }.getOrDefault(false),
            "gattConnected" to runCatching { execution.connected(this) }.getOrDefault(false),
            "linkAcknowledged" to (linkedToken != null), "status" to notificationStatus,
            "recoveryWaiting" to waitingForRecovery(), "nextRecoveryAt" to recoveryRetryAt,
            "recoveryWake" to CompanionRecoveryWake.snapshot(this),
            "diagnostics" to CompanionDiagnostics.snapshot(this)
        )).toString())
    }

    fun dispatch() {
        if (closed || !foregroundStarted || recoveryRetryAt != null) return
        if (dispatching) { redispatch = true; return }
        val target = CompanionBridge.address(this) ?: return
        dispatching = true
        awaitingStateAt = SystemClock.elapsedRealtime()
        execution.dispatch(mapOf("runtimeId" to runtimeId, "revision" to revision,
            "address" to target, "reason" to reason,
            "checkPending" to CompanionBridge.preferences(this).getBoolean("checkPending", false))) { ok ->
            dispatching = false
            if (closed || !ok) return@dispatch
            runtimeAcknowledged = true
            lastProbe = SystemClock.elapsedRealtime()
            handler.removeCallbacks(startupDeadline)
            handler.removeCallbacks(heartbeat)
            handler.postDelayed(heartbeat, 30000)
            if (redispatch) { redispatch = false; dispatch() }
        }
    }

    fun healthy(): Boolean = !closed && foregroundStarted && runtimeAcknowledged &&
        execution.live() && SystemClock.elapsedRealtime() - lastProbe < 60000 &&
        revision == CompanionBridge.revision(this)

    // Runtime liveness still serves OTA ownership. Recovery additionally requires
    // a real link or bounded progress; a responsive but idle engine is not enough.
    fun recoveryHealthy(): Boolean = healthy() && (DeviceOtaService.active?.hasTask() == true ||
        (linkedToken != null && execution.connected(this)) ||
        (recoveryProgressAt?.let { SystemClock.elapsedRealtime() - it < 30000 } == true) ||
        (reconnectPending && reconnectStartedAt?.let { SystemClock.elapsedRealtime() - it < reconnectWindowMs } == true))

    fun linkReady(): Boolean = healthy() && linkedToken != null && execution.connected(this)

    fun waitingForRecovery(): Boolean = !closed && foregroundStarted && recoveryRetryAt != null &&
        CompanionBridge.enabled(this) && revision == CompanionBridge.revision(this) && execution.problem(this) == null

    private fun notification(status: String): android.app.Notification {
        val open = PendingIntent.getActivity(this, NOTIFICATION_ID,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val text = when (status) {
            "INITIALIZING" -> "\u6b63\u5728\u542f\u52a8\u8bbe\u5907\u8fde\u63a5"
            "CONNECTING" -> "\u6b63\u5728\u8fde\u63a5\u8bbe\u5907\u84dd\u7259"
            "DISCOVERING", "SUBSCRIBING", "VERIFYING_DEVICE", "NEGOTIATING_CONTROL" -> "\u6b63\u5728\u786e\u8ba4\u8bbe\u5907\u8fde\u63a5"
            "RECOVERY_CLEANUP" -> "\u6b63\u5728\u6e05\u7406\u65e7\u8fde\u63a5"
            "DEVICE_OFFLINE", "DEVICE_IDENTITY_UNAVAILABLE", "CONNECTION_TIMEOUT", "CONNECTION_FAILED" -> "\u8bbe\u5907\u672a\u8fde\u63a5\uff0c\u7a0d\u540e\u91cd\u8bd5"
            "RECOVERY_BACKOFF" -> "\u8bbe\u5907\u672a\u8fde\u63a5\uff0c\u7b49\u5f85\u4e0b\u6b21\u91cd\u8bd5"
            "CHECKING" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u6b63\u5728\u68c0\u67e5\u56fa\u4ef6\u66f4\u65b0"
            "NO_UPDATE" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u56fa\u4ef6\u5df2\u662f\u6700\u65b0\u7248\u672c"
            "READY_AWAITING_DEVICE_CHOICE", "READY_OPEN_APP" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u6709\u53ef\u7528\u56fa\u4ef6\u66f4\u65b0"
            "WAIT_UNMETERED_NETWORK", "NO_NETWORK" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u7b49\u5f85\u7f51\u7edc\u6062\u590d"
            "LOGIN_REQUIRED" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u767b\u5f55\u540e\u53ef\u68c0\u67e5\u56fa\u4ef6\u66f4\u65b0"
            "TARGET_IDENTITY_VERIFIED" -> "\u56fa\u4ef6\u66f4\u65b0\u6210\u529f\uff0c\u5df2\u786e\u8ba4\u8bbe\u5907\u7248\u672c"
            "CHECK_FAILED", "PACKAGE_PREPARATION_FAILED" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u66f4\u65b0\u68c0\u67e5\u6682\u4e0d\u53ef\u7528"
            "DEVICE_CONTROL_UNSUPPORTED" -> "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u8bf7\u5728 App \u4e2d\u68c0\u67e5\u66f4\u65b0"
            else -> if (linkedToken != null) "\u8bbe\u5907\u5df2\u8fde\u63a5\uff0c\u540e\u53f0\u670d\u52a1\u8fd0\u884c\u4e2d" else "\u8bbe\u5907\u8fde\u63a5\u670d\u52a1\u8fd0\u884c\u4e2d"
        }
        return NotificationCompat.Builder(this, CompanionBridge.NOTIFICATION_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_e_track).setContentTitle("E-Track \u8bbe\u5907\u8fde\u63a5")
            .setContentText(text).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(open).build()
    }

    fun ownsDevice(key: DeviceOtaKey, requestedRuntime: String?): Boolean =
        requestedRuntime == runtimeId && healthy() && linkedToken == key.deviceToken &&
            CompanionBridge.enabled(this) && execution.problem(this) == null &&
            execution.connected(this)

    fun state(value: Map<*, *>?): Boolean {
        if (closed || value?.get("runtimeId") != runtimeId || value["revision"] != revision) return false
        val status = value["status"] as? String ?: return false
        if (!Regex("[A-Z_]{1,64}").matches(status)) return false
        if (recoveryRetryAt != null && value["connected"] != true) return false
        val sequence = (value["stateSequence"] as? Number)?.toLong()
        if (sequence != null && sequence <= stateSequence) return false
        val connected = value["connected"] == true
        val target = CompanionBridge.address(this) ?: return false
        if (connected && (value["deviceToken"] != CompanionBridge.deviceToken(target) || !execution.connected(this))) return false
        awaitingStateAt = null
        val recoveryBusy = value["recoveryBusy"] == true
        val nextRecovery = value["recoveryId"] as? String
        if (recoveryBusy) {
            if (nextRecovery == null || !Regex("[0-9a-f]{32}").matches(nextRecovery)) return false
            if (recoveryId != nextRecovery) {
                recoveryId = nextRecovery
                recoveryProgressAt = SystemClock.elapsedRealtime()
                handler.removeCallbacks(connectionDeadline)
                handler.postDelayed(connectionDeadline, 30000)
            }
        } else {
            recoveryId = null
            recoveryProgressAt = null
            handler.removeCallbacks(connectionDeadline)
        }
        if (sequence != null) stateSequence = sequence
        linkedToken = if (connected) CompanionBridge.deviceToken(target) else null
        val prefs = CompanionBridge.preferences(this)
        prefs.edit().putString("lastResult", status).apply()
        CompanionDiagnostics.record(this, status, runtimeId, reason, reconnectAttempts + 1, value)
        val presentation = if (!connected && status in listOf("TARGET_IDENTITY_VERIFIED", "UPGRADE_FAILED")) "CONNECTING" else status
        if (notificationStatus != presentation) {
            notificationStatus = presentation
            try { NotificationManagerCompat.from(this).notify(NOTIFICATION_ID, notification(presentation)) }
            catch (_: Exception) { /* Ownership checks independently detect a disabled channel. */ }
        }
        if (status == "CHECKING") prefs.edit().putBoolean("checkPending", true).apply()
        if (value["checkFinished"] == true) prefs.edit().putBoolean("checkPending", false).apply()
        if (connected && !recoveryBusy) {
            resetReconnect()
            CompanionRecoveryWake.cancel(this, clearBackoff = true)
            prefs.edit().putInt("failures", 0).putLong("nextAttempt", 0).apply()
            if (value["busy"] != true && wakeLock?.isHeld == true) wakeLock?.release()
        } else if (!connected && status in listOf("TARGET_IDENTITY_VERIFIED", "UPGRADE_FAILED")) {
            // OTA may close its verification GATT before handing control back.
            // This is a bounded reconnect, not a failed idle service to stop.
            if (!scheduleReconnect("CONNECTION_FAILED")) backOffRecovery("POST_OTA_RECOVERY_EXHAUSTED")
        } else if (recoveryBusy || (status == "CONNECTING" && value["busy"] == true)) {
            handler.removeCallbacks(reconnect)
            reconnectPending = false
            beginReconnectWindow()
        } else if (value["busy"] != true && DeviceOtaService.active?.hasTask() != true) {
            if (!scheduleReconnect(status)) backOffRecovery(status)
        }
        return true
    }

    private fun scheduleReconnect(status: String): Boolean {
        if (status !in listOf("DEVICE_OFFLINE", "DEVICE_IDENTITY_UNAVAILABLE", "CONNECTION_TIMEOUT", "CONNECTION_FAILED") ||
            !CompanionBridge.enabled(this) || execution.problem(this) != null ||
            revision != CompanionBridge.revision(this)) return false
        if (reconnectPending) return true
        val now = SystemClock.elapsedRealtime()
        val started = beginReconnectWindow()
        val delay = reconnectDelays.getOrNull(reconnectAttempts) ?: return false
        if (now - started + delay >= reconnectWindowMs) return false
        reconnectAttempts++
        reconnectStatus = status
        reconnectPending = true
        // Keep the acknowledged engine/radio owner; do not wait for the 15-minute job.
        handler.postDelayed(reconnect, delay)
        return true
    }

    private fun beginReconnectWindow(): Long {
        reconnectStartedAt?.let { return it }
        val started = SystemClock.elapsedRealtime()
        reconnectStartedAt = started
        // An established connection released the startup lock; later recovery needs its own bound.
        if (wakeLock?.isHeld != true) wakeLock?.acquire(reconnectWindowMs)
        return started
    }

    private fun resetReconnect() {
        handler.removeCallbacks(reconnect)
        handler.removeCallbacks(recoveryRetry)
        recoveryRetryAt = null
        reconnectPending = false
        reconnectStartedAt = null
        reconnectAttempts = 0
        awaitingStateAt = null
    }

    private fun backOffRecovery(status: String) {
        val prefs = CompanionBridge.preferences(this)
        val failures = (prefs.getInt("failures", 0) + 1).coerceAtMost(6)
        val delay = (60000L * (1L shl failures)).coerceAtMost(3600000L)
        val next = System.currentTimeMillis() + delay
        prefs.edit().putInt("failures", failures).putLong("nextAttempt", next).apply()
        if (status in listOf("DEVICE_OFFLINE", "DEVICE_IDENTITY_UNAVAILABLE", "CONNECTION_TIMEOUT", "CONNECTION_FAILED") &&
            runtimeAcknowledged && execution.live()) {
            waitForRecovery(next, status)
        } else stopCompanion(status)
    }

    private fun waitForRecovery(next: Long, status: String) {
        resetReconnect()
        recoveryId = null
        recoveryProgressAt = null
        handler.removeCallbacks(connectionDeadline)
        handler.removeCallbacks(startupDeadline)
        recoveryRetryAt = next
        notificationStatus = "RECOVERY_BACKOFF"
        val prefs = CompanionBridge.preferences(this)
        prefs.edit().putString("lastResult", notificationStatus).apply()
        CompanionDiagnostics.record(this, notificationStatus, runtimeId, "recovery",
            details = mapOf("reason" to status, "nextCheckAt" to next))
        try { NotificationManagerCompat.from(this).notify(NOTIFICATION_ID, notification(notificationStatus)) }
        catch (_: Exception) { /* The guarded heartbeat checks notification permission. */ }
        if (wakeLock?.isHeld == true) wakeLock?.release()
        // The Handler is the awake fast path. Unlike it, the alarm can wake a
        // sleeping CPU or recreate a reclaimed process for this deadline.
        CompanionRecoveryWake.schedule(this, next)
        handler.postDelayed(recoveryRetry, CompanionRecoveryWake.remainingMs(this))
        if (!runtimeAcknowledged) {
            handler.removeCallbacks(heartbeat)
            handler.postDelayed(heartbeat, 30000)
        }
    }

    fun stopCompanion(reason: String) {
        if (closed) return
        closed = true
        linkedToken = null
        if (!CompanionBridge.enabled(this) || (revision.isNotEmpty() && revision != CompanionBridge.revision(this)) ||
            reason in listOf("USER_DISABLED", "PERMISSION_OR_ASSOCIATION_LOST", "START_PRECONDITION_FAILED")) {
            CompanionRecoveryWake.cancel(this, clearBackoff = true)
        }
        resetReconnect()
        handler.removeCallbacksAndMessages(null)
        if (wakeLock?.isHeld == true) wakeLock?.release()
        CompanionBridge.preferences(this).edit().putString("lastResult", reason).apply()
        CompanionDiagnostics.record(this, "SERVICE_STOP_REQUESTED", runtimeId, this.reason,
            details = mapOf("reason" to reason))
        execution.lost(runtimeId)
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        try { networkManager?.unregisterNetworkCallback(networkCallback) } catch (_: Exception) { }
        networkManager = null
        CompanionDiagnostics.record(this, "SERVICE_DESTROYED", runtimeId)
        stopCompanion("SERVICE_STOPPED")
        if (active === this) active = null
        super.onDestroy()
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        CompanionDiagnostics.record(this, "TASK_REMOVED", runtimeId,
            details = mapOf("termination" to "task_removed_not_process_death"))
        super.onTaskRemoved(rootIntent)
    }
}

class CompanionJobService : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        if (!CompanionBridge.enabled(this)) {
            CompanionDiagnostics.record(this, "CHECK_NOT_EXECUTED", details = mapOf("reason" to "disabled"))
            return false
        }
        if (params.jobId == CompanionBridge.STARTUP_JOB) {
            CompanionBridge.recoverStartup(this, params.extras.getLong(CompanionBridge.STARTUP_DEADLINE, 0))
            return false
        }
        val prefs = CompanionBridge.preferences(this)
        val check = params.jobId == CompanionBridge.CHECK_JOB
        if (check) prefs.edit().putBoolean("checkPending", true).apply()
        if (!check && !prefs.getBoolean("checkPending", false) && CompanionService.active?.recoveryHealthy() == true) return false
        if (CompanionRecoveryWake.remainingMs(this) > 0) {
            CompanionRecoveryWake.restore(this)
            CompanionDiagnostics.record(this, "CHECK_NOT_EXECUTED", details = mapOf("reason" to "recovery_backoff",
                "nextCheckAt" to prefs.getLong("nextAttempt", 0)))
            return false
        }
        // The short system job hands off to an acknowledged connectedDevice owner.
        // A start request is deliberately not recorded as a completed firmware check.
        val trigger = if (check) "periodic" else "recovery"
        CompanionDiagnostics.record(this, "RECOVERY_JOB_DISPATCHED", trigger = trigger)
        CompanionService.start(this, trigger)
        return false
    }
    override fun onStopJob(params: JobParameters): Boolean = false
}

class CompanionBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val radioReady = intent.action == BluetoothAdapter.ACTION_STATE_CHANGED &&
            intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR) == BluetoothAdapter.STATE_ON
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED || radioReady) {
            Log.i("ETrackCompanion", "Restoring companion after ${intent.action}")
            val trigger = if (radioReady) "bluetooth" else if (intent.action == Intent.ACTION_BOOT_COMPLETED) "boot" else "package"
            CompanionDiagnostics.record(context, "SYSTEM_RECOVERY_TRIGGERED", trigger = trigger)
            try { CompanionBridge.restoreAfterSystemRestart(context) }
            catch (error: Exception) {
                CompanionBridge.preferences(context).edit().putString("lastResult", "BOOT_RESTORE_FAILED").apply()
                CompanionDiagnostics.record(context, "BOOT_RESTORE_FAILED", trigger = trigger,
                    details = mapOf("stage" to "restore", "errorType" to error.javaClass.simpleName))
            }
        }
    }
}

@Suppress("DEPRECATION")
class TrackCompanionDeviceService : CompanionDeviceService() {
    override fun onCreate() {
        super.onCreate()
        CompanionDiagnostics.record(this, "PRESENCE_SERVICE_CREATED", trigger = "presence")
    }
    override fun onDestroy() {
        CompanionDiagnostics.record(this, "PRESENCE_SERVICE_DESTROYED", trigger = "presence")
        super.onDestroy()
    }
    override fun onDeviceAppeared(address: String) = appeared(address)
    override fun onDeviceAppeared(associationInfo: AssociationInfo) = appeared(associationInfo.deviceMacAddress?.toString())
    private fun appeared(address: String?) {
        if (address == null || !address.equals(CompanionBridge.address(this), true)) return
        CompanionDiagnostics.record(this, "PRESENCE_APPEARED", trigger = "presence")
        CompanionService.start(this, "presence")
    }
    override fun onDeviceDisappeared(address: String) {
        if (address.equals(CompanionBridge.address(this), true))
            CompanionDiagnostics.record(this, "PRESENCE_DISAPPEARED", trigger = "presence")
        // BLE/OTA observes the actual link. A radio presence hint must not abort apply.
    }
    override fun onDeviceDisappeared(associationInfo: AssociationInfo) {
        associationInfo.deviceMacAddress?.toString()?.let { onDeviceDisappeared(it) }
    }
}
