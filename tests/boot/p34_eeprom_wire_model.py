"""I2C slave model driven by actual master edges; no precomputed response script."""


class Clock:
    def __init__(self):
        self.value = 0.

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class Slave:
    def __init__(self, clock, data):
        self.clock = clock
        self.data = bytearray(data)
        self.level = {6: 1, 7: 1}
        self.mode = 'idle'
        self.byte = self.bits = self.pointer = 0
        self.segment = []
        self.segments = []
        self.edges = []
        self.samples = []
        self.master_acks = []
        self.starts = self.stops = self.byte_count = 0
        self.fail_edge = None
        self.nack_byte = None
        self.busy_until = 0.
        self.protected = False
        self.prefix = None
        self.ack = True

    def physical(self, pin):
        if pin == 6:
            return self.level[6]
        slave = 1
        if self.mode == 'tx_ack':
            slave = int(not self.ack)
        elif self.mode == 'rx':
            slave = (self.data[self.pointer] >> (7-self.bits)) & 1
        return self.level[7] & slave

    def read(self, pin):
        self.samples.append((pin, self.physical(pin)))
        return self.physical(pin)

    def verify_idle(self):
        if self.level != {6: 1, 7: 1} or self.physical(7) != 1:
            raise ValueError('model bus not idle')

    def set(self, pin, high):
        previous = self.level[pin]
        self.level[pin] = high
        self.edges.append((pin, high))
        if pin == 7 and self.level[6] and previous != high:
            if high == 0:
                self.starts += 1
                if self.segment:
                    self.segments.append(tuple(self.segment))
                self.segment = []
                self.mode = 'tx'
                self.byte = self.bits = 0
            else:
                self.stops += 1
                self.segments.append(tuple(self.segment))
                if len(self.segment) >= 3 and self.segment[0] == 0xa0:
                    address, payload = self.segment[1], bytes(self.segment[2:])
                    if not self.protected:
                        take = len(payload) if self.prefix is None else min(self.prefix, len(payload))
                        for i in range(take):
                            self.data[(address & ~7) | ((address+i) & 7)] = payload[i]
                    self.busy_until = self.clock()+.005
                self.segment = []
                self.mode = 'idle'
        elif pin == 6 and previous != high:
            if high:
                if self.mode == 'tx':
                    self.byte = (self.byte << 1) | self.level[7]
                    self.bits += 1
                    if self.bits == 8:
                        self.byte_count += 1
                        self.ack = self.byte_count != self.nack_byte and self.clock() >= self.busy_until
                        if not self.segment:
                            self.ack &= self.byte in (0xa0, 0xa1)
                        self.segment.append(self.byte)
                        if len(self.segment) == 2 and self.segment[0] == 0xa0:
                            self.pointer = self.byte
                elif self.mode == 'rx_ack':
                    self.master_acks.append(self.level[7])
            else:
                if self.mode == 'tx' and self.bits == 8:
                    self.mode = 'tx_ack'
                elif self.mode == 'tx_ack':
                    if not self.ack:
                        self.mode = 'await_stop'
                    elif self.segment[0] == 0xa1:
                        self.mode = 'rx'
                        self.bits = 0
                    else:
                        self.mode = 'tx'
                        self.byte = self.bits = 0
                elif self.mode == 'rx':
                    self.bits += 1
                    if self.bits == 8:
                        self.mode = 'rx_ack'
                elif self.mode == 'rx_ack':
                    self.pointer = (self.pointer+1) & 255
                    self.bits = 0
                    self.mode = 'await_stop' if self.master_acks[-1] else 'rx'
        if len(self.edges) == self.fail_edge:
            raise OSError('delivered GPIO edge returned failure')
