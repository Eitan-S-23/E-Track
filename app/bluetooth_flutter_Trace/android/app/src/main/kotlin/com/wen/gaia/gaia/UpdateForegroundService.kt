package com.wen.gaia.gaia

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File

class UpdateForegroundService : Service() {
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureNotificationChannel()
        acquireWakeLock()

        val status = intent?.getStringExtra(EXTRA_STATUS) ?: "正在准备更新..."
        val progress = intent?.getIntExtra(EXTRA_PROGRESS, -1) ?: -1
        val notification = buildNotification(status, progress)
        startForegroundCompat(notification)

        when (intent?.action) {
            ACTION_INSTALL -> {
                val apkPath = intent.getStringExtra(EXTRA_APK_PATH)
                val authorityPackage = intent.getStringExtra(EXTRA_AUTHORITY_PACKAGE) ?: packageName
                if (!apkPath.isNullOrBlank()) {
                    showInstallReadyNotification(apkPath, authorityPackage, status)
                }
            }
            ACTION_STOP -> {
                stopForegroundCompat()
                stopSelf()
            }
        }

        return START_NOT_STICKY
    }

    override fun onDestroy() {
        wakeLock?.takeIf { it.isHeld }?.release()
        wakeLock = null
        super.onDestroy()
    }

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "trace:UpdateForegroundService",
        ).apply {
            setReferenceCounted(false)
            acquire(WAKE_LOCK_TIMEOUT_MS)
        }
    }

    private fun ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val updateChannel = NotificationChannel(
            CHANNEL_ID,
            "Trace 更新",
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = "Trace 应用更新下载与安装包合成"
            setShowBadge(false)
        }
        val installChannel = NotificationChannel(
            INSTALL_CHANNEL_ID,
            "Trace 安装",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Trace 更新完成后的安装入口"
            setShowBadge(false)
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(updateChannel)
        manager.createNotificationChannel(installChannel)
    }

    private fun buildNotification(status: String, progress: Int): Notification {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
            ?: Intent(this, MainActivity::class.java)
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or immutablePendingIntentFlag(),
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Trace 正在更新")
            .setContentText(status)
            .setStyle(NotificationCompat.BigTextStyle().bigText(status))
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setProgress(100, progress.coerceIn(0, 100), progress !in 0..100)
            .build()
    }

    private fun showInstallReadyNotification(apkPath: String, authorityPackage: String, status: String) {
        val apkFile = File(apkPath)
        if (!apkFile.exists()) return

        val installIntent = installIntentFor(this, apkFile.path, authorityPackage)
        startForegroundCompat(
            buildInstallReadyNotification(
                status,
                installIntent,
            ),
        )
    }

    private fun buildInstallReadyNotification(
        status: String,
        installIntent: Intent,
    ): Notification {
        val installPendingIntent = PendingIntent.getActivity(
            this,
            1,
            installIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or immutablePendingIntentFlag(),
        )

        return NotificationCompat.Builder(this, INSTALL_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Trace 更新已就绪")
            .setContentText(status)
            .setStyle(NotificationCompat.BigTextStyle().bigText(status))
            .setContentIntent(installPendingIntent)
            .addAction(R.mipmap.ic_launcher, "继续安装", installPendingIntent)
            .setOngoing(false)
            .setOnlyAlertOnce(false)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setProgress(0, 0, false)
            .build()
    }

    private fun startForegroundCompat(notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun stopForegroundCompat() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } else {
            @Suppress("DEPRECATION")
            stopForeground(true)
        }
    }

    private fun immutablePendingIntentFlag(): Int {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            PendingIntent.FLAG_IMMUTABLE
        } else {
            0
        }
    }

    companion object {
        private const val CHANNEL_ID = "trace_update"
        private const val INSTALL_CHANNEL_ID = "trace_update_install"
        private const val NOTIFICATION_ID = 2401
        private const val ACTION_START = "com.wen.gaia.gaia.UPDATE_START"
        private const val ACTION_INSTALL = "com.wen.gaia.gaia.UPDATE_INSTALL"
        private const val ACTION_STOP = "com.wen.gaia.gaia.UPDATE_STOP"
        private const val EXTRA_STATUS = "status"
        private const val EXTRA_PROGRESS = "progress"
        private const val EXTRA_APK_PATH = "apkPath"
        private const val EXTRA_AUTHORITY_PACKAGE = "authorityPackage"
        private const val WAKE_LOCK_TIMEOUT_MS = 60L * 60L * 1000L

        fun installIntentFor(
            context: Context,
            apkPath: String,
            authorityPackage: String,
        ): Intent {
            val apkFile = File(apkPath)
            val uri = FileProvider.getUriForFile(
                context,
                "$authorityPackage.fileprovider",
                apkFile,
            )
            return Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                clipData = ClipData.newUri(
                    context.contentResolver,
                    "Trace update APK",
                    uri,
                )
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }
        }


        fun start(context: Context, status: String, progress: Int): Boolean {
            val intent = Intent(context, UpdateForegroundService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_STATUS, status)
                putExtra(EXTRA_PROGRESS, progress)
            }
            return try {
                ContextCompat.startForegroundService(context, intent)
                true
            } catch (_: Exception) {
                false
            }
        }

        fun showInstallReadyNotification(
            context: Context,
            apkPath: String?,
            authorityPackage: String,
            status: String,
        ): Boolean {
            if (apkPath.isNullOrBlank()) return false
            val intent = Intent(context, UpdateForegroundService::class.java).apply {
                action = ACTION_INSTALL
                putExtra(EXTRA_STATUS, status)
                putExtra(EXTRA_PROGRESS, 100)
                putExtra(EXTRA_APK_PATH, apkPath)
                putExtra(EXTRA_AUTHORITY_PACKAGE, authorityPackage)
            }
            return try {
                ContextCompat.startForegroundService(context, intent)
                true
            } catch (_: Exception) {
                false
            }
        }

        fun stop(context: Context): Boolean {
            val intent = Intent(context, UpdateForegroundService::class.java).apply {
                action = ACTION_STOP
            }
            return try {
                ContextCompat.startForegroundService(context, intent)
                true
            } catch (_: Exception) {
                false
            }
        }


        private fun immutablePendingIntentFlag(): Int {
            return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                PendingIntent.FLAG_IMMUTABLE
            } else {
                0
            }
        }
    }
}
