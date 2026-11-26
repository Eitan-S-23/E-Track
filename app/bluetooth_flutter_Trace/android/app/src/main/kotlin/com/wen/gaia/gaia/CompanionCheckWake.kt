package com.wen.gaia.gaia

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.SystemClock
import android.provider.Settings
import java.util.UUID

/** The actual next check deadline, independent of BLE backoff and periodic job windows. */
internal object CompanionCheckWake {
    const val ACTION = "com.wen.gaia.gaia.COMPANION_CHECK_WAKE"
    private const val REQUEST = 2415
    private const val PREFIX = "checkWake"
    private const val MAX_DELAY = 86400000L
    private val fields = listOf("Id", "Revision", "Device", "At", "Elapsed", "Created", "Boot", "Requested", "Mode")
    private data class Ticket(val id: String, val revision: String, val device: String,
                              val at: Long, val elapsed: Long, val created: Long, val boot: Int)

    private fun boot(context: Context) = runCatching {
        Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
    }.getOrDefault(-1)

    private fun read(context: Context): Ticket? {
        val p = CompanionBridge.preferences(context)
        val id = p.getString(PREFIX + "Id", null) ?: return null
        return Ticket(id, p.getString(PREFIX + "Revision", "") ?: "", p.getString(PREFIX + "Device", "") ?: "",
            p.getLong(PREFIX + "At", 0), p.getLong(PREFIX + "Elapsed", 0), p.getLong(PREFIX + "Created", 0),
            p.getInt(PREFIX + "Boot", -1))
    }

    private fun current(context: Context, ticket: Ticket) = CompanionBridge.enabled(context) &&
        ticket.revision == CompanionBridge.revision(context) && ticket.at == CompanionBridge.preferences(context).getLong("nextCheckAt", 0) &&
        CompanionBridge.address(context)?.let { CompanionBridge.deviceToken(it) == ticket.device } == true

    private fun sameBoot(context: Context, ticket: Ticket) = ticket.boot >= 0 && ticket.boot == boot(context) &&
        SystemClock.elapsedRealtime() >= ticket.created

    private fun remaining(context: Context, ticket: Ticket) = if (sameBoot(context, ticket))
        (ticket.elapsed - SystemClock.elapsedRealtime()).coerceAtLeast(0)
        else (ticket.at - System.currentTimeMillis()).coerceIn(0, MAX_DELAY)

    private fun intent(context: Context, id: String) = Intent(context, CompanionCheckReceiver::class.java)
        .setAction(ACTION).setData(Uri.parse("etrack://companion-check/$id"))

    private fun pending(context: Context, id: String, create: Boolean) = PendingIntent.getBroadcast(context, REQUEST,
        intent(context, id), PendingIntent.FLAG_IMMUTABLE or if (create) PendingIntent.FLAG_UPDATE_CURRENT else PendingIntent.FLAG_NO_CREATE)

    private fun removeAlarm(context: Context, ticket: Ticket) {
        try {
            pending(context, ticket.id, false)?.let {
                context.getSystemService(AlarmManager::class.java).cancel(it)
                it.cancel()
            }
        } catch (error: Exception) {
            CompanionDiagnostics.record(context, "CHECK_WAKE_CANCEL_FAILED", trigger = "alarm",
                details = mapOf("errorType" to error.javaClass.simpleName))
        }
    }

    private fun clear(context: Context, claim: Boolean): Boolean {
        val ticket = read(context)
        val edit = CompanionBridge.preferences(context).edit().remove("nextCheckAt")
        fields.forEach { edit.remove(PREFIX + it) }
        if (claim) edit.putBoolean("checkPending", true)
        val saved = edit.commit()
        if (saved) ticket?.let { removeAlarm(context, it) }
        return saved
    }

    fun cancel(context: Context): Boolean = clear(context, false)

    fun waiting(context: Context): Boolean = read(context)?.let { current(context, it) && remaining(context, it) > 0 } == true

    fun schedule(context: Context, at: Long): Boolean {
        val address = CompanionBridge.address(context)
        if (!CompanionBridge.enabled(context) || address == null || at <= 0) return cancel(context)
        val p = CompanionBridge.preferences(context)
        val now = SystemClock.elapsedRealtime()
        val old = read(context)
        val ticket = if (old != null && old.at == at && current(context, old) && sameBoot(context, old)) old
            else Ticket(UUID.randomUUID().toString(), CompanionBridge.revision(context), CompanionBridge.deviceToken(address),
                at, now + (at - System.currentTimeMillis()).coerceIn(0, MAX_DELAY), now, boot(context))
        try {
            check(p.edit().putLong("nextCheckAt", at).putString(PREFIX + "Id", ticket.id)
                .putString(PREFIX + "Revision", ticket.revision).putString(PREFIX + "Device", ticket.device)
                .putLong(PREFIX + "At", ticket.at).putLong(PREFIX + "Elapsed", ticket.elapsed)
                .putLong(PREFIX + "Created", ticket.created).putInt(PREFIX + "Boot", ticket.boot)
                .putBoolean(PREFIX + "Requested", false).commit())
            if (old != null && old.id != ticket.id) removeAlarm(context, old)
            val mode = CompanionAlarm.schedule(context, ticket.elapsed, pending(context, ticket.id, true)!!)
            p.edit().putBoolean(PREFIX + "Requested", true).putString(PREFIX + "Mode", mode).apply()
            CompanionDiagnostics.record(context, "CHECK_WAKE_SCHEDULED", trigger = "alarm",
                details = mapOf("nextCheckAt" to at, "deadlineElapsedMs" to ticket.elapsed, "scheduleMode" to mode))
            return true
        } catch (error: Exception) {
            CompanionDiagnostics.record(context, "CHECK_WAKE_SCHEDULE_FAILED", trigger = "alarm",
                details = mapOf("nextCheckAt" to at, "errorType" to error.javaClass.simpleName))
            return false
        }
    }

    fun restore(context: Context) {
        val ticket = read(context)
        if (!CompanionBridge.enabled(context) || !CompanionBridge.associated(context) ||
            (ticket != null && !current(context, ticket))) {
            cancel(context)
            return
        }
        val at = CompanionBridge.preferences(context).getLong("nextCheckAt", 0)
        if (at > 0) schedule(context, at)
    }

    fun claimDue(context: Context, trigger: String): Boolean {
        val ticket = read(context) ?: return false
        if (!current(context, ticket) || remaining(context, ticket) > 0) return false
        if (!clear(context, true)) return false
        CompanionDiagnostics.record(context, "CHECK_WAKE_RECEIVED", trigger = trigger,
            details = mapOf("nextCheckAt" to ticket.at, "executedAt" to System.currentTimeMillis(),
                "wakeDelayMs" to (SystemClock.elapsedRealtime() - ticket.elapsed).coerceAtLeast(0)))
        return true
    }

    fun snapshot(context: Context): Map<String, Any?> {
        val ticket = read(context)?.takeIf { current(context, it) }
        val p = CompanionBridge.preferences(context)
        return mapOf("pending" to (ticket != null), "requested" to p.getBoolean(PREFIX + "Requested", false),
            "nextCheckAt" to ticket?.at, "deadlineElapsedMs" to ticket?.elapsed,
            "remainingMs" to ticket?.let { remaining(context, it) }, "scheduleMode" to p.getString(PREFIX + "Mode", null),
            "exactWakeAllowed" to CompanionAlarm.exactAllowed(context), "checkPending" to p.getBoolean("checkPending", false))
    }

    fun receive(context: Context, request: Intent) {
        if (request.action != ACTION) return
        val ticket = read(context)
        if (ticket == null || request.data != intent(context, ticket.id).data) {
            CompanionDiagnostics.record(context, "CHECK_WAKE_IGNORED", trigger = "alarm", details = mapOf("reason" to "stale_generation"))
            return
        }
        if (!current(context, ticket) || !CompanionBridge.associated(context)) {
            cancel(context)
            return
        }
        if (remaining(context, ticket) > 0) {
            schedule(context, ticket.at)
            return
        }
        if (!claimDue(context, "alarm")) return
        val backoff = CompanionRecoveryWake.remainingMs(context)
        if (backoff > 0 || DeviceOtaService.active?.hasTask() == true) {
            CompanionDiagnostics.record(context, "CHECK_NOT_EXECUTED", trigger = "alarm",
                details = mapOf("reason" to if (backoff > 0) "recovery_backoff" else "ota_busy"))
            return
        }
        // Even a healthy connected owner must receive this pending HTTP check.
        val requested = CompanionService.start(context, "periodic")
        CompanionDiagnostics.record(context, if (requested) "CHECK_WAKE_START_REQUESTED" else "CHECK_WAKE_START_FAILED", trigger = "alarm")
    }
}

class CompanionCheckReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = CompanionCheckWake.receive(context, intent)
}
