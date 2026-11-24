"""Host callback boundary for unchanged recovery C core, never a hardware entry."""
import ctypes
import hashlib
import time

from .probe import require

LOW, HIGH, LENGTH = 0x200000, 0x299000, 619580
PINNED = '7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf'
READ = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
                       ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32)
ERASE = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)


class IO(ctypes.Structure):
    _fields_ = [('ctx', ctypes.c_void_p), ('source', READ), ('read', READ),
                ('erase', ERASE), ('program', READ)]


def scope(address, size):
    require(type(address) is int and type(size) is int and
            LOW <= address < HIGH and 0 < size <= HIGH-address,
            'outside exact authorized recovery range')


class Guard:
    def __init__(self, port, source, *, seconds=1800, clock=time.monotonic):
        require(isinstance(source, bytes) and len(source) == LENGTH, 'exact immutable source length required')
        require(0 < seconds <= 13200, 'finite writer callback deadline required')
        self.port, self.source, self.seconds, self.clock = port, source, seconds, clock
        self.started, self.error, self.calls, self.mutations = clock(), None, 0, 0
        self.refs = [READ(lambda ctx, off, dst, n: self.invoke(self.source_read, off, dst, n)),
                     READ(lambda ctx, addr, dst, n: self.invoke(self.read, addr, dst, n)),
                     ERASE(lambda ctx, addr: self.invoke(self.erase, addr)),
                     READ(lambda ctx, addr, src, n: self.invoke(self.program, addr, src, n))]
        self.io = IO(None, *self.refs)

    def check(self):
        require(self.error is None, 'writer callback fault latched')
        require(0 <= self.clock()-self.started < self.seconds, 'writer callback deadline expired')

    def invoke(self, operation, *args):
        if self.error is not None: return -1
        try:
            self.check()
            self.calls += 1
            operation(*args)
            self.check()
            return 0
        except BaseException as error:
            self.error = type(error).__name__+': '+str(error)
            return -1

    def source_read(self, offset, destination, size):
        require(0 <= offset < LENGTH and 0 < size <= min(4096, LENGTH-offset), 'source read scope')
        ctypes.memmove(destination, self.source[offset:offset+size], size)

    def read(self, address, destination, size):
        scope(address, size)
        require(size <= 4096, 'bounded NOR read callback')
        data = self.port.read(address, size)
        require(isinstance(data, bytes) and len(data) == size, 'short/invalid NOR read')
        ctypes.memmove(destination, data, size)

    def erase(self, address):
        scope(address, 4096)
        require(address % 4096 == 0, 'unaligned NOR sector erase')
        self.mutations += 1
        require(self.port.erase(address) == 0, 'failed/uncertain NOR erase')

    def program(self, address, source, size):
        scope(address, size)
        require(size <= 256 and (address & 255)+size <= 256, 'NOR page crossing')
        require((LOW+4096 <= address and address+size <= LOW+4096+LENGTH) or
                (address == LOW and size == 28) or (address == LOW+28 and size == 4),
                'only payload, metadata then separate marker may be programmed')
        data = ctypes.string_at(source, size)
        self.mutations += 1
        require(self.port.program(address, data) == 0, 'failed/uncertain NOR program')


def bind(library):
    library.rr_host_workspace_size.argtypes = []
    library.rr_host_workspace_size.restype = ctypes.c_size_t
    library.rr_host_io_size.argtypes = []
    library.rr_host_io_size.restype = ctypes.c_size_t
    require(library.rr_host_workspace_size() == 12252 and library.rr_host_io_size() == ctypes.sizeof(IO),
            'host recovery ABI mismatch')
    function = library.rr_host_run
    function.argtypes = [ctypes.POINTER(IO), ctypes.c_uint32, ctypes.POINTER(ctypes.c_ubyte)]
    function.restype = ctypes.c_int
    return function


def run(function, port, source, **kwargs):
    require(hashlib.sha256(source).hexdigest() == PINNED, 'recovery source digest changed')
    guard = Guard(port, source, **kwargs)
    pinned = (ctypes.c_ubyte*32).from_buffer_copy(bytes.fromhex(PINNED))
    result = function(ctypes.byref(guard.io), len(source), pinned)
    try:
        guard.check()
    except BaseException as error:
        if guard.error is None: guard.error = type(error).__name__+': '+str(error)
    return dict(result='HOST_WRITER_CALLBACKS_COMPLETED' if result == 0 and guard.error is None else 'FAILED',
                native_result=result, callback_error=guard.error, callbacks=guard.calls,
                mutation_attempts=guard.mutations, elapsed_seconds=guard.clock()-guard.started,
                independent_physical_admission=False)
