"""Additive continuation layout and terminal physical-idle audit; frozen base unchanged."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_offline_audit as legacy

SELF=Path(__file__).resolve()
LEGACY_WIRE,LEGACY_SEGMENTS=legacy.wire,legacy.segments


def wire(rows,kind,address,payload,size,original):
    raw=LEGACY_WIRE(rows,kind,address,payload,size,original)
    output=original
    after_stop=False
    for operation,at,value in legacy.target_events(rows):
        if operation=='write':
            previous=output
            output=output|value if at==legacy.gpio.SET else output&~value
            if value==0x80 and previous&0x40 and bool(previous&0x80)!=bool(output&0x80):
                after_stop=bool(output&0x80)
        elif at==legacy.gpio.INPUT and after_stop and value&0xc0!=0xc0:
            raise ValueError('non-idle physical INPUT after STOP')
    return raw


def segments(assets,plan,demcr,aircr):
    partial=assets['image'][:6144]+assets['envelope'][6144:]
    for spec in LEGACY_SEGMENTS(assets,plan,demcr,aircr):
        if spec['name'] in ('flash-0','flash-1','flash-2'):continue
        if spec['name']=='before-envelope':
            name,offset,address,raw=spec['archive']
            spec=dict(spec,archive=(name,offset,address,partial[offset:offset+len(raw)]))
        yield spec
        if spec['name']=='retained-entry':
            for index in range(3):
                yield dict(name='completed-prefix-'+str(index),reads=legacy.body.INTERNAL_READS,stores=())


def audit(store,area):
    import p34_install_continue as current
    before=[legacy.record(p) for p in current.sources(store)]
    early=[legacy.record(store.checked(area/name)) for name in ('events.jsonl','plan.json')]
    plan=store.read(area/'plan.json')
    if plan['inputs']!=before or plan['scope']!=current.SCOPE:raise ValueError('continuation scope/source binding differs')
    image=current.ASSETS['image'].read_bytes()
    with (area/'events.jsonl').open(encoding='utf-8') as stream:
        groups=iter(legacy.partitions(stream))
        next(groups);next(groups)
        for index in range(3):
            if legacy.chunks(next(groups),0x08010000+index*2048,2048)!=image[index*2048:(index+1)*2048]:
                raise ValueError('fresh completed-prefix archive mismatch')
    # This is an offline, single-threaded adapter only. Hardware workers never
    # replace module globals. Always restore even when a legacy check rejects.
    old_wire,old_segments=legacy.wire,legacy.segments
    try:
        legacy.wire,legacy.segments=wire,segments
        result=legacy.audit(store,area)
    finally:legacy.wire,legacy.segments=old_wire,old_segments
    if early!=[legacy.record(store.checked(r['path'])) for r in early]:
        raise ValueError('early prefix/scope evidence changed during strict audit')
    if before!=[legacy.record(p) for p in current.sources(store)]:raise ValueError('strict source drift after audit')
    result.update(strict_auditor=legacy.record(SELF),strict_inputs=before,
                  strict_early_inputs=early,
                  continuation_prefix_sectors=3,programmed_sectors=300,terminal_idle_checked=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--area',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    legacy.host.cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                            'isolated root required')
    store=legacy.host.cli.Store(ROOT);out=store.checked(args.output_dir)
    store.checked(out/'result.json')
    if out.exists():raise ValueError('preserve strict audit output')
    result=audit(store,store.checked(args.area))
    if result['strict_auditor']!=legacy.record(SELF):raise ValueError('strict auditor changed before publication')
    store.write(out/'result.json',result);print(result['result'])


if __name__=='__main__':main()
