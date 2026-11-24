"""Minimal V8.18 ctypes adapter; no write/reset/halt/power function is bound."""
import ctypes
import os
import threading

from .probe import BEFORE_CONNECT, BEFORE_OPEN, read_allowed, require


DLL_SHA = "6b6f7f15c0f3dfe93c985e14dc6e7e3efa47ad563579def9370602a019873908"
SETTINGS = frozenset((*BEFORE_OPEN, *BEFORE_CONNECT, "SetEnableMemCache = 0", "InvalidateCache"))


def guarded(function, *args, seconds=5):
    """A stuck DLL kills only this owned worker, leaving the operation uncertain."""
    def abort():
        os.write(2, b"NATIVE_CALL_TIMEOUT: worker terminated, outcome uncertain\n")
        os._exit(124)
    timer = threading.Timer(seconds, abort)
    timer.daemon = True
    timer.start()
    try:
        return function(*args)
    finally:
        timer.cancel()


class ConnectInfo(ctypes.Structure):
    _fields_ = [("SerialNumber", ctypes.c_uint32), ("Connection", ctypes.c_ubyte),
        ("USBAddr", ctypes.c_uint32), ("aIPAddr", ctypes.c_uint8 * 16),
        ("Time", ctypes.c_int), ("Time_us", ctypes.c_uint64), ("HWVersion", ctypes.c_uint32),
        ("abMACAddr", ctypes.c_uint8 * 6), ("acProduct", ctypes.c_char * 32),
        ("acNickname", ctypes.c_char * 32), ("acFWString", ctypes.c_char * 112),
        ("IsDHCPAssignedIP", ctypes.c_char), ("IsDHCPAssignedIPIsValid", ctypes.c_char),
        ("NumIPConnections", ctypes.c_char), ("NumIPConnectionsIsValid", ctypes.c_char),
        ("aPadding", ctypes.c_uint8 * 34)]


class Native:
    def __init__(self, sdk, log, project, callback_stream):
        self.sdk, self.callback_error = sdk, None
        self._opened = False
        self.close_returned = False
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        def callback(data):
            try:
                if data:
                    callback_stream.write(data + b"\n")
                    callback_stream.flush()
            except BaseException as error:
                self.callback_error = error
        self.callback = callback_type(callback)
        signatures = {
            "JLINKARM_ExecCommand": ([ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
            "JLINKARM_SetLogFile": ([ctypes.c_char_p], None),
            "JLINKARM_EMU_GetList": ([ctypes.c_int, ctypes.POINTER(ConnectInfo), ctypes.c_int], ctypes.c_int),
            "JLINKARM_EMU_SelectByUSBSN": ([ctypes.c_uint32], ctypes.c_int),
            "JLINKARM_OpenEx": ([callback_type, callback_type], ctypes.c_char_p),
            "JLINKARM_Close": ([], None), "JLINKARM_GetSN": ([], ctypes.c_uint32),
            "JLINKARM_IsConnected": ([], ctypes.c_int),
            "JLINKARM_TIF_Select": ([ctypes.c_int], ctypes.c_int),
            "JLINKARM_SetSpeed": ([ctypes.c_uint32], None),
            "JLINKARM_Connect": ([], ctypes.c_int),
            "JLINKARM_ReadMemEx": ([ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_ubyte], ctypes.c_int),
        }
        for name, (args, result) in signatures.items():
            function = getattr(sdk, name)
            function.argtypes, function.restype = args, result
        self._call("JLINKARM_SetLogFile", str(log).encode("ascii"))
        # Caller preflights a fresh project path before loading the DLL.
        rc, message = self._exec("ProjectFile = " + str(project))
        require(rc == 0 and message == "", "SDK project redirection failed")

    def _call(self, name, *args):
        require(self.callback_error is None, "SDK callback evidence failed")
        value = guarded(getattr(self.sdk, name), *args)
        require(self.callback_error is None, "SDK callback evidence failed")
        return value

    def _exec(self, value):
        error = ctypes.create_string_buffer(1024)
        result = self._call("JLINKARM_ExecCommand", value.encode("ascii"), error, len(error))
        return result, error.value.decode("ascii", errors="replace")

    def command(self, value):
        require(value in SETTINGS, "unlisted native setting")
        return self._exec(value)

    def select(self, serial):
        require(serial == 123456, "wrong probe serial")
        infos = (ConnectInfo * 4)()
        count = self._call("JLINKARM_EMU_GetList", 1, infos, 4)
        require(count == 1 and infos[0].SerialNumber == serial and infos[0].Connection == 1,
                "SDK USB identity mismatch")
        return self._call("JLINKARM_EMU_SelectByUSBSN", serial)

    def open(self):
        self._opened = True
        result = self._call("JLINKARM_OpenEx", self.callback, self.callback)
        if result is None:
            require(self._call("JLINKARM_GetSN") in (123456, 0xffffffff), "firmware probe serial mismatch")
        return result

    def connected(self): return self._call("JLINKARM_IsConnected")
    def interface(self, value):
        require(value == 1, "SWD only")
        return self._call("JLINKARM_TIF_Select", value)
    def speed(self, value):
        require(value == 1000, "1000kHz only")
        return self._call("JLINKARM_SetSpeed", value)
    def connect(self): return self._call("JLINKARM_Connect")

    def read(self, address, size):
        require(read_allowed(address, size), "native read outside scope")
        buffer = ctypes.create_string_buffer(size)
        rc = self._call("JLINKARM_ReadMemEx", address, size, buffer, 0)
        require(rc == size, "short native read")
        return buffer.raw

    def close(self):
        if self._opened:
            self._opened = False
            # A broken callback log must not suppress the native close attempt.
            guarded(self.sdk.JLINKARM_Close)
            self.close_returned = True
