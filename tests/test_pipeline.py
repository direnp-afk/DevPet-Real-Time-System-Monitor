import json
import shutil
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app import make_server
from devpet_cli import execute
from event_log import write_event
from runtime import DevPetRuntime, tail_command


def wait_for(predicate, timeout=6):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_log_is_jsonl(tmp_path):
    path=tmp_path/'logs'/'events.log'
    data=write_event('TEST_PASSED','All green!',path,tests=24)
    stored=json.loads(path.read_text(encoding='utf-8').strip())
    assert stored == data
    assert stored['tests'] == 24
    assert stored['ts'].endswith('+00:00')
    with pytest.raises(ValueError):
        write_event('bad type', 'x', path)


def test_real_tail_replay_and_live_events(tmp_path):
    try:
        tail_command(tmp_path / 'events.log')
    except RuntimeError:
        pytest.skip('No supported log follower present')
    logfile = tmp_path/'events.log'
    write_event('TEST_PASSED','logged before launch',logfile)
    runtime = DevPetRuntime(logfile,poll_seconds=60)
    try:
        runtime.start()
        assert wait_for(lambda: runtime.snapshot()['pet']['total_xp'] == 25)
        write_event('APP_CRASH','something failed',logfile)
        assert wait_for(lambda: runtime.snapshot()['pet']['mood'] == 'sick')
        assert runtime.snapshot()['tail']['running']
        assert runtime.snapshot()['events_seen'] == 2
    finally:
        runtime.stop()


def test_tail_follows_log_rotation(tmp_path):
    if sys.platform == 'win32' or not shutil.which('tail'):
        pytest.skip('GNU tail log rotation tested on Unix')
    logfile=tmp_path/'events.log'
    runtime=DevPetRuntime(logfile,poll_seconds=60)
    try:
        runtime.start()
        write_event('GIT_COMMIT','before rotation',logfile)
        assert wait_for(lambda:runtime.snapshot()['pet']['total_xp']==15)
        logfile.rename(tmp_path/'events.log.1')
        write_event('TEST_PASSED','after rotation',logfile)
        assert wait_for(lambda:runtime.snapshot()['pet']['total_xp']==40,timeout=8)
    finally:
        runtime.stop()


def test_http_dashboard_and_demo(tmp_path):
    try:
        tail_command(tmp_path / 'events.log')
    except RuntimeError:
        pytest.skip('No supported log follower present')
    runtime=DevPetRuntime(tmp_path/'events.log',poll_seconds=60)
    runtime.start()
    server=make_server(runtime,'127.0.0.1',0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/') as response:
            assert b'DevPet' in response.read()
            assert response.status == 200
        for name in ('/style.css','/main.js'):
            with urlopen(base+name) as response:
                assert response.status == 200
        payload=json.dumps({'type':'BUILD_SUCCESS'}).encode()
        with urlopen(Request(base+'/api/demo',data=payload,headers={'Content-Type':'application/json'})) as response:
            assert json.load(response)['ok']
        assert wait_for(lambda:runtime.snapshot()['pet']['total_xp']==30)
        with urlopen(base+'/api/state') as response:
            result=json.load(response)
            assert result['pet']['level']==1
            assert result['events_seen']==1
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(base+'/api/demo',data=b'{"type":"SOMETHING_DANGEROUS"}',headers={'Content-Type':'application/json'}))
        assert exc.value.code==400
        with pytest.raises(HTTPError) as exc:
            urlopen(base+'/../runtime.py')
        assert exc.value.code==404
    finally:
        server.shutdown()
        server.server_close()
        runtime.stop()


def test_cli_runs_real_commands(tmp_path):
    log=tmp_path/'events.log'
    assert execute('tests',[sys.executable,'-c','pass'],log)==0
    assert execute('tests',[sys.executable,'-c','import sys;sys.exit(5)'],log)==5
    assert execute('run',[sys.executable,'-c','pass'],log)==0
    assert execute('run',[sys.executable,'-c','import sys;sys.exit(3)'],log)==3
    events=[json.loads(line) for line in log.read_text().splitlines()]
    assert [ev['type'] for ev in events] == ['TEST_PASSED','TEST_FAILED','BUILD_SUCCESS','APP_CRASH']
