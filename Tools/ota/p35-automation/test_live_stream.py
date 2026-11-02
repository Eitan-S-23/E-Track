"""Transport regression tests, synthetic inputs, no ADB or device execution."""
import hashlib
import io
import json
import struct
import socket
import sys
import uuid
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import live_stream as live
import runner as r
from test_runner import plan, state


def archive(count=100):
    rows = [dict(state(), seq=i+1, monoUs=i) for i in range(count)]
    cid = rows[0]['captureId']
    body = b''.join((r.PREFIX + json.dumps(row) + '\n').encode() for row in rows)
    header = ('OTA_P35_CAPTURE ' + json.dumps(dict(schema=1,kind='open',captureId=cid))+'\n').encode()
    footer = ('OTA_P35_CAPTURE ' + json.dumps(dict(schema=1,kind='close',captureId=cid,
        records=count,sha256=hashlib.sha256(body).hexdigest(),healthy=True,lost=0,error=None))+'\n').encode()
    return header, body, footer


class Peer:
    def __init__(self, frames):
        self.raw = b''.join(struct.pack('!I',len(frame))+frame for frame in frames)
        self.input = io.BytesIO(self.raw)
        self.acks = []
    def recv(self, n):
        return self.input.read(min(n,17))
    def sendall(self, data):
        self.acks.append(data)


class StreamTests(unittest.TestCase):
    def test_native_mirror_error_must_be_bound_to_exact_original(self):
        raw=b''.join(archive(3));line=raw.splitlines()[1]
        cid=state()['captureId']
        value=dict(schema=1,captureId=cid,source='diagnostic-only',status='FAILED_DISABLED',
                   errorType='AndroidLogWriteFailure',nativeResult=-11,expectedBytes=len(line)+9,
                   record=line.decode(),recordSha256=hashlib.sha256(line).hexdigest())
        self.assertEqual(r.audit_logcat_status(json.dumps(value).encode(),cid,raw),value)
        for changes in ({'captureId':'f'*32},{'recordSha256':'0'*64},{'record':'not an original'},
                        {'nativeResult':True},{'expectedBytes':0},{'expectedBytes':12},{'source':'live'},{'extra':1}):
            with self.assertRaises(r.Stop):r.audit_logcat_status(json.dumps(dict(value,**changes)).encode(),cid,raw)

    def test_no_native_error_does_not_claim_logcat_delivery(self):
        value=dict(schema=1,captureId=state()['captureId'],source='diagnostic-only',status='NO_NATIVE_ERROR_OBSERVED')
        self.assertEqual(r.audit_logcat_status(json.dumps(value).encode(),value['captureId'],b''),value)
        with self.assertRaises(r.Stop):r.audit_logcat_status(json.dumps(dict(value,missing=0)).encode(),value['captureId'],b'')

    def driver(self, data, *, running=True, exit_code=0):
        class File:
            def stat(self):return SimpleNamespace(st_size=len(data))
            def open(self, mode):return io.BytesIO(data)
        d=object.__new__(r.Android)
        d.capture=SimpleNamespace(alive=lambda:True,paths={'stdout':None})
        d.server=SimpleNamespace(alive=lambda:True)
        d.stream_port=5193
        d.stream_capture=SimpleNamespace(alive=lambda:running,paths={'stdout':File()},
                                        process=SimpleNamespace(poll=lambda:exit_code))
        d.decoder=r.Decoder();d.offset=0;d.queue=deque();d.preparation=None
        d.p=plan();d.last_state_at=None
        return d

    def test_real_runner_pump_uses_stream_not_diagnostic_logcat(self):
        raw=b''.join(archive(3))
        d=self.driver(raw,running=False)
        d._pump_logcat()
        self.assertEqual([x['seq'] for x in d.queue],[1,2,3])
        self.assertEqual(d.offset,len(raw))
        self.assertIsNotNone(d.last_state_at)

    def test_real_runner_pump_rejects_early_close_and_gap_without_fallback(self):
        head,body,foot=archive(3)
        for raw in (head+body,head+body.splitlines(keepends=True)[0]+body.splitlines(keepends=True)[2]+foot):
            d=self.driver(raw,running=False)
            with self.assertRaises(r.Stop):d._pump_logcat()
        d=self.driver(head+body+foot,running=False,exit_code=1)
        with self.assertRaises(r.Stop):d._pump_logcat()

    def test_forward_and_collector_start_are_explicit_single_use(self):
        d=object.__new__(r.Android)
        d.stream_port=5193;d.stream_capture=None;d.p=plan();d.preparation=SimpleNamespace()
        calls=[]
        d.record=lambda *a,**k:None
        d.h=SimpleNamespace(listening=lambda port:False,checked=lambda path:path,
            Process=lambda *a:SimpleNamespace(alive=lambda:True))
        def cmd(argv):
            calls.append(argv)
            return ('%s tcp:5193 tcp:49135\n'%d.p['phone']['serial']).encode()
        d.cmd=cmd;d.out=Path('synthetic');d.env={}
        d.prepare_live_stream();d.start_live_stream()
        self.assertEqual(calls[0],['forward','--no-rebind','tcp:5193','tcp:49135'])
        self.assertEqual(d.preparation.observation_source,'acknowledged-stream-v1')
        with self.assertRaises(r.Stop):d.start_live_stream()

    def test_fragmented_frames_are_preserved_before_ack(self):
        frames = archive(6000)
        # Actual wire batches are bounded, independently of original file size.
        lines = frames[1].splitlines(keepends=True)
        frames = [frames[0]] + [b''.join(lines[i:i+20]) for i in range(0,len(lines),20)] + [frames[2]]
        peer, sink, wire = Peer(frames), io.BytesIO(), io.BytesIO()
        synced = []
        def sync():
            self.assertEqual(len(peer.acks),len(synced))
            synced.append(len(sink.getvalue()))
        result = live.receive(peer,sink,sync=sync,wire=wire)
        self.assertEqual(result['records'],6000)
        self.assertEqual(sink.getvalue(),b''.join(frames))
        self.assertEqual(wire.getvalue(),peer.raw)
        self.assertEqual(len(synced),len(frames))
        for frame,ack in zip(frames,peer.acks):
            self.assertEqual(ack,('ACK %d %s\n'%(len(frame),hashlib.sha256(frame).hexdigest())).encode())

    def test_gap_reorder_replay_wrong_hash_and_identity_reject(self):
        head,body,foot=archive(3)
        lines=body.splitlines(keepends=True)
        for frames in ((head,lines[0]+lines[2],foot), (head,lines[1]+lines[0],foot),
                       (head,lines[0]+lines[0],foot), (head,body,foot.replace(b'"healthy": true',b'"healthy": false')),
                       (head,body,foot.replace(hashlib.sha256(body).hexdigest().encode(),b'0'*64)),
                       (head,body.replace(b'"captureId": "',b'"captureId": "f'),foot)):
            with self.subTest(frames=frames[-1][:30]):
                peer=Peer(frames)
                with self.assertRaises(r.Stop):live.receive(peer,io.BytesIO())
                self.assertLess(len(peer.acks),len(frames))

    def test_short_frame_and_unbounded_length_preserve_wire_without_ack(self):
        for raw in (struct.pack('!I',12)+b'bad',struct.pack('!I',live.MAX_BATCH+1)):
            peer=Peer([]);peer.input=io.BytesIO(raw);wire=io.BytesIO()
            with self.assertRaises(r.Stop):live.receive(peer,io.BytesIO(),wire=wire)
            self.assertEqual(wire.getvalue(),raw)
            self.assertEqual(peer.acks,[])

    def test_disk_failure_is_not_acknowledged(self):
        peer=Peer(archive())
        def sync():raise OSError('synthetic disk failure')
        with self.assertRaises(OSError):live.receive(peer,io.BytesIO(),sync=sync)
        self.assertEqual(peer.acks,[])

    def test_plan_requires_explicit_matching_control_and_test_package(self):
        p=plan()
        p['preparation']=dict(log_buffer='events',live_stream_port=5193)
        with self.assertRaises(r.Stop):r.validate_plan(p)
        p['ui']['arm']={'resource-id':'p35-arm-stream'}
        p['app']['id']='test.app.p35acceptance'
        r.validate_plan(p)
        for port in (True,5037,p['phone']['adb_port'],65536):
            p['preparation']['live_stream_port']=port
            with self.assertRaises(r.Stop):r.validate_plan(p)


class RealWorkerTests(unittest.TestCase):
    def run_worker(self, complete):
        h=r.load_host()
        out=h.checked(r.ROOT/'.cache/p35-stream-host-tests'/uuid.uuid4().hex)
        for n in ('worker.stdout','worker.stderr','worker.started.json','worker.closed.json','wire.bin','expected.jsonl','host'):
            h.checked(out/n)
        h.fresh(out)
        env=h.environment(out)
        frames=list(archive(100))
        if not complete:frames=frames[:2]
        h.raw(out/'expected.jsonl',b''.join(frames))
        worker=None
        with socket.socket() as server:
            server.bind(('127.0.0.1',0));server.listen(1);server.settimeout(5)
            try:
                worker=h.Process(out,'worker',[sys.executable,'-I','-S','-B','-u','-X','utf8',
                    str(r.ROOT/'Tools/ota/p35-automation/live_stream.py'),'--port',str(server.getsockname()[1]),
                    '--wire-out',str(out/'wire.bin')],env)
                peer,_=server.accept()
                with peer:
                    peer.settimeout(5)
                    for data in frames:
                        peer.sendall(struct.pack('!I',len(data))+data)
                        wanted=('ACK %d %s\n'%(len(data),hashlib.sha256(data).hexdigest())).encode()
                        self.assertEqual(live.exact(peer,len(wanted)),wanted)
                h.wait_for(lambda:not worker.alive(),5)
                self.assertEqual(worker.process.returncode==0,complete)
            finally:
                if worker:worker.close('test-finished')
        self.assertEqual((out/'worker.stdout').read_bytes(),b''.join(frames))
        self.assertEqual((out/'wire.bin').read_bytes(),b''.join(struct.pack('!I',len(x))+x for x in frames))

    def test_actual_process_persists_and_acks_then_exits_after_footer(self):self.run_worker(True)
    def test_actual_process_rejects_eof_without_footer(self):self.run_worker(False)


if __name__ == '__main__':unittest.main()
