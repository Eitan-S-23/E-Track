"""Correct GDB set-logging filename syntax, retaining both unexecuted drafts."""
from pathlib import Path
import hashlib
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
AREA = Path(__file__).resolve().parent
assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h

plan = h.read_json(AREA / 'key-plan.json')
text = h.pinned(plan['definitions']).read_text(encoding='ascii')


def filename(match):
    path = h.checked(Path(match[1]))
    h.require(not any(c.isspace() for c in str(path)), 'unexpected space in logging path')
    return 'set logging file ' + path.as_posix()


text, count = re.subn(r'^set logging file "([^"]+)"$', filename, text, flags=re.MULTILINE)
h.require(count == 4, 'unexpected stage count')
definitions = AREA / 'gdb-definitions-03.gdb'
entry = AREA / 'gdb-key-03.gdb'
h.raw(definitions, text.encode('ascii'))
h.raw(entry, (f'source "{definitions.as_posix()}"\np17-key-test\nquit\n').encode('ascii'))
for key, path in (('definitions', definitions), ('entry', entry)):
    plan[key] = dict(path=str(path), bytes=path.stat().st_size,
                     sha256=hashlib.sha256(path.read_bytes()).hexdigest())
plan['preparationHistory'] = 'gdb-check-02: set logging retains literal quotes; host-only failure preserved'
h.save(AREA / 'key-plan-final.json', plan)
print('FINAL_KEY_DEFINITIONS_PREPARED_NOT_RUN', flush=True)
