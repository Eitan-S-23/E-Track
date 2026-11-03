"""Evaluate the immutable first P1-7 observation without any device operation."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p17_observe as p

CONTRACT_SHA256 = '3387d981ae3145736160c288e5659dab79f757684c6f1c41e2774d7f7515c6b3'
MATRIX_SHA256 = '010cdd55e9700e1afcfbfc6243c8f1a5d2971e35fe8f90cccc36a595050907ec'


def safe_relative(name):
    path = PurePosixPath(name)
    p.h.require(not path.is_absolute() and str(path) == name and
                not any(part in ('.', '..') or ':' in part or '\\' in part for part in path.parts),
                'unsafe original path')
    return path


def evaluate(read):
    inputs = {}

    def original(name, digest=None):
        safe_relative(name)
        data = read(name)
        actual = hashlib.sha256(data).hexdigest()
        p.h.require(digest is None or actual == digest.lower(), 'original hash mismatch: ' + name)
        inputs[name] = dict(bytes=len(data), sha256=actual)
        return data

    contract = json.loads(original('contract.json', CONTRACT_SHA256))
    matrix = json.loads(original('final-matrix.json', MATRIX_SHA256))
    p.h.require(matrix['overall_result'] == 'HARNESS_FAIL', 'first failure must remain explicit')
    for name, digest in matrix['evidence_hashes'].items():
        original(name, digest)
    for item in contract['external_inputs']:
        original(item['evidence_path'], item['evidence_sha256'])
    for item in matrix['artifacts']:
        p.h.require(len(original(item['path'], item['sha256'])) == item['size'], 'artifact size mismatch')
    plan = json.loads(original('inputs/plan.json'))
    measured = p.summarize(p.sdk_events(original('observation/native/0003-startup-samples/sdk.log').decode('utf8')),
                           plan['addresses'], plan['samples'])
    app, boot, executable = (original('inputs/' + name) for name in
                             ('app-final.bin', 'boot-full.bin', 'boot-executable.bin'))
    p.h.require(boot.startswith(executable) and 0 < len(executable) <= 65536, 'wrong Boot executable')
    p.h.require(boot[len(executable):16384] == b'\xff' * (16384-len(executable)), 'Boot padding mismatch')
    health = {}
    for stage in ('0001-before', '0005-after'):
        prefix = 'observation/native/' + stage + '/'
        samples = {Path(name).stem: original(name) for name in matrix['evidence_hashes']
                   if name.startswith(prefix) and name.endswith('.bin')}
        p.h.require(samples['app'] == app and samples['boot'] == boot, 'retained image mismatch')
        health[stage] = p.live_mcu.health_gate(samples)
    p.h.require(health['0001-before']['registers']['freeze'] ==
                health['0005-after']['registers']['freeze'] == 0, 'debug freeze not restored')
    closed = 0
    for name in matrix['evidence_hashes']:
        if name.endswith('.started.json'):
            receipt = json.loads(original(name.replace('.started.json', '.closed.json')))
            p.h.require(receipt['cleanup_complete'], 'unclosed original command')
            # Paths in native receipts retain their original invocation location.
            for stream in ('stdout', 'stderr'):
                rel = name.removesuffix('.started.json') + '.' + stream
                original(rel, receipt[stream]['sha256'])
            closed += 1
    p.h.require(matrix['commands'][0]['exit_code'] == 1, 'original parser failure disappeared')
    criteria = dict(C_STARTUP=measured['startup']['result'], C_POWER_HOLD=measured['powerHold']['result'],
                    C_CLOCK_SIZE=measured['clock']['result'], C_RECOVERY_KEY='NOT_OBSERVED', C_BATTERY='NOT_OBSERVED')
    return dict(outcome='ORIGINALS_EVALUATED', overallResult='EVIDENCE_GAP', criteria=criteria,
                observed=measured, bootExecutableBytes=len(executable), health=health,
                originalContractSha256=CONTRACT_SHA256, originalMatrixSha256=MATRIX_SHA256,
                originalOutcome='HARNESS_FAIL', originalCommandExitCode=1,
                closedOriginalCommands=closed, inputHashes=inputs, deviceOperations=0,
                originalPhysicalResets=1, originalOperator='Original independent acceptance session',
                originalSource=contract['freeze_commit'], originalDate=contract['approved_at'],
                interpretation='Offline original evidence evaluation, not repeated hardware or whole-card PASS.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    p.h.require(Path.cwd() == p.ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                'isolated project-root execution required')
    bundle = p.h.checked(args.bundle)
    out = p.h.checked(args.out)
    p.h.require(not out.exists(), 'preserve previous result')
    result = evaluate(lambda name: p.h.checked(bundle / str(safe_relative(name))).read_bytes())
    p.h.save(out, result)
    print(json.dumps({k: result[k] for k in ('outcome', 'overallResult', 'criteria', 'deviceOperations')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
