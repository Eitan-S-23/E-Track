package com.wen.gaia.gaia

import android.content.Context
import android.os.SystemClock
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** All disk work is serialized off the BLE/UI thread; input is allowlisted. */
internal object CompanionJournal {
    const val MAX_BYTES = 20L * 1024 * 1024
    const val RETENTION_MS = 7L * 86400000
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private val queued = AtomicInteger()
    private val dropped = AtomicInteger()
    private var context: Context? = null
    private var pending: JSONObject? = null
    private var signature = ""
    private var sequence = 0L
    private var pruned = 0L
    private var errors = 0
    private var detailUntil = 0L
    private var detailBudget = 0
    private fun prefs(c: Context) = c.getSharedPreferences("companion_journal_v2", Context.MODE_PRIVATE)
    private fun dir(c: Context) = File(c.filesDir, "companion-journal-v2").apply { mkdirs() }
    private fun files(c: Context) = dir(c).listFiles()?.filter { it.name.endsWith(".jsonl") }?.sortedBy { it.name } ?: emptyList()
    private fun safe(value: Any?) = (value as? String)?.takeIf { Regex("[A-Za-z0-9_-]{1,64}").matches(it) }
    private val strings = listOf("stage", "errorType", "errorCode", "taskId", "recoveryId", "deviceKey",
        "source", "outcome", "reason", "uiState", "launchSource", "termination", "reconnection", "processId",
        "kind", "packageSha", "beforeSha", "targetSha", "afterSha")
    private val numbers = listOf("elapsedMs", "startupWaitMs", "connectionMs", "closeToReadyMs", "lastCheckAt",
        "nextCheckAt", "executedAt", "retryCount", "beforeVersion", "targetVersion", "afterVersion", "startedAt", "verifiedAt")
    init { worker.scheduleWithFixedDelay({ runCatching { context?.let { flush(it) } }.onFailure { errors++ } }, 1, 1, TimeUnit.SECONDS) }
    private fun initialize(c: Context) {
        if (context != null) return
        context = c.applicationContext
        val p = prefs(c)
        sequence = p.getLong("sequence", 0); pruned = p.getLong("pruned", 0)
        errors = p.getInt("errors", 0); dropped.addAndGet(p.getInt("dropped", 0))
        files(c).lastOrNull()?.forEachLine { line ->
            runCatching { sequence = maxOf(sequence, JSONObject(line).optLong("seq")) }
        }
    }
    fun record(c: Context, state: String, runtime: String?, trigger: String?, attempt: Int, details: Map<*, *>?) {
        val row = JSONObject().put("at", System.currentTimeMillis()).put("uptimeMs", SystemClock.elapsedRealtime())
            .put("state", safe(state) ?: "UNKNOWN").put("attempt", attempt.coerceIn(0, 100000))
            .put("level", if (state.contains("FAIL") || state.contains("TIMEOUT") || details?.get("errorCode") != null) "error" else "info")
        runtime?.takeIf { Regex("[0-9a-f-]{36}").matches(it) }?.let { row.put("runtime", it.take(8)) }
        safe(trigger)?.let { row.put("trigger", it) }
        for (key in strings) safe(details?.get(key))?.let { row.put(key, it) }
        for (key in numbers) (details?.get(key) as? Number)?.toLong()?.takeIf { it >= 0 }?.let { row.put(key, it) }
        (details?.get("errorCode") as? Number)?.let { row.put("errorCode", it.toInt()) }
        if (attempt > 0 && !row.has("retryCount")) row.put("retryCount", attempt - 1)
        if (queued.incrementAndGet() > 512) { queued.decrementAndGet(); dropped.incrementAndGet(); return }
        worker.execute {
            try {
                initialize(c)
                val key = (listOf("state", "runtime", "trigger", "attempt") + strings + numbers).joinToString("|") { row.optString(it) }
                val old = pending
                if (old != null && key == signature && row.getLong("uptimeMs") - old.getLong("uptimeMs") < 1000) {
                    old.put("count", old.optInt("count", 1) + 1).put("lastAt", row.getLong("at"))
                } else {
                    flush(c)
                    row.put("seq", ++sequence).put("count", 1)
                    if (SystemClock.elapsedRealtime() < detailUntil && detailBudget > 0) {
                        val runtimeMemory = Runtime.getRuntime()
                        row.put("diagnosticMode", "bounded_detail")
                            .put("queueDelayMs", (SystemClock.elapsedRealtime() - row.getLong("uptimeMs")).coerceAtLeast(0))
                            .put("heapUsedBytes", runtimeMemory.totalMemory() - runtimeMemory.freeMemory())
                            .put("queuedEvents", queued.get())
                        detailBudget--
                    }
                    pending = row; signature = key
                }
            } catch (_: Exception) { errors++ }
            finally { queued.decrementAndGet() }
        }
    }
    private fun prune(c: Context, reserve: Int = 0) {
        val list = files(c)
        var total = list.sumOf { it.length() }
        for (f in list) if (f.lastModified() < System.currentTimeMillis() - RETENTION_MS || total + reserve > MAX_BYTES - 131072) {
            val size = f.length(); check(f.delete()) { "RETENTION_FAILED" }; total -= size; pruned += size
        }
        prefs(c).edit().putLong("pruned", pruned).apply()
    }
    private fun flush(c: Context) {
        val row = pending ?: return
        val bytes = (row.toString() + "\n").toByteArray(Charsets.UTF_8)
        prune(c, bytes.size)
        val hour = row.getLong("at") / 3600000
        val last = files(c).lastOrNull()
        val complete = last == null || last.length() == 0L || java.io.RandomAccessFile(last, "r").use {
            it.seek(it.length() - 1); it.read() == 10
        }
        val file = if (last != null && complete && last.name.startsWith("$hour-") && last.length() + bytes.size <= 131072) last
            else File(dir(c), "$hour-${row.getLong("seq").toString().padStart(16, '0')}.jsonl")
        file.appendBytes(bytes); pending = null
        prefs(c).edit().putLong("sequence", sequence).putLong("pruned", pruned)
            .putInt("errors", errors).putInt("dropped", dropped.get()).apply()
    }
    private fun metadata(c: Context): Map<String, Any?> = mapOf("schema" to 2, "retentionDays" to 7,
        "maximumBytes" to MAX_BYTES, "retainedBytes" to files(c).sumOf { it.length() }, "prunedBytes" to pruned,
        "droppedEvents" to dropped.get(), "ioErrors" to errors, "queuedEvents" to queued.get(),
        "processKillLoss" to "unknown_up_to_buffer_and_queue", "legacyHistory" to "not_migrated",
        "detailRemaining" to detailBudget, "detailUntilUptimeMs" to detailUntil)
    fun query(c: Context, filter: Map<*, *>?, done: (Result<Map<String, Any?>>) -> Unit) {
        worker.execute { done(runCatching {
            initialize(c); flush(c); prune(c)
            val limit = ((filter?.get("limit") as? Number)?.toInt() ?: 80).coerceIn(1, 200)
            val before = (filter?.get("beforeSeq") as? Number)?.toLong() ?: Long.MAX_VALUE
            val from = maxOf((filter?.get("from") as? Number)?.toLong() ?: 0, System.currentTimeMillis() - RETENTION_MS)
            val to = (filter?.get("to") as? Number)?.toLong() ?: Long.MAX_VALUE
            val search = (filter?.get("search") as? String)?.take(128)?.lowercase() ?: ""
            val rows = java.util.ArrayDeque<Map<String, Any>>()
            var matched = 0; var malformed = 0
            for (file in files(c)) file.forEachLine { line ->
                val row = try { JSONObject(line) } catch (_: Exception) { malformed++; null }
                if (row != null && row.optLong("seq") < before && row.optLong("at") in from..to &&
                    listOf("deviceKey", "taskId", "level").all { key ->
                        val value = filter?.get(key) as? String; value.isNullOrEmpty() || row.optString(key) == value
                    } && (search.isEmpty() || row.toString().lowercase().contains(search))) {
                    matched++; rows.addLast(row.keys().asSequence().associateWith { row.get(it) })
                    if (rows.size > limit) rows.removeFirst()
                }
            }
            val result = rows.toList().reversed()
            mapOf("history" to result, "nextCursor" to if (matched > result.size) result.last()["seq"] else null,
                "metadata" to metadata(c) + mapOf("malformedLines" to malformed, "pageTruncated" to (matched > result.size)))
        }) }
    }
    fun detailed(minutes: Int) { worker.execute {
        detailUntil = SystemClock.elapsedRealtime() + minutes.coerceIn(0, 15) * 60000L
        detailBudget = if (minutes <= 0) 0 else 2000
    } }
    fun export(c: Context, done: (Result<File>) -> Unit) { worker.execute { done(runCatching {
        initialize(c); flush(c); prune(c)
        val out = File(c.cacheDir, "companion-diagnostics.zip")
        var malformed = 0
        ZipOutputStream(out.outputStream().buffered()).use { zip ->
            zip.putNextEntry(ZipEntry("events.jsonl"))
            for (f in files(c)) f.inputStream().use { it.copyTo(zip) }
            zip.closeEntry(); zip.putNextEntry(ZipEntry("readable.txt"))
            zip.write("E-Track local diagnostic timeline. No addresses, credentials or payloads.\n".toByteArray())
            for (f in files(c)) f.forEachLine { line -> try {
                val row = JSONObject(line)
                zip.write((row.keys().asSequence().joinToString(" ") { "$it=${row.get(it)}" } + "\n").toByteArray())
            } catch (_: Exception) { malformed++ } }
            zip.closeEntry(); zip.putNextEntry(ZipEntry("metadata.json"))
            zip.write(JSONObject(metadata(c) + mapOf("exportTruncated" to false, "malformedLines" to malformed,
                "missing" to "Only observed local events. Process death or force-stop may have no closing callback.")).toString(2).toByteArray())
            zip.closeEntry()
        }
        out
    }) } }
}
