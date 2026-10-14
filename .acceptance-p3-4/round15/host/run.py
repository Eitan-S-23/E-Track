"""Execute only the standard successor plan's still-required offline commands."""
import os
from pathlib import Path
import shlex
import sys

R = Path('D:/github/my/E-Track/.cache/p34-final')
F = R / '.cache/p34-local-closeout-20261014/successor15'
B = R / '.acceptance-p3-4/round15'
assert Path.cwd() == R and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(R / 'Tools/ota/p34-acceptance'))
import live_host as h

prepared = h.read_json(F / 'prepared.json')
c = h.read_json(h.pinned(prepared['contract']))
h.pinned(prepared['matrix'])
assert h.read_json(h.pinned(prepared['preflight']))['exit_code'] == 0
plan = h.read_json(h.pinned(prepared['plan']))
required = set(plan['required_commands'])
assert len(required) == 16 and plan['reusable_criteria'] == ['P34-CANDIDATE-REFERENCE']
inputs = h.read_json(B / 'origins/v13/inputs/live-inputs.json')
git = h.pinned(inputs['tools']['git'])
fc = h.pinned(h.read_json(B / 'origins/v13/inputs/fc-tool.json'))
out = h.fresh(F / 'evaluation')
env = h.environment(out)
env['PATH'] = str(git.parent) + os.pathsep + env.get('PATH', '')
completed = []
try:
    for item in c['commands']:
        if item['id'] not in required:
            continue
        argv = shlex.split(item['command'])
        if argv[0] == 'python':
            assert argv[1:6] == ['-I', '-S', '-B', '-X', 'utf8']
            if argv[6] == '-m':
                assert argv[6:9] == ['-m', 'zipfile', '-t'] and len(argv) == 10
                h.checked(R / argv[9])
            else:
                assert argv[6] in ('Tools/ota/p3-4-link-stats/acceptance_stats.py',
                                   'Tools/ota/p34-acceptance/metrics.py')
        elif Path(argv[0]) == fc:
            assert argv[1] == '/B' and len(argv) == 4
            for name in argv[2:]:
                assert Path(name).is_absolute() and '/' not in name
                h.checked(name)
        else:
            assert Path(argv[0]) == git and argv[1:3] == ['--no-optional-locks', 'diff']
            assert '--no-ext-diff' in argv and '--no-textconv' in argv and '--exit-code' in argv
        h.command(B / 'commands', item['id'], argv, env,
            seconds=item['process_timeout_seconds'], success_codes=tuple(item['expected_exit_codes']))
        path = B / 'commands' / (item['id'] + '.closed.json')
        receipt = h.read_json(path)
        assert receipt['exit_code'] == 0 and not receipt['stopped_while_running']
        if item['id'].startswith('CMD-CANDIDATE-ARCHIVE-'):
            assert (B / 'commands' / (item['id'] + '.stdout')).read_text(encoding='utf-8').strip() == 'Done testing'
        completed.append(h.record(path))
        print('OFFLINE_COMMAND_PASS', item['id'], flush=True)
except BaseException as error:
    h.save(F / 'evaluation-failed.json', dict(error_type=type(error).__name__, message=str(error),
        completed=completed, preserve_outputs=True, no_automatic_replay=True, device_operations=0))
    raise
h.save(F / 'evaluated.json', dict(required_count=len(required), commands=completed,
    reused_criteria=plan['reusable_criteria'], physical_device_operations=0, qualification_total=3))
print('V15_OFFLINE_COMMANDS_COMPLETE; independent original-data adjudication follows', flush=True)
