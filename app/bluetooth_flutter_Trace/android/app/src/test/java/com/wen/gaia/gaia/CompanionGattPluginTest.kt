package com.wen.gaia.gaia

import android.Manifest
import android.app.Application
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.os.Looper
import com.lib.flutter_blue_plus.FlutterBluePlusPlugin
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowBluetoothGatt
import org.robolectric.util.ReflectionHelpers
import java.util.UUID

/** Real plugin admission, physical-GATT retirement and callback delivery under Android shadows. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], instrumentedPackages = ["io.flutter"])
class CompanionGattPluginTest {
    private lateinit var plugin: FlutterBluePlusPlugin
    private lateinit var app: Application
    private lateinit var messages: CompanionMessenger
    private val address = "AA:BB:CC:DD:EE:FF"
    private val attempt = "a".repeat(32)
    private val callback get() = ReflectionHelpers.getField<BluetoothGattCallback>(plugin, "mGattCallback")
    private val connected get() = gatts("mConnectedDevices")
    private val connecting get() = gatts("mCurrentlyConnectingDevices")

    private fun gatts(name: String): MutableMap<String, BluetoothGatt> = ReflectionHelpers.getField(plugin, name)
    private fun newGatt(): BluetoothGatt = ShadowBluetoothGatt.newInstance(
        app.getSystemService(BluetoothManager::class.java).adapter.getRemoteDevice(address))

    @Before fun setUp() {
        app = RuntimeEnvironment.getApplication()
        shadowOf(app).grantPermissions(Manifest.permission.BLUETOOTH, Manifest.permission.BLUETOOTH_CONNECT)
        shadowOf(app.getSystemService(BluetoothManager::class.java).adapter).setState(BluetoothAdapter.STATE_ON)
        plugin = FlutterBluePlusPlugin()
        messages = CompanionMessenger()
        ReflectionHelpers.setField(plugin, "context", app)
        ReflectionHelpers.setField(plugin, "methodChannel", MethodChannel(messages, "flutter_blue_plus/methods"))
    }

    private class Reply : MethodChannel.Result {
        var calls = 0
        var value: Any? = null
        var error: String? = null
        override fun success(result: Any?) { calls++; value = result }
        override fun error(code: String, message: String?, details: Any?) { calls++; error = code }
        override fun notImplemented() { calls++; error = "NOT_IMPLEMENTED" }
        fun success(): Any? { assertEquals(1, calls); assertNull(error); return value }
    }

    private fun invoke(method: String, id: String = attempt): Reply {
        val args = hashMapOf<String, Any>("remote_id" to address, "attempt" to id)
        if (method == "connect") { args["auto_connect"] = 0; args["companion_attempt"] = id }
        return Reply().also { plugin.onMethodCall(MethodCall(method, args), it) }
    }

    private fun begin(): BluetoothGatt {
        assertEquals(true, invoke("companionBegin").success())
        assertEquals(true, invoke("connect").success())
        return connecting.getValue(address)
    }

    @Test fun headlessConnectFinishesOnlyAfterPhysicalConnection() {
        val gatt = begin()
        assertEquals(false, invoke("companionFinish").success())
        callback.onConnectionStateChange(gatt, 0, BluetoothProfile.STATE_CONNECTED)
        shadowOf(Looper.getMainLooper()).idle()
        assertSame(gatt, connected[address])
        assertEquals(true, invoke("companionFinish").success())
        assertEquals(false, invoke("companionClose").success())
        assertFalse(shadowOf(gatt).isClosed)
        assertEquals(1, messages.sent.count { it.call.method == "OnConnectionStateChanged" })
    }

    @Test fun retiringAPendingAttemptClosesItsGattAndRejectsLateConnect() {
        val gatt = begin()
        assertEquals(mapOf("closed" to true, "replaced" to false), invoke("companionClose").success())
        assertTrue(shadowOf(gatt).isClosed)
        assertTrue(connecting.isEmpty())
        assertTrue(connected.isEmpty())
        assertEquals("companion", invoke("connect").error)
        callback.onConnectionStateChange(gatt, 0, BluetoothProfile.STATE_CONNECTED)
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(connected.isEmpty())
        assertEquals(1, messages.sent.count { it.call.method == "OnConnectionStateChanged" })
    }

    @Test fun oldRetirementAndCallbacksCannotCloseOrOverwriteAReplacement() {
        val old = begin()
        callback.onConnectionStateChange(old, 0, BluetoothProfile.STATE_CONNECTED)
        shadowOf(Looper.getMainLooper()).idle()
        messages.sent.clear()
        val replacement = newGatt()
        connected[address] = replacement
        val mtu = ReflectionHelpers.getField<MutableMap<String, Int>>(plugin, "mMtu")
        mtu[address] = 247
        assertEquals(mapOf("closed" to true, "replaced" to true), invoke("companionClose").success())
        callback.onConnectionStateChange(old, 0, BluetoothProfile.STATE_CONNECTED)
        callback.onConnectionStateChange(old, 133, BluetoothProfile.STATE_DISCONNECTED)
        callback.onMtuChanged(old, 23, 0)
        callback.onServicesDiscovered(old, 0)
        val service = BluetoothGattService(UUID.fromString("0000fff0-0000-1000-8000-00805f9b34fb"), 0)
        val characteristic = BluetoothGattCharacteristic(UUID.fromString("0000fff1-0000-1000-8000-00805f9b34fb"), 16, 1)
        val descriptor = BluetoothGattDescriptor(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"), 1)
        service.addCharacteristic(characteristic); characteristic.addDescriptor(descriptor)
        callback.onCharacteristicChanged(old, characteristic, byteArrayOf(1))
        callback.onCharacteristicWrite(old, characteristic, 0)
        callback.onDescriptorWrite(old, descriptor, 0)
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(shadowOf(old).isClosed)
        assertFalse(shadowOf(replacement).isClosed)
        assertSame(replacement, connected[address])
        assertEquals(247, mtu[address])
        assertTrue(messages.sent.isEmpty())
    }

    @Test fun alreadyQueuedCallbackIsFencedAgainAtDartDelivery() {
        val old = begin()
        callback.onConnectionStateChange(old, 0, BluetoothProfile.STATE_CONNECTED)
        callback.onServicesDiscovered(old, 0)
        val replacement = newGatt()
        connected[address] = replacement
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue(messages.sent.isEmpty())
        assertSame(replacement, connected[address])
    }

    @Test fun foreignAttemptCannotRetireTheCurrentGatt() {
        val gatt = begin()
        assertEquals(false, invoke("companionClose", "b".repeat(32)).success())
        assertFalse(shadowOf(gatt).isClosed)
        assertSame(gatt, connecting[address])
    }

    @Test fun connectionFailureRetainsTheActualControllerCodeUntilCleanup() {
        val gatt = begin()
        callback.onConnectionStateChange(gatt, 133, BluetoothProfile.STATE_DISCONNECTED)
        assertEquals(133, invoke("companionError").success())
        assertEquals(mapOf("closed" to true, "replaced" to false), invoke("companionClose").success())
        assertTrue(shadowOf(gatt).isClosed)
    }
}
