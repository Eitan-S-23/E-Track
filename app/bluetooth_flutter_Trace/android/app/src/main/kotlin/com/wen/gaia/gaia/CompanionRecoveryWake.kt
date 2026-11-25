package com.wen.gaia.gaia

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.os.SystemClock
import android.provider.Settings
import java.util.UUID

/** One process-independent fallback for the current cooldown, not a polling loop. */
internal object CompanionRecoveryWake {
    const val ACTION = "com.wen.gaia.gaia.COMPANION_RECOVERY_WAKE"
    private const val REQUEST = 2414
    private const val MAX_DELAY = 3600000L
    private const val PREFIX = "recoveryWake"
    private val fields = listOf("Id", "Revision", "Device", "At", "Elapsed", "Created", "Boot", "Requested")

    private data class Ticket(val id: String, val revision: String, val device: String,
                              val at: Long, val elapsed: Long, val created: Long, val boot: Int)

    private fun boot(context: Context) = runCatching {
        Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
    }.getOrDefault(-1)

    private fun read(context: Context): Ticket? {
        val p = CompanionBridge.preferences(context)
        val id = p.getString(PREFIX + "Id", null) ?: return null
        return Ticket(id, p.getString(PREFIX + "Revision", "") ?: "",
            p.getString(PREFIX + "Device", "") ?: "", p.getLong(PREFIX + "At", 0),
            p.getLong(PREFIX + "Elapsed", 0), p.getLong(PREFIX + "Created", 0),
            p.getInt(PREFIX + "Boot", -1))
    }

    private fun current(context: Context, ticket: Ticket): Boolean =
        CompanionBridge.enabled(context) && ticket.revision == CompanionBridge.revision(context) &&
            CompanionBridge.address(context)?.let { CompanionBridge.deviceToken(it) == ticket.device } == true &&
            ticket.at == CompanionBridge.preferences(context).getLong("nextAttempt", 0)

    private fun sameBoot(context: Context, ticket: Ticket): Boolean =
        ticket.boot >= 0 && ticket.boot == boot(context) && SystemClock.elapsedRealtime() >= ticket.created

    fun remainingMs(context: Context): Long {
        val next = CompanionBridge.preferences(context).getLong("nextAttempt", 0)
        if (next <= 0) return 0
        val ticket = read(context)
        return if (ticket != null && current(context, ticket) && sameBoot(context, ticket)) {
            (ticket.elapsed - SystemClock.elapsedRealtime()).coerceAtLeast(0)
        } else (next - System.currentTimeMillis()).coerceIn(0, MAX_DELAY)
    }

    private fun wakeIntent(context: Context, id: String) = Intent(context, CompanionRecoveryReceiver::class.java)
        .setAction(ACTION).setData(Uri.parse("etrack://companion-recovery/$id"))

    private fun pending(context: Context, id: String, create: Boolean): PendingIntent? =
        PendingIntent.getBroadcast(context, REQUEST, wakeIntent(context, id),
            PendingIntent.FLAG_IMMUTABLE or if (create) PendingIntent.FLAG_UPDATE_CURRENT else PendingIntent.FLAG_NO_CREATE)

    private fun removeAlarm(context: Context, ticket: Ticket) {
        try {
            pending(context, ticket.id, false)?.let {
                context.getSystemService(AlarmManager::class.java).cancel(it)
                it.cancel()
            }
        } catch (error: Exception) {
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_CANCEL_FAILED", trigger = "alarm",
                details = mapOf("errorType" to error.javaClass.simpleName, "wakeId" to ticket.id))
        }
    }

    fun cancel(context: Context, clearBackoff: Boolean = false): Boolean {
        val p = CompanionBridge.preferences(context)
        if (fields.none { p.contains(PREFIX + it) } && (!clearBackoff || p.getLong("nextAttempt", 0) == 0L)) return true
        val ticket = read(context)
        val edit = p.edit()
        fields.forEach { edit.remove(PREFIX + it) }
        if (clearBackoff) edit.putLong("nextAttempt", 0)
        val saved = edit.commit()
        ticket?.let { removeAlarm(context, it) }
        if (!saved) CompanionDiagnostics.record(context, "RECOVERY_WAKE_CANCEL_FAILED", trigger = "alarm",
            details = mapOf("stage" to "cancel_persistence", "errorCode" to "SETTINGS_NOT_PERSISTED"))
        return saved
    }

    fun schedule(context: Context, next: Long): Boolean {
        val address = CompanionBridge.address(context)
        if (!CompanionBridge.enabled(context) || address == null || next <= 0) {
            cancel(context)
            return false
        }
        val p = CompanionBridge.preferences(context)
        val old = read(context)
        val now = SystemClock.elapsedRealtime()
        val ticket = if (old != null && old.at == next && current(context, old) && sameBoot(context, old)) old
            else Ticket(UUID.randomUUID().toString(), CompanionBridge.revision(context),
                CompanionBridge.deviceToken(address), next,
                now + (next - System.currentTimeMillis()).coerceIn(0, MAX_DELAY), now, boot(context))
        if (old != null && old.id != ticket.id) removeAlarm(context, old)
        try {
            // Persist the fence before registering with Android. Re-creation can
            // reconcile an interrupted registration without reusing an old owner.
            check(p.edit().putLong("nextAttempt", next)
                .putString(PREFIX + "Id", ticket.id).putString(PREFIX + "Revision", ticket.revision)
                .putString(PREFIX + "Device", ticket.device).putLong(PREFIX + "At", ticket.at)
                .putLong(PREFIX + "Elapsed", ticket.elapsed).putLong(PREFIX + "Created", ticket.created)
                .putInt(PREFIX + "Boot", ticket.boot).putBoolean(PREFIX + "Requested", false).commit())
            context.getSystemService(AlarmManager::class.java).setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP, ticket.elapsed, pending(context, ticket.id, true)!!)
            p.edit().putBoolean(PREFIX + "Requested", true).apply()
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_SCHEDULED", trigger = "alarm",
                details = details(context, ticket) + ("scheduleMode" to "inexact_allow_idle"))
            return true
        } catch (error: Exception) {
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_SCHEDULE_FAILED", trigger = "alarm",
                details = details(context, ticket) + mapOf("stage" to "alarm_schedule",
                    "errorType" to error.javaClass.simpleName))
            return false
        }
    }

    fun restore(context: Context) {
        val old = read(context)
        if (!CompanionBridge.enabled(context) || !CompanionBridge.associated(context) ||
            (old != null && !current(context, old))) {
            cancel(context, clearBackoff = true)
            return
        }
        val next = CompanionBridge.preferences(context).getLong("nextAttempt", 0)
        if (next > 0) schedule(context, next) else cancel(context)
    }

    private fun details(context: Context, ticket: Ticket): Map<String, Any> {
        val monotonic = sameBoot(context, ticket)
        val late = if (monotonic) SystemClock.elapsedRealtime() - ticket.elapsed else System.currentTimeMillis() - ticket.at
        val idle = runCatching {
            if (context.getSystemService(PowerManager::class.java).isDeviceIdleMode) "doze" else "not_doze"
        }.getOrDefault("unknown")
        val battery = runCatching {
            if (context.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(context.packageName)) "exempt" else "optimized"
        }.getOrDefault("unknown")
        return mapOf("wakeId" to ticket.id, "nextCheckAt" to ticket.at,
            "deadlineElapsedMs" to ticket.elapsed, "wakeDelayMs" to late.coerceAtLeast(0),
            "clockSource" to if (monotonic) "elapsed" else "wall_fallback",
            "idleState" to idle, "batteryPolicy" to battery)
    }

    fun snapshot(context: Context): Map<String, Any?> {
        val ticket = read(context)
        return mapOf("pending" to (ticket != null && current(context, ticket)),
            "requested" to CompanionBridge.preferences(context).getBoolean(PREFIX + "Requested", false),
            "nextAttemptAt" to ticket?.at, "deadlineElapsedMs" to ticket?.elapsed,
            "remainingMs" to remainingMs(context))
    }

    fun receive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return
        val ticket = read(context)
        if (ticket == null || intent.data != wakeIntent(context, ticket.id).data) {
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_IGNORED", trigger = "alarm",
                details = mapOf("reason" to "stale_generation"))
            return
        }
        val details = details(context, ticket) + ("executedAt" to System.currentTimeMillis())
        if (!current(context, ticket) || !CompanionBridge.associated(context)) {
            cancel(context, clearBackoff = true)
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_IGNORED", trigger = "alarm",
                details = details + ("reason" to "disabled_or_owner_changed"))
            return
        }
        if (remainingMs(context) > 0) {
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_IGNORED", trigger = "alarm",
                details = details + ("reason" to "before_deadline"))
            schedule(context, ticket.at)
            return
        }
        CompanionDiagnostics.record(context, "RECOVERY_WAKE_RECEIVED", trigger = "alarm", details = details)
        // Claim this generation before handing off. The Handler/job/presence
        // paths share Service ownership and cannot replay this PendingIntent.
        if (!cancel(context, clearBackoff = true)) return
        if (DeviceOtaService.active?.hasTask() == true || CompanionService.active?.recoveryHealthy() == true) {
            CompanionDiagnostics.record(context, "RECOVERY_WAKE_COALESCED", trigger = "alarm",
                details = details + ("reason" to "owner_already_active"))
            return
        }
        CompanionBridge.observePresence(context, "alarm")
        val requested = CompanionService.start(context, "recovery")
        CompanionDiagnostics.record(context,
            if (requested) "RECOVERY_WAKE_START_REQUESTED" else "RECOVERY_WAKE_START_FAILED",
            trigger = "alarm", details = details)
    }
}

class CompanionRecoveryReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        CompanionRecoveryWake.receive(context, intent)
    }
}
