package com.wen.gaia.gaia

import android.content.Context
import android.os.Handler
import android.os.Looper
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.util.concurrent.CancellationException
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** Engine channel survives Activity backgrounding; one request owns the worker. */
object AppPatchBridge {
    private data class Task(val id: String, val cancelled: AtomicBoolean = AtomicBoolean(false))
    private val main = Handler(Looper.getMainLooper())
    private val executor = Executors.newSingleThreadExecutor { work ->
        Thread(work, "app-patch").apply { isDaemon = true }
    }
    private var active: Task? = null

    fun install(engine: FlutterEngine, context: Context) {
        val app = context.applicationContext
        val channel = MethodChannel(engine.dartExecutor.binaryMessenger, "trace/app_patch")
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "cancel" -> {
                    val task = active
                    val matches = task != null && call.argument<String>("id") == task.id
                    if (matches) task!!.cancelled.set(true)
                    result.success(matches)
                }
                "apply" -> apply(app, channel, call, result)
                else -> result.notImplemented()
            }
        }
    }

    private fun apply(context: Context, channel: MethodChannel, call: MethodCall, result: MethodChannel.Result) {
        if (active != null) {
            result.error("PATCH_BUSY", "Another patch is still running", null)
            return
        }
        try {
            fun text(name: String): String = call.argument<String>(name)?.takeIf { it.isNotBlank() }
                ?: throw IllegalArgumentException("Missing $name")
            val id = text("id")
            require(Regex("^[0-9a-f-]{1,80}$").matches(id)) { "Invalid request identity" }
            require(text("algorithm") == BsdiffLzmaPatch.FORMAT) { "Unsupported patch format" }
            val old = File(text("oldApkPath")).canonicalFile
            require(old == File(context.applicationInfo.sourceDir).canonicalFile) { "Base is not the installed APK" }
            val cache = context.cacheDir.canonicalFile
            fun cacheFile(name: String): File = File(text(name)).canonicalFile.also {
                require(it.path.startsWith(cache.path + File.separator)) { "Patch path escapes app cache" }
            }
            val patch = cacheFile("patchPath")
            val output = cacheFile("outputApkPath")
            val oldSha = text("oldSha256")
            val patchSha = text("patchSha256")
            val newSha = text("newSha256")
            val rawSize = call.argument<Number>("newSize")
            require(rawSize is Int || rawSize is Long) { "Invalid output size" }
            val size = rawSize.toLong()
            val task = Task(id)
            active = task
            executor.execute {
                try {
                    var lastProgress = 0L
                    val measured = BsdiffLzmaPatch.apply(old, patch, output, oldSha, patchSha, newSha, size,
                        object : BsdiffLzmaPatch.Observer {
                            override fun cancelled(): Boolean = task.cancelled.get()
                            override fun progress(completed: Long, total: Long) {
                                val now = System.nanoTime()
                                if (completed != total && now - lastProgress < 100_000_000L) return
                                lastProgress = now
                                main.post {
                                    if (active === task && !task.cancelled.get()) channel.invokeMethod("progress",
                                        mapOf("id" to id, "completed" to completed, "total" to total))
                                }
                            }
                        })
                    main.post {
                        if (active === task) active = null
                        if (task.cancelled.get()) {
                            val removed = output.delete() || !output.exists()
                            result.error(if (removed) "PATCH_CANCELLED" else "PATCH_FAILED",
                                if (removed) "Patch cancelled" else "Partial output cleanup failed", null)
                        } else {
                            result.success(mapOf("id" to id, "bytes" to measured.bytes,
                                "sha256" to newSha, "elapsedMillis" to measured.elapsedMillis,
                                "dictionaryBytes" to measured.dictionaryBytes, "controls" to measured.controls))
                        }
                    }
                } catch (error: Exception) {
                    main.post {
                        if (active === task) active = null
                        result.error(if (error is CancellationException) "PATCH_CANCELLED" else "PATCH_FAILED",
                            error.message ?: "Patch failed", null)
                    }
                }
            }
        } catch (error: Exception) {
            active = null
            result.error("PATCH_INVALID", error.message ?: "Invalid patch request", null)
        }
    }
}
