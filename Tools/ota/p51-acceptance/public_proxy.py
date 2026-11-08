"""Bind the fixed P51 proxy to original native deployment and API receipts."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p34-acceptance'))
import live_host as h

PROJECT = 'e-track-p51-benchmark'
ORIGIN = 'https://' + PROJECT + '.pages.dev'
PUBLIC = Path(__file__).resolve().parent / 'public'
UPSTREAM = re.compile(r'https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com')
SOURCE_PATHS = dict(worker='Tools/ota/p51-acceptance/public/site/_worker.js',
    template='Tools/ota/p51-acceptance/public/wrangler.jsonc')


def deployment_config(upstream):
    h.require(isinstance(upstream, str) and UPSTREAM.fullmatch(upstream), 'one exact HTTPS upstream required')
    config = h.read_json(PUBLIC / 'wrangler.jsonc')
    config['vars']['P51_UPSTREAM_ORIGIN'] = upstream
    return config


def native_tools_match(argv, pins):
    if not isinstance(argv, list) or len(argv) < len(pins):
        return False
    for argument, pin in zip(argv, pins):
        if not isinstance(argument, str) or not Path(argument).is_absolute():
            return False
        # Preserve the original argv; an installed tool may be invoked through a junction.
        if h.pinned(dict(pin, path=argument)) != h.pinned(pin):
            return False
    return True


def source_bytes(value, key):
    command = h.read_json(h.pinned(value['source_commands'][key]))
    h.require(command['argv'][1:] == ['--no-optional-locks', 'show',
        value['source'] + ':' + SOURCE_PATHS[key]] and
        native_tools_match(command['argv'], [value['tools']['git']]) and command['exit_code'] == 0 and
        command['exit_status'] == 'exited' and command['stopped_while_running'] is False and
        command['cleanup_complete'] is True and command['cleanup_errors'] == [],
        'original successful native Git source receipt required')
    h.pinned(command['stderr'])
    return h.pinned(command['stdout']).read_bytes().replace(b'\r\n', b'\n')


def validate_publication(pin, expected):
    value = h.read_json(h.pinned(pin))
    h.require(value.get('schema') == 'p51-pages-proxy-v1' and value.get('project') == PROJECT and
        value.get('origin') == expected['origin'] == ORIGIN, 'isolated fixed proxy identity required')
    upstream = value['upstream']
    config_path = h.pinned(value['configuration'])
    h.require(config_path.name == 'wrangler.jsonc' and
        h.read_json(config_path) == deployment_config(upstream), 'proxy deployment configuration drift')
    worker = h.pinned(value['worker'])
    h.require(worker == config_path.parent / 'site/_worker.js' and
        worker.read_bytes() == (PUBLIC / 'site/_worker.js').read_bytes(), 'proxy deployed source drift')
    ready = h.read_json(h.pinned(value['upstream_ready']))
    h.require(ready['origin'] == ORIGIN and ready['upstream'] == upstream and
        ready['service_config'] == expected['service_config'] and
        all(ready['package'][key] == expected['package'][key] for key in ('bytes', 'sha256')) and
        expected.get('upstream_origin', upstream) == upstream, 'proxy upstream/fixture identity drift')
    h.pinned(ready['source'])
    h.pinned(ready['package'])
    service_config = h.read_json(h.pinned(ready['service_config']))
    h.require(service_config['publicBaseUrl'] == ORIGIN, 'fixture download URLs must use the fixed origin')

    source = value['source']
    h.require(isinstance(source, str) and re.fullmatch(r'[0-9a-f]{40}', source), 'proxy source commit required')
    h.require(source_bytes(value, 'worker') == worker.read_bytes().replace(b'\r\n', b'\n') and
        source_bytes(value, 'template') == (PUBLIC / 'wrangler.jsonc').read_bytes().replace(b'\r\n', b'\n'),
        'proxy Git blob content differs from deployed worker or canonical template')
    tools = [value['tools'][key] for key in ('node', 'wrangler')]
    command = h.read_json(h.pinned(value['deploy_command']))
    h.require(command['argv'][2:] == ['pages', 'deploy', str(worker.parent),
        '--project-name', PROJECT, '--branch', 'main', '--commit-hash', source,
        '--commit-dirty=false', '--no-bundle', '--upload-source-maps=false', '--cwd', str(config_path.parent)] and
        native_tools_match(command['argv'], tools) and
        command['exit_code'] == 0 and command['exit_status'] == 'exited' and
        command['stopped_while_running'] is False and command['cleanup_complete'] is True and
        command['cleanup_errors'] == [], 'original successful native Pages deployment required')
    stdout = h.pinned(command['stdout']).read_text(encoding='utf-8')
    h.pinned(command['stderr'])
    output = [json.loads(line) for line in h.pinned(value['deploy_output']).read_text(encoding='utf-8').splitlines()]
    detailed = [row for row in output if row.get('type') == 'pages-deploy-detailed']
    h.require(len(detailed) == 1, 'one original native Pages deployment identity required')
    native = detailed[0]

    response_pin = value['project_response']
    response = h.read_json(h.pinned(response_pin))
    http = h.read_json(h.pinned(value['project_http']))
    account = value['account']
    h.require(re.fullmatch(r'[0-9a-f]{32}', account) and http['method'] == 'GET' and
        http['url'] == 'https://api.cloudflare.com/client/v4/accounts/' + account + '/pages/projects/' + PROJECT and
        http['status'] == 200 and http['body'] == response_pin and response['success'] is True,
        'original successful Pages project readback required')
    project = response['result']
    deployed = project['canonical_deployment']
    h.require(project['name'] == PROJECT and project['subdomain'] == PROJECT + '.pages.dev' and
        project['production_branch'] == 'main' and deployed['project_name'] == PROJECT and
        deployed['environment'] == 'production' and deployed['latest_stage']['status'] == 'success' and
        re.fullmatch(r'[0-9a-f-]{36}', deployed['id']) and
        deployed['deployment_trigger']['metadata']['commit_hash'] == source and
        deployed['deployment_trigger']['metadata']['commit_dirty'] is False and
        deployed['url'] in stdout and native['deployment_id'] == deployed['id'] and
        native['pages_project'] == PROJECT and native['url'] == deployed['url'] and
        native['environment'] == 'production' and
        native['deployment_trigger']['metadata']['commit_hash'] == source,
        'proxy remote/native/source deployment identity mismatch')
    variables = dict(P51_UPSTREAM_ORIGIN=dict(type='plain_text', value=upstream))
    production = project['deployment_configs']['production']
    h.require(deployed['env_vars'] == production['env_vars'] == variables and
        deployed['compatibility_date'] == production['compatibility_date'] == deployment_config(upstream)['compatibility_date'] and
        not any(production.get(key) or deployed.get(key) for key in
            ('services', 'd1_databases', 'r2_buckets', 'kv_namespaces', 'durable_object_namespaces')),
        'proxy must bind exactly the observed upstream, without production data resources')
    return value


def publish(pin, expected, destination):
    destination = h.checked(destination)
    pending = h.checked(destination.with_suffix(destination.suffix + '.tmp'))
    h.require(not destination.exists() and not pending.exists(),
        'prior/uncertain proxy publication exists; reconcile, do not replay')
    value = validate_publication(pin, expected)
    h.require(not destination.exists() and not pending.exists(),
        'proxy publication changed during validation; reconcile, do not replay')
    h.host.io.write_json(h.ROOT, destination, value, replace=True)
    return h.record(destination)
