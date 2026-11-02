"""Archive boundary and strict positional regressions, no physical operations."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import original as v
import supplement as s
import store
import evaluate


def packet(files, objects, extra=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('index.json',json.dumps(dict(schema='p35-local-evidence-packet-v1',files=files)))
        for name,data in objects.items():z.writestr('objects/'+name,data)
        if extra:z.writestr(extra,b'x')
    return out.getvalue()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.data=b'original'
        self.row=dict(bytes=len(self.data),sha256=store.sha(self.data))

    def test_exact_aliases_and_glob(self):
        archive=store.Store(packet({'a/b.txt':self.row,'a\\c.txt':self.row},
                                  {self.row['sha256']:self.data}),v.ROOT)
        self.assertEqual(archive.read(v.ROOT/'a/b.txt'),self.data)
        self.assertEqual(archive.verify()['objects'],1)
        self.assertEqual(len(archive.glob(v.ROOT/'a','*.txt')),2)
        self.assertEqual(archive.children(v.ROOT/'a'),[v.ROOT/'a/b.txt',v.ROOT/'a/c.txt'])
        self.assertFalse(archive.exists(v.ROOT/'a/missing'))

    def test_traversal_and_absolute_paths(self):
        for name in ('../x','a/../../x','/x','D:/x','a/../x'):
            with self.subTest(name=name), self.assertRaises(ValueError):store.relative(name)

    def test_unindexed_member(self):
        with self.assertRaises(ValueError):
            store.Store(packet({'a':self.row},{self.row['sha256']:self.data},'extra'),v.ROOT)

    def test_missing_object(self):
        with self.assertRaises(ValueError):store.Store(packet({'a':self.row},{}),v.ROOT)

    def test_tampered_object(self):
        a=store.Store(packet({'a':self.row},{self.row['sha256']:b'tampered'}),v.ROOT)
        with self.assertRaises(ValueError):a.read('a')

    def test_conflicting_alias(self):
        with self.assertRaises(ValueError):
            store.Store(packet({'a/b':self.row,'a\\b':dict(self.row,bytes=3)},
                               {self.row['sha256']:self.data}),v.ROOT)

    def test_alias_size_mismatch(self):
        a=store.Store(packet({'a':self.row,'b':dict(self.row,bytes=1)},
                            {self.row['sha256']:self.data}),v.ROOT)
        with self.assertRaises(ValueError):a.verify()


class PositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=v.ROOT/'.cache/p35-independent-review-20261102-02/packet.zip'
        a=store.Store(source.read_bytes(),v.ROOT)
        v.STORE=a
        cls.states=v.r.Decoder().feed(a.read(s.RUN/'device/app-capture.jsonl'))
        cls.plan=json.loads(a.read(s.RUN/'plan.json'))

    def gate(self,states):
        return s.position_gate(states,self.plan,*[next(x for x in states if x['seq']==n) for n in (291,318,376,379)])

    def test_real_position(self):
        self.assertEqual(self.gate(self.states),'PRE_DURABLE_POSITION_PROVED')

    def test_portable_position_callers(self):
        self.assertEqual(s.position()['actualCutDurable'],0)

    def test_actual_admission_identity(self):
        self.assertEqual(evaluate.admission()['campaignInitialVersion'],30307)

    def test_canonical_predecessor_plan(self):
        sys.path.insert(0,str(v.ROOT))
        from Tools.acceptance import validate_bundle as validator
        b=v.ROOT/'docs/acceptance-contracts/P3-5-v4'
        c,m,d,_=validator._load_bundle(b/'contract.json',b/'evidence-matrix.json')
        expected=json.loads((b/'rerun-plan.json').read_bytes())
        self.assertEqual(evaluate.predecessor_plan(c,m,d,b/'history/v3'),expected)
        self.assertEqual(expected['previous_contract_sha256'],expected['previous_contract_sha256'].upper())

    def test_invalid_positions(self):
        for n,k,value in ((318,'durable',4096),(376,'durable',8192),(379,'sendOffset',128),
                          (379,'session',1),(318,'linkConnected',True)):
            rows=copy.deepcopy(self.states)
            rows[n-1][k]=value
            with self.subTest(seq=n,field=k), self.assertRaises(v.r.Stop):self.gate(rows)

    def test_capture_corruption(self):
        a=store.Store((v.ROOT/'.cache/p35-independent-review-20261102-02/packet.zip').read_bytes(),v.ROOT)
        raw=a.read(s.RUN/'device/app-capture.jsonl')
        for altered in (raw.rsplit(b'OTA_P35_CAPTURE ',1)[0],raw.replace(b'"seq":2,',b'"seq":3,',1),
                        raw.replace(b'"lost":0',b'"lost":1',1)):
            self.assertNotEqual(altered,raw)
            with self.assertRaises(v.r.Stop):v.r.audit_capture(altered,self.states[0]['captureId'])


if __name__=='__main__':
    assert Path.cwd()==v.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    unittest.main(verbosity=2)
