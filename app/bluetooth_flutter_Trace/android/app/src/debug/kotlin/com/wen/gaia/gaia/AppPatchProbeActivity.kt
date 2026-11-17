package com.wen.gaia.gaia

import android.app.Activity
import android.content.pm.ApplicationInfo
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.SystemClock
import android.widget.TextView
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean
import org.json.JSONObject

/** Debug-only, side-by-side codec measurement. Never installs an APK or opens BLE. */
class AppPatchProbeActivity : Activity() {
    private val cancelled = AtomicBoolean(false)

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE == 0 ||
            !packageName.endsWith(".codec") || !active.compareAndSet(false, true)) {
            finish()
            return
        }
        val view = TextView(this).apply { text = "App codec measurement" }
        setContentView(view)
        val trial = intent.getStringExtra("trial") ?: ""
        if (!Regex("^[0-9]{1,2}$").matches(trial)) {
            active.set(false)
            finish()
            return
        }
        val root = File(filesDir, "codec-probe")
        val receipt = File(root, "result-$trial.json")
        if (receipt.exists()) {
            active.set(false)
            view.text = "Existing measurement retained"
            return
        }
        val cancelDuring = intent.getBooleanExtra("cancel_during", false)
        Thread({
            val report = JSONObject().put("trial", trial).put("algorithm", BsdiffLzmaPatch.FORMAT)
                .put("packageName", packageName).put("manufacturer", Build.MANUFACTURER)
                .put("model", Build.MODEL).put("sdk", Build.VERSION.SDK_INT)
                .put("startedAtMillis", System.currentTimeMillis())
            val output = File(root, "output-$trial.apk")
            try {
                val metadataFile = File(root, "input.json")
                require(metadataFile.length() in 1L..16384L) { "Missing/oversized probe metadata" }
                val input = JSONObject(metadataFile.readText())
                report.put("input", input)
                var peakPss = 0L
                var peakJava = 0L
                var samples = 0
                var lastSample = 0L
                fun sample(force: Boolean = false) {
                    val now = SystemClock.elapsedRealtime()
                    if (!force && now - lastSample < 100) return
                    lastSample = now
                    peakPss = maxOf(peakPss, Debug.getPss())
                    val runtime = Runtime.getRuntime()
                    peakJava = maxOf(peakJava, runtime.totalMemory() - runtime.freeMemory())
                    samples++
                }
                sample(true)
                report.put("baselinePssKb", peakPss)
                val start = SystemClock.elapsedRealtime()
                var completed = 0L
                try {
                    val result = BsdiffLzmaPatch.apply(File(root, "base.apk"), File(root, "patch.bin"), output,
                        input.getString("oldSha256"), input.getString("patchSha256"), input.getString("newSha256"),
                        input.getLong("newSize"), object : BsdiffLzmaPatch.Observer {
                            override fun cancelled(): Boolean = cancelled.get() || (cancelDuring && completed >= 65536)
                            override fun progress(bytes: Long, total: Long) { completed = bytes; sample() }
                        })
                    require(!cancelDuring) { "Cancellation did not interrupt decoding" }
                    val digest = MessageDigest.getInstance("SHA-256")
                    output.inputStream().use { stream ->
                        val bytes = ByteArray(65536)
                        while (true) {
                            val count = stream.read(bytes)
                            if (count < 0) break
                            digest.update(bytes, 0, count)
                        }
                    }
                    val outputSha = digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
                    require(outputSha == input.getString("newSha256")) { "Readback mismatch" }
                    report.put("status", "pass").put("outputSha256", outputSha).put("outputBytes", result.bytes)
                        .put("decoderMillis", result.elapsedMillis).put("dictionaryBytes", result.dictionaryBytes)
                        .put("controls", result.controls)
                } catch (error: CancellationException) {
                    require(cancelDuring && !output.exists()) { "Unexpected cancellation or leaked output" }
                    report.put("status", "cancelled-pass").put("outputRetained", false)
                } finally {
                    sample(true)
                    report.put("elapsedIncludingReadbackMillis", SystemClock.elapsedRealtime() - start)
                        .put("observedPeakPssKb", peakPss).put("observedPeakJavaBytes", peakJava).put("samples", samples)
                        .put("memorySampling", "100ms progress sampling plus start/end; not exact peak")
                }
            } catch (error: Exception) {
                report.put("status", "failed").put("error", error.javaClass.simpleName + ": " + error.message)
            } finally {
                try {
                    val temporary = File(root, "result-$trial.json.tmp")
                    check(temporary.createNewFile()) { "Existing probe temporary output" }
                    temporary.writeText(report.toString(2))
                    check(!receipt.exists() && temporary.renameTo(receipt)) { "Probe receipt write failed" }
                    runOnUiThread { view.text = report.optString("status") }
                } finally {
                    active.set(false)
                }
            }
        }, "app-codec-probe").start()
    }

    override fun onDestroy() {
        cancelled.set(true)
        super.onDestroy()
    }

    companion object { private val active = AtomicBoolean(false) }
}
