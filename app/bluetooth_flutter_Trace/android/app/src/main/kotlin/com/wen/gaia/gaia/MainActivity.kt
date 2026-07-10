package com.wen.gaia.gaia

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.lifecycle.Lifecycle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

class MainActivity: FlutterActivity() {
    private var deepLinkChannel: MethodChannel? = null
    private var appUpdateChannel: MethodChannel? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        deepLinkChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            DEEP_LINK_CHANNEL
        )
        deepLinkChannel?.setMethodCallHandler { call, result ->
            when (call.method) {
                "getInitialLink" -> result.success(intent?.dataString)
                else -> result.notImplemented()
            }
        }
        appUpdateChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            APP_UPDATE_CHANNEL
        )
        appUpdateChannel?.setMethodCallHandler { call, result ->
            when (call.method) {
                "getAppInfo" -> result.success(getAppInfo())
                "canRequestPackageInstalls" -> result.success(canRequestPackageInstalls())
                "installApk" -> {
                    val apkPath = call.argument<String>("apkPath")
                    installApk(apkPath, result)
                }
                "startUpdateForegroundService" -> {
                    val status = call.argument<String>("status") ?: "正在准备更新..."
                    val progress = call.argument<Int>("progress") ?: -1
                    result.success(UpdateForegroundService.start(applicationContext, status, progress))
                }
                "updateUpdateForegroundService" -> {
                    val status = call.argument<String>("status") ?: "正在更新..."
                    val progress = call.argument<Int>("progress") ?: -1
                    result.success(UpdateForegroundService.start(applicationContext, status, progress))
                }
                "stopUpdateForegroundService" -> {
                    result.success(UpdateForegroundService.stop(applicationContext))
                }
                "showInstallReadyNotification" -> {
                    val apkPath = call.argument<String>("apkPath")
                    val status = call.argument<String>("status")
                        ?: "安装包已就绪，请点按继续安装"
                    result.success(
                        UpdateForegroundService.showInstallReadyNotification(
                            applicationContext,
                            apkPath,
                            packageName,
                            status,
                        )
                    )
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        intent.dataString?.let { link ->
            deepLinkChannel?.invokeMethod("onDeepLink", link)
        }
    }


    companion object {
        private const val DEEP_LINK_CHANNEL = "trace/deep_link"
        private const val APP_UPDATE_CHANNEL = "trace/app_update"
    }

    private fun getAppInfo(): Map<String, Any> {
        val packageInfo = packageManager.getPackageInfo(packageName, 0)
        val versionCode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageInfo.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            packageInfo.versionCode.toLong()
        }
        return mapOf(
            "versionName" to (packageInfo.versionName ?: ""),
            "versionCode" to versionCode,
            "sourceApkPath" to applicationInfo.sourceDir
        )
    }

    private fun installApk(apkPath: String?, result: MethodChannel.Result) {
        if (apkPath.isNullOrBlank()) {
            result.error("APK_PATH_EMPTY", "APK path is empty", null)
            return
        }
        val apkFile = File(apkPath)
        if (!apkFile.exists()) {
            result.error("APK_NOT_FOUND", "APK file does not exist", null)
            return
        }

        if (!lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            result.error(
                "APP_NOT_FOREGROUND",
                "Trace must be foreground before launching the package installer",
                null,
            )
            return
        }

        if (!canRequestPackageInstalls()) {
            val settingsIntent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:$packageName")
            )
            settingsIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            try {
                startActivity(settingsIntent)
            } catch (_: Exception) {
                // Flutter still needs the explicit permission error instead of a hung method call.
            }
            result.error("UNKNOWN_APP_SOURCES", "Unknown app source permission required", null)
            return
        }

        val installIntent = UpdateForegroundService.installIntentFor(
            this,
            apkFile.path,
            packageName,
        )
        try {
            startActivity(installIntent)
            result.success(mapOf("requested" to true, "launched" to true))
        } catch (e: ActivityNotFoundException) {
            result.error(
                "INSTALLER_LAUNCH_FAILED",
                e.message ?: "No package installer activity found",
                null,
            )
        } catch (e: SecurityException) {
            result.error(
                "INSTALLER_LAUNCH_FAILED",
                e.message ?: "Package installer launch was denied",
                null,
            )
        } catch (e: Exception) {
            result.error(
                "INSTALLER_LAUNCH_FAILED",
                e.message ?: "Failed to launch package installer",
                null,
            )
        }
    }

    private fun canRequestPackageInstalls(): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
            packageManager.canRequestPackageInstalls()
    }
}
