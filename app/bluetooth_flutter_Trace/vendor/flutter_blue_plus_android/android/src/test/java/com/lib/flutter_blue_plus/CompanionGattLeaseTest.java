package com.lib.flutter_blue_plus;

public final class CompanionGattLeaseTest {
    private static int checks;
    private static void check(boolean value) {
        checks++;
        if (!value) throw new AssertionError("GATT lease check " + checks);
    }
    public static void main(String[] args) {
        Object old = new Object(), replacement = new Object();
        CompanionGattLease<Object> first = new CompanionGattLease<>("first", old);
        check(first.matches("first"));
        check(!first.matches("other"));
        check(first.bind("first", old));
        check(!first.bind("first", replacement));
        check(first.gatt() == old);
        check(!first.retire("other"));
        check(first.matches("first"));
        check(first.retire("first"));
        check(!first.matches("first"));
        check(!first.retire("first"));
        check(!first.bind("first", replacement));
        CompanionGattLease<Object> second = new CompanionGattLease<>("second", null);
        check(second.bind("second", replacement));
        check(!second.bind("first", old));
        check(second.gatt() == replacement);
        // Same remote address is insufficient: connection, discovery, descriptor,
        // write and delayed UI callbacks must all use physical object identity.
        check(!CompanionGattLease.current(old, replacement, null, null));
        check(!CompanionGattLease.current(old, null, replacement, null));
        check(!CompanionGattLease.current(old, null, null, replacement));
        check(CompanionGattLease.current(replacement, replacement, null, null));
        check(CompanionGattLease.current(replacement, null, replacement, null));
        check(CompanionGattLease.current(replacement, null, null, replacement));
        check(!CompanionGattLease.current(null, null, null, null));
        check(!CompanionGattLease.current(old, null, null, null));
        check(second.matches("second"));
        check(second.retire("second"));
        System.out.println("COMPANION_GATT_LEASE_TESTS_PASS " + checks);
    }
}
