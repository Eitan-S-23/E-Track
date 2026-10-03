package com.lib.flutter_blue_plus;

import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.WeakHashMap;

/** One bounded observation per GATT object; Android callbacks have no request ID. */
final class PhyProbe {
    interface Actions { void read(); void prefer2m(); }
    interface Listener { void complete(Map<String, Object> value); }
    interface Scheduler { Runnable after(long milliseconds, Runnable task); }
    interface Clock { long nanos(); }

    private final IdentityHashMap<Object, Long> connections = new IdentityHashMap<>();
    // BluetoothGatt inherits identity equality. Weak keys do not retain closed GATTs.
    private final WeakHashMap<Object, Boolean> spent = new WeakHashMap<>();
    private final IdentityHashMap<Object, Pending> pending = new IdentityHashMap<>();
    private final Scheduler scheduler;
    private final Clock clock;
    private long nextGeneration;
    static final long TIMEOUT_MS = 4000;

    private static final class Pending {
        final Object gatt;
        final Actions actions;
        final Listener listener;
        final Map<String, Object> value = new HashMap<>();
        final long started;
        final boolean prefer;
        int stage;
        Runnable cancel = () -> {};
        Pending(Object gatt, Actions actions, Listener listener, long started, boolean prefer) {
            this.gatt = gatt;
            this.actions = actions;
            this.listener = listener;
            this.started = started;
            this.prefer = prefer;
        }
    }

    PhyProbe(Scheduler scheduler, Clock clock) {
        this.scheduler = scheduler;
        this.clock = clock;
    }

    synchronized void connected(Object gatt) {
        if (!connections.containsKey(gatt)) connections.put(gatt, ++nextGeneration);
    }

    synchronized boolean current(Object gatt, long generation) {
        Long actual = connections.get(gatt);
        return actual != null && actual == generation;
    }

    synchronized void disconnected(Object gatt) {
        connections.remove(gatt);
        finish(pending.get(gatt), "disconnected");
    }

    synchronized void clear() {
        connections.clear();
        for (Pending item : pending.values().toArray(new Pending[0])) finish(item, "disconnected");
        // Do not clear spent: a late callback must not satisfy a reused GATT object.
    }

    synchronized void start(Object gatt, String remote, String request, boolean prefer,
                            Actions actions, Listener listener) {
        if (!connections.containsKey(gatt)) throw new IllegalStateException("disconnected");
        if (spent.containsKey(gatt)) throw new IllegalStateException("gatt-already-observed");
        spent.put(gatt, true);
        Pending item = new Pending(gatt, actions, listener, clock.nanos(), prefer);
        item.value.put("schema", 1);
        item.value.put("remoteId", remote);
        item.value.put("requestId", request);
        item.value.put("connectionGeneration", connections.get(gatt));
        item.value.put("policy", prefer ? "prefer2m" : "observe");
        pending.put(gatt, item);
        item.cancel = scheduler.after(TIMEOUT_MS, () -> timeout(item));
        invoke(item, actions::read);
    }

    private synchronized void timeout(Pending item) {
        if (pending.get(item.gatt) == item) finish(item, "timeout");
    }

    private Pending active(Object gatt, int stage) {
        Pending item = pending.get(gatt);
        if (item != null && clock.nanos() - item.started >= TIMEOUT_MS * 1000000L) {
            finish(item, "timeout");
            return null;
        }
        return item != null && item.stage == stage && connections.containsKey(gatt) ? item : null;
    }

    synchronized void read(Object gatt, int tx, int rx, int status) {
        Pending item = active(gatt, 0);
        boolean before = item != null;
        if (item == null) item = active(gatt, 2);
        if (item == null) return;
        item.value.put(before ? "beforeReadStatus" : "readStatus", status);
        if (status != 0) { finish(item, "read-failed"); return; }
        if (!valid(tx) || !valid(rx)) { finish(item, "invalid-phy"); return; }
        item.value.put(before ? "beforeTxPhy" : "txPhy", tx);
        item.value.put(before ? "beforeRxPhy" : "rxPhy", rx);
        if (before && item.prefer) {
            item.stage = 1;
            invoke(item, item.actions::prefer2m);
        } else {
            if (before) {
                item.value.put("txPhy", tx);
                item.value.put("rxPhy", rx);
            }
            finish(item, "observed");
        }
    }

    synchronized void update(Object gatt, int tx, int rx, int status) {
        Pending item = active(gatt, 1);
        if (item == null) return;
        item.value.put("updateStatus", status);
        if (status != 0) { finish(item, "update-failed"); return; }
        if (!valid(tx) || !valid(rx)) { finish(item, "invalid-phy"); return; }
        item.value.put("updateTxPhy", tx);
        item.value.put("updateRxPhy", rx);
        item.stage = 2;
        invoke(item, item.actions::read);
    }

    private static boolean valid(int phy) { return phy >= 1 && phy <= 3; }

    private void invoke(Pending item, Runnable action) {
        try { action.run(); }
        catch (RuntimeException error) { finish(item, "native-call-failed"); }
    }

    private void finish(Pending item, String status) {
        if (item == null || pending.get(item.gatt) != item) return;
        pending.remove(item.gatt);
        item.cancel.run();
        item.value.put("status", status);
        item.value.put("elapsedMicros", (clock.nanos() - item.started) / 1000L);
        item.listener.complete(new HashMap<>(item.value));
    }
}
