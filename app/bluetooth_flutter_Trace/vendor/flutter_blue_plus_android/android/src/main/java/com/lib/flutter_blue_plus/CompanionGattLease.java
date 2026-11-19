package com.lib.flutter_blue_plus;

/** Attempt identity and physical GATT identity are separate fences. */
final class CompanionGattLease<T> {
    final String attempt;
    private T gatt;
    private boolean retired;
    int errorCode;

    CompanionGattLease(String attempt, T current) {
        this.attempt = attempt;
        this.gatt = current;
    }

    boolean matches(String id) { return !retired && attempt.equals(id); }
    T gatt() { return gatt; }
    boolean bind(String id, T next) {
        if (!matches(id) || (gatt != null && gatt != next)) return false;
        gatt = next;
        return true;
    }
    boolean retire(String id) {
        if (!matches(id)) return false;
        retired = true;
        return true;
    }
    static boolean current(Object gatt, Object connecting, Object connected, Object automatic) {
        return gatt != null && (gatt == connecting || gatt == connected || gatt == automatic);
    }
}
