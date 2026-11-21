package com.wen.gaia.gaia

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Process
import android.os.SystemClock
import android.provider.Settings
import java.util.UUID

/** UI visibility is observed, never inferred from a service wake reason. */
internal object CompanionLifecycle {
    private val processId = UUID.randomUUID().toString().replace("-", "")
    private var observed = false
    private var resumed = false
    private var everResumed = false
    private var uiState = "unknown"
    private var serviceAt: Long? = null
    private var connectAt: Long? = null
    private var recoveryId: String? = null
    private fun prefs(c: Context) = c.getSharedPreferences("companion_lifecycle_v1", Context.MODE_PRIVATE)
    private fun boot(c: Context) = Settings.Global.getInt(c.contentResolver, Settings.Global.BOOT_COUNT, -1)
    private fun since(now: Long, before: Long?) = before?.takeIf { now >= it }?.let { now - it }

    fun created(c: Context, intent: Intent?) {
        val source = if (intent?.action == Intent.ACTION_MAIN && intent.hasCategory(Intent.CATEGORY_LAUNCHER) &&
            intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY == 0) "user_open"
            else if (intent != null && intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY != 0) "task_history" else "unknown"
        CompanionDiagnostics.record(c, "UI_CREATED", details = mapOf("launchSource" to source))
    }

    fun ui(c: Context, state: String) {
        resumed = state == "resumed"
        uiState = state
        val source = if (resumed && everResumed) "existing_process_foreground" else "unknown"
        if (resumed) everResumed = true
        if (state == "stopped") prefs(c).edit().putLong("leftAt", System.currentTimeMillis())
            .putLong("leftUptime", SystemClock.elapsedRealtime()).putInt("boot", boot(c)).apply()
        CompanionDiagnostics.record(c, "UI_${state.uppercase()}", details = mapOf("launchSource" to source))
        if (state == "stopped" && CompanionService.active?.linkReady() == true)
            CompanionDiagnostics.record(c, "LINK_REUSED")
    }

    @Synchronized
    fun decorate(c: Context, state: String, details: Map<*, *>?): Map<String, Any?> {
        val now = SystemClock.elapsedRealtime()
        if (!observed) {
            observed = true
            CompanionJournal.record(c, "PROCESS_OBSERVED", null, null, 0,
                mapOf("processId" to processId, "elapsedMs" to (now - Process.getStartElapsedRealtime()).coerceAtLeast(0),
                    "launchSource" to if (state == "SERVICE_CREATED") "background_service" else details?.get("launchSource") ?: "unknown"))
            if (Build.VERSION.SDK_INT >= 30) runCatching {
                c.getSystemService(ActivityManager::class.java).getHistoricalProcessExitReasons(c.packageName, 0, 1).firstOrNull()?.let {
                    val cause = when (it.reason) {
                        ApplicationExitInfo.REASON_LOW_MEMORY -> "system_low_memory"
                        ApplicationExitInfo.REASON_USER_REQUESTED -> "user_requested_or_force_stop"
                        ApplicationExitInfo.REASON_CRASH, ApplicationExitInfo.REASON_CRASH_NATIVE -> "crash"
                        ApplicationExitInfo.REASON_ANR -> "anr"
                        else -> "unknown"
                    }
                    CompanionJournal.record(c, "PREVIOUS_PROCESS_EXIT", null, null, 0,
                        mapOf("termination" to cause, "executedAt" to it.timestamp, "processId" to processId))
                }
            }
        }
        val result = mutableMapOf<String, Any?>()
        details?.forEach { (key, value) -> if (key is String) result[key] = value }
        result["processId"] = processId
        result["uiState"] = uiState
        if (state == "SERVICE_CREATED") serviceAt = now
        val id = details?.get("recoveryId") as? String
        if (state == "CONNECTING" && (connectAt == null || id != recoveryId)) { connectAt = now; recoveryId = id }
        if (state == "CONTROL_READY" || state == "LINK_REUSED") {
            val p = prefs(c)
            val left = if (p.contains("leftUptime") && p.getInt("boot", -1) >= 0 && p.getInt("boot", -1) == boot(c)) p.getLong("leftUptime", 0) else null
            result["reconnection"] = if (state == "LINK_REUSED") "not_occurred" else "occurred"
            result["startupWaitMs"] = serviceAt?.let { since(it, left) }
            result["connectionMs"] = if (state == "LINK_REUSED") null else since(now, connectAt)
            result["closeToReadyMs"] = if (resumed) null else since(now, left)
            connectAt = null; recoveryId = null
        }
        return result
    }
}
