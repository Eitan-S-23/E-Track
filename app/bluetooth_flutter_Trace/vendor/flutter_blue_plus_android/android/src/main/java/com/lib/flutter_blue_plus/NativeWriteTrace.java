package com.lib.flutter_blue_plus;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.CRC32;

/** Bounded observation only. No Bluetooth operations, timers, channel calls or I/O. */
final class NativeWriteTrace {
    static final int CAPACITY = 8192;
    interface Clock { long nanos(); }
    private final Clock clock;
    private final int capacity;
    private final List<Entry> entries = new ArrayList<>();
    private final IdentityHashMap<Object, Integer> connections = new IdentityHashMap<>();
    private final IdentityHashMap<Object, Entry> pending = new IdentityHashMap<>();
    private String captureId;
    private String remoteId;
    private long origin;
    private long epoch;
    private int overflow;
    private int errors;
    private int snapshots;

    static final class Entry {
        final long epoch;
        final Object gatt;
        final Object characteristic;
        // id, connection, bytes, CRC32, entry, submit, return, callback, dispatch, API, GATT status
        final long[] values;
        Entry(long epoch, Object gatt, Object characteristic, long[] values) {
            this.epoch = epoch;
            this.gatt = gatt;
            this.characteristic = characteristic;
            this.values = values;
        }
    }

    NativeWriteTrace(Clock clock) { this(clock, CAPACITY); }

    NativeWriteTrace(Clock clock, int capacity) {
        if (capacity < 1 || capacity > CAPACITY) throw new IllegalArgumentException("capacity");
        this.clock = clock;
        this.capacity = capacity;
    }

    synchronized boolean start(String capture, String remote) {
        if (capture == null || !capture.matches("[0-9]{13,20}-[0-9a-f]{24}") ||
                remote == null || !remote.matches("[0-9A-F]{2}(:[0-9A-F]{2}){5}")) return false;
        if (captureId != null) return captureId.equals(capture) && remoteId.equals(remote);
        captureId = capture;
        remoteId = remote;
        origin = clock.nanos();
        epoch++;
        return true;
    }

    synchronized long entered() { return captureId == null ? 0 : clock.nanos(); }

    synchronized Entry begin(Object gatt, Object characteristic, String remote, byte[] bytes, long entered) {
        if (captureId == null || !remoteId.equals(remote)) return null;
        if (gatt == null || characteristic == null || bytes == null || bytes.length == 0 || entered < origin) {
            errors++;
            return null;
        }
        if (entries.size() == capacity || connections.size() == 64 && !connections.containsKey(gatt)) {
            overflow++;
            return null;
        }
        Integer connection = connections.get(gatt);
        if (connection == null) {
            connection = connections.size() + 1;
            connections.put(gatt, connection);
        }
        CRC32 crc = new CRC32();
        crc.update(bytes);
        Entry entry = new Entry(epoch, gatt, characteristic, new long[] {
            entries.size() + 1, connection, bytes.length, crc.getValue(), entered - origin,
            clock.nanos() - origin, -1, -1, -1, -1, -1});
        entries.add(entry);
        if (pending.containsKey(gatt)) {
            // Ambiguous writes must not be paired with an arbitrary callback.
            pending.put(gatt, null);
            errors++;
        } else {
            pending.put(gatt, entry);
        }
        return entry;
    }

    synchronized void returned(Entry entry, int result) {
        if (!current(entry)) return;
        if (entry.values[6] != -1) { errors++; return; }
        entry.values[6] = clock.nanos() - origin;
        entry.values[9] = result;
        if (result != 0 && pending.get(entry.gatt) == entry) pending.remove(entry.gatt);
    }

    synchronized Entry callback(Object gatt, Object characteristic, int status) {
        if (captureId == null || !connections.containsKey(gatt)) return null;
        Entry entry = pending.get(gatt);
        if (entry == null || entry.characteristic != characteristic) { errors++; return null; }
        pending.remove(gatt);
        entry.values[7] = clock.nanos() - origin;
        entry.values[10] = status;
        return entry;
    }

    synchronized void dispatched(Entry entry) {
        if (!current(entry)) return;
        if (entry.values[7] < 0 || entry.values[8] != -1) { errors++; return; }
        entry.values[8] = clock.nanos() - origin;
    }

    synchronized void disconnected(Object gatt) {
        pending.remove(gatt);
    }

    private boolean current(Entry entry) {
        return captureId != null && entry != null && entry.epoch == epoch;
    }

    synchronized Map<String, Object> snapshot(String capture, String remote) {
        if (captureId == null || !captureId.equals(capture) || !remoteId.equals(remote)) {
            throw new IllegalArgumentException("trace binding");
        }
        List<List<Long>> rows = new ArrayList<>();
        int incomplete = 0, apiErrors = 0, callbackErrors = 0;
        for (Entry entry : entries) {
            long[] v = entry.values;
            if (v[6] < 0 || v[9] == 0 && (v[7] < 0 || v[8] < 0)) incomplete++;
            if (v[6] >= 0 && v[9] != 0) apiErrors++;
            if (v[7] >= 0 && v[10] != 0) callbackErrors++;
            List<Long> row = new ArrayList<>();
            for (long value : v) row.add(value);
            rows.add(row);
        }
        Map<String, Object> result = new HashMap<>();
        result.put("schema", 1);
        result.put("captureId", captureId);
        result.put("remoteId", remoteId);
        result.put("clock", "System.nanoTime-relative-ns");
        result.put("snapshot", ++snapshots);
        result.put("capacity", capacity);
        result.put("sampleCount", entries.size());
        result.put("overflow", overflow);
        result.put("correlationErrors", errors);
        result.put("incomplete", incomplete);
        result.put("apiErrors", apiErrors);
        result.put("callbackErrors", callbackErrors);
        result.put("rows", rows);
        return result;
    }

    synchronized void clear() {
        captureId = null;
        remoteId = null;
        epoch++;
        entries.clear();
        connections.clear();
        pending.clear();
        overflow = errors = snapshots = 0;
    }

    synchronized boolean stop(String capture, String remote) {
        if (captureId == null || !captureId.equals(capture) || !remoteId.equals(remote)) return false;
        clear();
        return true;
    }
}
