package com.wen.gaia.gaia

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.os.Build

internal object CompanionAlarm {
    fun exactAllowed(context: Context): Boolean = Build.VERSION.SDK_INT < 31 || runCatching {
        context.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()
    }.getOrDefault(false)

    fun schedule(context: Context, elapsedAt: Long, intent: PendingIntent): String {
        val manager = context.getSystemService(AlarmManager::class.java)
        if (exactAllowed(context)) {
            try {
                manager.setExactAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, elapsedAt, intent)
                return "exact_allow_idle"
            } catch (error: SecurityException) {
                // Permission can change between the capability check and registration.
                CompanionDiagnostics.record(context, "EXACT_WAKE_UNAVAILABLE", trigger = "alarm",
                    details = mapOf("errorType" to error.javaClass.simpleName))
            }
        }
        manager.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, elapsedAt, intent)
        return "inexact_allow_idle"
    }
}
