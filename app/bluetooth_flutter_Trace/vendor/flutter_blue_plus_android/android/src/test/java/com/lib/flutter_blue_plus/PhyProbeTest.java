package com.lib.flutter_blue_plus;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Executable host regression without Android, Gradle, mocks or JUnit downloads. */
public final class PhyProbeTest {
    private static int assertions;
    private static void check(boolean value) {
        assertions++;
        if (!value) throw new AssertionError("assertion " + assertions);
    }
    private static final class Fixture implements PhyProbe.Actions {
        long now;
        int reads, preferences, cancelled;
        boolean throwRead, throwPrefer;
        Runnable timeout;
        final List<Map<String, Object>> results = new ArrayList<>();
        final Object gatt = new Object();
        final PhyProbe probe = new PhyProbe((delay, task) -> {
            check(delay == 4000);
            timeout = task;
            return () -> cancelled++;
        }, () -> now);
        Fixture() { probe.connected(gatt); }
        public void read() { reads++; if (throwRead) throw new SecurityException(); }
        public void prefer2m() { preferences++; if (throwPrefer) throw new SecurityException(); }
        void start(boolean prefer) { probe.start(gatt, "AA:BB:CC:DD:EE:FF", "trial-1", prefer, this, results::add); }
        void read(int tx, int rx, int status) { probe.read(gatt, tx, rx, status); }
        void update(int tx, int rx, int status) { probe.update(gatt, tx, rx, status); }
        Map<String, Object> result(String status) {
            check(results.size() == 1);
            check(status.equals(results.get(0).get("status")));
            check(cancelled == 1);
            return results.get(0);
        }
        void rejectsReplay() {
            try { start(false); throw new AssertionError("accepted reused GATT"); }
            catch (IllegalStateException expected) { check(true); }
        }
    }
    public static void main(String[] args) {
        Fixture observe = new Fixture();
        observe.start(false);
        observe.update(2, 2, 0);
        check(observe.results.isEmpty());
        observe.read(1, 2, 0);
        Map<String, Object> actual = observe.result("observed");
        check(actual.get("txPhy").equals(1) && actual.get("rxPhy").equals(2));
        check(observe.preferences == 0 && observe.reads == 1);
        observe.rejectsReplay();
        observe.timeout.run();
        observe.read(2, 2, 0);
        check(observe.results.size() == 1);

        for (int finalPhy : new int[]{1, 2, 3}) {
            Fixture prefer = new Fixture();
            prefer.start(true);
            prefer.probe.read(new Object(), 2, 2, 0);
            check(prefer.preferences == 0);
            prefer.read(1, 1, 0);
            check(prefer.preferences == 1 && prefer.results.isEmpty());
            prefer.read(2, 2, 0); // Wrong callback kind while awaiting the update.
            check(prefer.results.isEmpty());
            prefer.update(2, 2, 0);
            check(prefer.reads == 2 && prefer.results.isEmpty());
            prefer.read(finalPhy, finalPhy, 0);
            actual = prefer.result("observed");
            check(actual.get("txPhy").equals(finalPhy));
            check(actual.get("beforeTxPhy").equals(1));
            check(actual.get("updateTxPhy").equals(2));
            prefer.rejectsReplay();
        }

        for (int phase = 0; phase < 3; phase++) {
            for (String failure : new String[]{"timeout", "disconnect", "clear"}) {
                Fixture f = new Fixture();
                f.start(true);
                if (phase >= 1) f.read(1, 1, 0);
                if (phase == 2) f.update(2, 2, 0);
                if (failure.equals("timeout")) { f.now = 4000000000L; f.timeout.run(); }
                else if (failure.equals("disconnect")) f.probe.disconnected(f.gatt);
                else f.probe.clear();
                actual = f.result(failure.equals("timeout") ? "timeout" : "disconnected");
                f.read(2, 2, 0);
                f.update(2, 2, 0);
                check(f.results.size() == 1);
                f.probe.connected(f.gatt);
                f.rejectsReplay();
                Object next = new Object();
                f.probe.connected(next);
                f.probe.start(next, "AA:BB:CC:DD:EE:FF", "trial-2", false, f, f.results::add);
                f.read(2, 2, 0);
                check(f.results.size() == 1);
                f.probe.read(next, 1, 1, 0);
                check(f.results.size() == 2);
            }
        }
        Fixture expired = new Fixture();
        expired.start(true);
        expired.now = 4000000001L; // Deadline enforced even if main-loop timer is delayed.
        expired.read(1, 1, 0);
        expired.result("timeout");
        check(expired.preferences == 0);
        for (int stage = 0; stage < 3; stage++) {
            Fixture f = new Fixture();
            f.start(true);
            if (stage > 0) f.read(1, 1, 0);
            if (stage == 2) f.update(2, 2, 0);
            if (stage == 1) f.update(2, 2, 7); else f.read(2, 2, 7);
            actual = f.result(stage == 1 ? "update-failed" : "read-failed");
            check(!actual.containsKey("txPhy"));
        }
        for (int invalid : new int[]{0, 4, -1}) {
            Fixture f = new Fixture();
            f.start(false); f.read(invalid, 1, 0); f.result("invalid-phy");
        }
        for (boolean atRead : new boolean[]{true, false}) {
            Fixture f = new Fixture();
            f.throwRead = atRead; f.throwPrefer = !atRead;
            f.start(true);
            if (!atRead) f.read(1, 1, 0);
            f.result("native-call-failed");
        }
        Fixture generation = new Fixture();
        generation.start(false); generation.read(1, 1, 0);
        long token = ((Number) generation.result("observed").get("connectionGeneration")).longValue();
        check(generation.probe.current(generation.gatt, token));
        generation.probe.disconnected(generation.gatt);
        check(!generation.probe.current(generation.gatt, token));
        generation.probe.connected(generation.gatt);
        check(!generation.probe.current(generation.gatt, token));
        System.out.println("PHY_NATIVE_PASS assertions=" + assertions);
    }
}
