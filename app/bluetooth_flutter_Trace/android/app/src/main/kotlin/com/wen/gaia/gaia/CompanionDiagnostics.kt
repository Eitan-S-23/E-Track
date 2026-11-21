package com.wen.gaia.gaia

import android.content.Context
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Bounded local history. Never store addresses, tokens, URLs or exception messages. */
internal object CompanionDiagnostics {
    private const val LIMIT = 80
    private fun prefs(context: Context) = context.getSharedPreferences("companion_diagnostics_v1", Context.MODE_PRIVATE)
    private fun safe(value: Any?) = (value as? String)?.takeIf { Regex("[A-Za-z0-9_]{1,64}").matches(it) }

    @Synchronized
    fun record(context: Context, state: String, runtime: String? = null, trigger: String? = null,
               attempt: Int = 0, details: Map<*, *>? = null) {
        try {
            CompanionJournal.record(context, state, runtime, trigger, attempt,
                CompanionLifecycle.decorate(context, state, details))
            val preferences = prefs(context)
            val old = JSONArray(preferences.getString("history", "[]"))
            val row = JSONObject().put("at", System.currentTimeMillis()).put("uptimeMs", SystemClock.elapsedRealtime())
                .put("state", safe(state) ?: "UNKNOWN").put("attempt", attempt.coerceIn(0, 4))
            runtime?.takeIf { Regex("[0-9a-f-]{36}").matches(it) }?.let { row.put("runtime", it.take(8)) }
            safe(trigger)?.let { row.put("trigger", it) }
            for (key in listOf("stage", "errorType")) safe(details?.get(key))?.let { row.put(key, it) }
            val elapsed = details?.get("elapsedMs") as? Number
            if (elapsed != null) row.put("elapsedMs", elapsed.toLong().coerceIn(0, 300000))
            val code = details?.get("errorCode")
            if (code is Number) row.put("errorCode", code.toInt())
            else safe(code)?.let { row.put("errorCode", it) }
            val history = JSONArray()
            for (index in (old.length() - LIMIT + 1).coerceAtLeast(0) until old.length()) history.put(old.getJSONObject(index))
            history.put(row)
            val day = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())
            val quality = if (preferences.getString("day", "") == day) JSONObject(preferences.getString("quality", "{}")) else JSONObject()
            val counter = when (state) {
                "RECOVERY_STARTED" -> "connectionAttempts"
                "RECOVERY_CONNECTED" -> "connectionSucceeded"
                "RECOVERY_FAILED" -> "connectionFailed"
                "NO_UPDATE", "READY_AWAITING_DEVICE_CHOICE", "READY_OPEN_APP" -> "checksSucceeded"
                "CHECK_FAILED", "PACKAGE_PREPARATION_FAILED" -> "checksFailed"
                "TARGET_IDENTITY_VERIFIED" -> "updatesSucceeded"
                "UPGRADE_FAILED" -> "updatesFailed"
                else -> null
            }
            if (counter != null) quality.put(counter, (quality.optInt(counter) + 1).coerceAtMost(100000))
            preferences.edit().putString("history", history.toString()).putString("day", day)
                .putString("quality", quality.toString()).apply()
        } catch (_: Exception) { /* Diagnostics must not become a radio failure. */ }
    }

    fun snapshot(context: Context): Map<String, Any?> {
        val preferences = prefs(context)
        return try {
            val history = JSONArray(preferences.getString("history", "[]"))
            val quality = JSONObject(preferences.getString("quality", "{}"))
            mapOf("limit" to LIMIT, "history" to (0 until history.length()).map { index ->
                val row = history.getJSONObject(index)
                row.keys().asSequence().associateWith { row.get(it) }
            }, "quality" to (quality.keys().asSequence().associateWith { quality.get(it) } +
                mapOf("day" to preferences.getString("day", ""), "scope" to "companion-day")))
        } catch (_: Exception) { mapOf("limit" to LIMIT, "history" to emptyList<Any>(), "quality" to null) }
    }
}
