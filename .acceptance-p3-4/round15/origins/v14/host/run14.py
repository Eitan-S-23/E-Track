"""Run the standard plan's admitted offline commands, never device entries."""
import os
from pathlib import Path
import shlex
import sys

R = Path('D:/github/my/E-Track/.cache/p34-final')
E = R / '.cache/p34-local-closeout-20261014'
B = R / '.acceptance-p3-4/round14'
assert Path.cwd() == R and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(R / 'Tools/ota/p34-acceptance'))
import live_host as h

prepared = h.read_json(E / 'candidate-prepared.json')
c = h.read_json(h.pinned(prepared['contract']))
h.pinned(prepared['matrix'])
assert h.read_json(h.pinned(prepared['preflight']))['exit_code'] == 0
plan = h.read_json(h.pinned(prepared['plan']))
required = set(plan['required_commands'])
assert len(required) == 19 and required == {x['id'] for x in c['commands']}
assert not plan['reusable_criteria']
inputs = h.read_json(B / 'origins/v13/inputs/live-inputs.json')
git = h.pinned(inputs['tools']['git'])
fc = h.pinned(h.read_json(B / 'origins/v13/inputs/fc-tool.json'))
out = h.fresh(E / 'candidate-evaluation')
env = h.environment(out)
env['PATH'] = str(git.parent) + os.pathsep + env.get('PATH', '')
completed = []
try:
    for item in c['commands']:
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
            for path in argv[2:]:
                h.checked(R / path)
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
    h.save(E / 'candidate-evaluation-failed.json', dict(error_type=type(error).__name__,
        message=str(error), completed=completed, preserve_outputs=True, no_automatic_replay=True,
        device_operations=0))
    raise
h.save(E / 'candidate-evaluated.json', dict(required_count=len(required), commands=completed,
    interpretation='New offline evaluations of existing originals; no new physical executions.',
    device_operations=0, physical_qualification_total=3))
print('CANDIDATE_OFFLINE_COMMANDS_COMPLETE; original-data adjudication follows', flush=True)
