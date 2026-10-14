package com.lib.flutter_blue_plus;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

public final class NativeWriteTraceTest {
    private static final String CAPTURE = "1791437508254294-28859c8670dc4095b0eae5c2";
    private static final String REMOTE = "E3:49:E1:14:D6:CB";
    private static int checks;

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("check " + (checks + 1));
        checks++;
    }

    private static int count(Map<String, Object> snapshot, String name) {
        return (Integer) snapshot.get(name);
    }

    private static List<?> row(Map<String, Object> snapshot, int index) {
        return (List<?>) ((List<?>) snapshot.get("rows")).get(index);
    }

    public static void main(String[] args) {
        AtomicLong clock = new AtomicLong(1000);
        NativeWriteTrace trace = new NativeWriteTrace(clock::get, 3);
        Object gatt = new Object(), characteristic = new Object();
        byte[] bytes = new byte[] {1, 2, 3};
        check(trace.entered() == 0 && trace.begin(gatt, characteristic, REMOTE, bytes, 0) == null);
        check(!trace.start("bad", REMOTE) && !trace.start(CAPTURE, "other"));
        check(trace.start(CAPTURE, REMOTE) && trace.start(CAPTURE, REMOTE));
        check(!trace.start(CAPTURE, "E3:49:E1:14:D6:CC"));
        check(trace.begin(gatt, characteristic, "E3:49:E1:14:D6:CC", bytes, trace.entered()) == null);
        clock.set(1100);
        NativeWriteTrace.Entry first = trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered());
        clock.set(1200);
        trace.returned(first, 0);
        clock.set(1300);
        check(trace.callback(gatt, characteristic, 0) == first);
        clock.set(1400);
        trace.dispatched(first);
        Map<String, Object> snapshot = trace.snapshot(CAPTURE, REMOTE);
        check(count(snapshot, "sampleCount") == 1 && count(snapshot, "incomplete") == 0);
        check(row(snapshot, 0).equals(java.util.Arrays.asList(1L, 1L, 3L, 1438416925L,
            100L, 100L, 200L, 300L, 400L, 0L, 0L)));
        try { trace.snapshot(CAPTURE, "E3:49:E1:14:D6:CC"); throw new AssertionError("binding"); }
        catch (IllegalArgumentException expected) { checks++; }

        // Android can callback before the synchronous API returns.
        NativeWriteTrace.Entry early = trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered());
        clock.set(1500);
        trace.callback(gatt, characteristic, 0);
        clock.set(1600);
        trace.returned(early, 0);
        clock.set(1700);
        trace.dispatched(early);
        check(count(trace.snapshot(CAPTURE, REMOTE), "incomplete") == 0);
        check(row(snapshot, 0).get(8).equals(400L));
        NativeWriteTrace.Entry failed = trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered());
        trace.returned(failed, 201);
        snapshot = trace.snapshot(CAPTURE, REMOTE);
        check(count(snapshot, "apiErrors") == 1 && count(snapshot, "incomplete") == 0);
        check(trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered()) == null);
        check(count(trace.snapshot(CAPTURE, REMOTE), "overflow") == 1);

        trace.clear();
        trace.start(CAPTURE, REMOTE);
        trace.dispatched(first);
        check(count(trace.snapshot(CAPTURE, REMOTE), "sampleCount") == 0);
        NativeWriteTrace.Entry missing = trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered());
        trace.returned(missing, 0);
        trace.disconnected(gatt);
        check(count(trace.snapshot(CAPTURE, REMOTE), "incomplete") == 1);
        Object nextGatt = new Object();
        NativeWriteTrace.Entry next = trace.begin(nextGatt, characteristic, REMOTE, bytes, trace.entered());
        check(trace.callback(gatt, characteristic, 0) == null);
        trace.returned(next, 0);
        check(trace.callback(nextGatt, new Object(), 0) == null);
        check(trace.callback(nextGatt, characteristic, 5) == next);
        trace.dispatched(next);
        snapshot = trace.snapshot(CAPTURE, REMOTE);
        check(row(snapshot, 1).get(1).equals(2L) && count(snapshot, "callbackErrors") == 1);
        check(count(snapshot, "correlationErrors") == 2);

        trace.clear();
        trace.start(CAPTURE, REMOTE);
        trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered());
        trace.begin(gatt, characteristic, REMOTE, bytes, trace.entered());
        check(trace.callback(gatt, characteristic, 0) == null);
        check(count(trace.snapshot(CAPTURE, REMOTE), "incomplete") == 2);
        check(count(trace.snapshot(CAPTURE, REMOTE), "correlationErrors") == 2);
        check(!trace.stop(CAPTURE, "E3:49:E1:14:D6:CC"));
        check(count(trace.snapshot(CAPTURE, REMOTE), "sampleCount") == 2);
        check(trace.stop(CAPTURE, REMOTE) && trace.entered() == 0);
        System.out.println("NATIVE_WRITE_TRACE_TESTS_PASS " + checks);
    }
}
