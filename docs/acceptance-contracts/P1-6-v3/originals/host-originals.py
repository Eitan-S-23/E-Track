"""Evaluate source-bound historical group16 originals; do not rerun their campaigns."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path.cwd()
sys.path.insert(0,str(ROOT/'Tools/ota/p34-acceptance'))
import live_host as h
ORIGINAL=Path('D:/github/my/E-Track/.cache/p34-boot-checkpoint')
TARGET=Path('D:/github/my/E-Track/.cache/p34-bc-target/f')
out=h.checked(ROOT/'.cache/p16g-20261104-01/host-originals')
for leaf in ('host','inputs.json','result.json'):h.checked(out/leaf)
h.fresh(out);env=h.environment(out)
inputs={}
def raw(p):
    p=Path(p);data=p.read_bytes()
    inputs[str(p)]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    return data
def bound(item):
    data=raw(item['path'])
    assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
    return data
def js(p):return json.loads(raw(p))
assert raw(ORIGINAL/'boot_state_machine.c').replace(b'\r\n',b'\n')==raw(TARGET/'boot/src/boot_state_machine.c').replace(b'\r\n',b'\n')
results=[]
for name,prefix in (('r3','g16-'),('extension1','g16-'),('review-tests1','')):
    result=js(ORIGINAL/name/'result.json')
    changed=[]
    for item in result['sources']:
        data=raw(item['path'])
        if hashlib.sha256(data).hexdigest()!=item['sha256']:changed.append(Path(item['path']))
    assert {p.name for p in changed}=={'ota_ble_frame.h','ota_ble_session.h','ota_staging.h'}
    compile_record=js(ORIGINAL/name/(prefix+'compile.json'))
    run_record=js(ORIGINAL/name/(prefix+'run.json'))
    assert compile_record['exit']==run_record['exit']==0
    assert bound(compile_record['log'])==b''
    output=bound(run_record['log']).decode()
    command=compile_record['command']
    assert '-DP34_BOOT_APPLY_CHECKPOINT_BLOCKS=16' in command and '-DP34_BOOT_SKIP_IDENTICAL_BLOCKS=1' in command
    args=command[:command.index('-o')]+['-MM']
    deps=h.command(out,'dependencies-'+name,args,env,seconds=60).decode()
    assert all(p.name not in deps for p in changed), 'changed header participates in model translation units'
    if name=='r3':assert 'BOOT_CHECKPOINT_MODEL_PASS group=16 scenarios=1793 cuts=1691 max_rework=16' in output
    if name=='extension1':assert 'CHECKPOINT_EXTENSION_PASS group=16 frontiers=13 scenarios=39' in output
    if name=='review-tests1':
        assert 'CHECKPOINT_REVIEW_PASS tears=336 io_faults=36 sequences=11 oracle_negatives=3' in output
        bound(result['generated']);bound(result['executable'])
    results.append(dict(original=name,originalExit=0,rawOutput=output,changedInventoryHeadersNotCompiled=[str(p) for p in changed]))
h.save(out/'inputs.json',inputs)
h.save(out/'result.json',dict(outcome='EXISTING_GROUP16_MODELS_REVIEWED',results=results,
    actualStateMachineMatchesTargetIgnoringCRLF=True,modelsRerun=0,deviceOperations=0,
    scope='Host model invariants only; no electrical power-cut proof or new endurance group.'))
print('EXISTING_GROUP16_MODELS_REVIEWED modelsRerun=0 deviceOperations=0',flush=True)
