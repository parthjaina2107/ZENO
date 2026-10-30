import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import zipfile

import pytest

from brain.coding_intent import CodingIntent, CodingRequest
from brain.planner import describe_action, PlannedAction
from desktop.control import RunControl
from desktop.engine import DesktopEngine
from executor import coding_workspace as cw
from executor.file_ops import FileOps


def plan(*files):
    return cw.CodingPlan(status='ready', summary='Completed tutorial', question='',
                         files=[cw.ProposedFile(path=p, content=c) for p, c in files], suggested_checks=[])


def test_intent_requires_explicit_task_and_literal_workspace():
    router = CodingIntent()
    assert router.route('Explain how to open VS Code and write Python') is None
    assert router.route("Do not open VS Code and write anything") is None
    assert router.route('Open VS Code') is None
    assert router.route('Open VS Code and write Tutorial 3 in etc').question
    result = router.route('"C:\\Users\\HP\\Desktop\\etc"')
    assert result.workspace.endswith('Desktop\\etc')
    assert 'Tutorial 3' in result.goal
    assert router.route('Coding task: fix the exercise').question
    router.route('cancel')
    assert not router.pending_goal
    assert router.route('Zeno, can you write my Tutorial 3 in etc').question


@pytest.mark.parametrize('relative', ['../outside.py', '/outside.py', 'C:/outside.py', '.env',
                                     '.git/config.py', 'CON.py', 'sub/file.py.', 'a:stream.py',
                                     '__tutorial_context__/instructions.txt'])
def test_unsafe_output_paths_rejected(tmp_path, relative):
    with pytest.raises(ValueError):
        cw.target_path(tmp_path, relative)


def test_snapshot_and_apply_preserve_secrets_backup_and_verify(tmp_path):
    (tmp_path / 'task.py').write_text('answer = 1\n')
    (tmp_path / '.env').write_text('TOKEN=private')
    (tmp_path / 'credentials.json').write_text('{}')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'x.js').write_text('ignored')
    original = cw.snapshot(tmp_path)
    assert set(original) == {'task.py'}
    changes = plan(('task.py', 'answer = 3\n'), ('src/new.py', 'print(3)\n'))
    run = tmp_path / 'run'
    manifest = cw.apply_plan(tmp_path, changes, original, run)
    assert (tmp_path / 'task.py').read_text() == 'answer = 3\n'
    assert (run / 'backups/task.py').read_text() == 'answer = 1\n'
    assert cw.digest((tmp_path / 'src/new.py').read_bytes()) == manifest[1]['after_sha256']
    assert (tmp_path / '.env').read_text() == 'TOKEN=private'


def test_stale_and_invalid_batch_never_writes(tmp_path):
    old = b'value = 1\n'
    (tmp_path / 'task.py').write_bytes(old)
    original = cw.snapshot(tmp_path)
    with pytest.raises(SyntaxError):
        cw.apply_plan(tmp_path, plan(('task.py', 'value = 2\n'), ('bad.py', 'def :')), original, tmp_path / 'run')
    assert (tmp_path / 'task.py').read_bytes() == old
    (tmp_path / 'task.py').write_text('user edit')
    with pytest.raises(ValueError, match='changed'):
        cw.apply_plan(tmp_path, plan(('task.py', 'value = 2\n')), original, tmp_path / 'run')
    assert (tmp_path / 'task.py').read_text() == 'user edit'


def test_duplicate_outputs_and_unread_files_rejected(tmp_path):
    (tmp_path / 'x.py').write_text('pass')
    with pytest.raises(ValueError, match='absent'):
        cw.validate_plan(tmp_path, plan(('x.py', 'pass')), {})
    with pytest.raises(ValueError, match='duplicate'):
        cw.validate_plan(tmp_path, plan(('new.py', 'pass'), ('NEW.py', 'pass')), {})


def test_failed_batch_rolls_back_saved_files(tmp_path, monkeypatch):
    (tmp_path / 'a.py').write_text('value = 1')
    original = cw.snapshot(tmp_path)
    replace = cw.os.replace
    def fail_replace(source, dest):
        raise OSError('simulated write failure')
    monkeypatch.setattr(cw.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        cw.apply_plan(tmp_path, plan(('new.py', 'pass'), ('a.py', 'value = 2')), original, tmp_path / 'run')
    assert not (tmp_path / 'new.py').exists()
    assert (tmp_path / 'a.py').read_text() == 'value = 1'


def test_tutorial_docx_and_pdf_extraction(tmp_path):
    with zipfile.ZipFile(tmp_path / 'Tutorial 3.docx', 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Write a sorting function</w:t></w:r></w:p></w:body></w:document>')
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    staging = tmp_path / 'staging'
    staging.mkdir()
    cw.stage_documents(tmp_path, staging)
    assert 'sorting function' in (staging / '__tutorial_context__/Tutorial 3.docx.txt').read_text()
    with (tmp_path / 'scanned.pdf').open('wb') as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match='No tutorial text'):
        cw.stage_documents(tmp_path, staging)


@pytest.mark.asyncio
async def test_runner_approvals_and_end_to_end_fake_provider(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'Tutorial3.txt').write_text('Write a function that adds two numbers')
    monkeypatch.setattr(cw.config, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(cw, 'coding_executable', lambda: 'fake-codex')
    def fake_proposal(goal, staging, directory, control, progress):
        assert (staging / 'Tutorial3.txt').read_text().startswith('Write')
        result = plan(('tutorial3.py', 'def add(a, b):\n    return a + b\n'))
        (directory / 'proposal.json').write_text(result.model_dump_json())
        return result
    proposal = MagicMock(side_effect=fake_proposal)
    monkeypatch.setattr(cw, 'propose', proposal)
    editor = MagicMock(return_value=True)
    monkeypatch.setattr(cw, 'open_vscode', editor)
    runner = cw.CodingRunner(MagicMock(), FileOps([str(root)]))
    request = CodingRequest('Complete Tutorial 3', str(root))
    denied = AsyncMock(return_value=False)
    assert 'Cancelled' in await runner.run(request, denied, lambda *a: None, RunControl())
    proposal.assert_not_called()
    approve = AsyncMock(side_effect=[True, False])
    assert 'not applied' in await runner.run(request, approve, lambda *a: None, RunControl())
    assert not (root / 'tutorial3.py').exists()
    editor.assert_not_called()
    approve = AsyncMock(return_value=True)
    reply = await runner.run(request, approve, lambda *a: None, RunControl())
    assert 'Saved and verified 1' in reply
    assert 'Runtime tests were not run' in reply
    assert (root / 'tutorial3.py').exists()
    assert approve.call_args_list[1].args[0].risk_level == 'high'
    reports = list((tmp_path / 'data/coding_runs').glob('*/report.json'))
    assert any(json.loads(p.read_text())['status'] == 'saved' for p in reports)
    editor.assert_called_once()


@pytest.mark.asyncio
async def test_engine_routes_coding_without_gemini(tmp_path, monkeypatch):
    engine = DesktopEngine.__new__(DesktopEngine)
    engine.permissions = MagicMock()
    engine.brain = SimpleNamespace(think=AsyncMock(side_effect=AssertionError('Gemini called')),
                                  planner=SimpleNamespace(executor=SimpleNamespace(file=FileOps([str(tmp_path)]))))
    run = AsyncMock(return_value='Saved code')
    monkeypatch.setattr(cw.CodingRunner, 'run', run)
    reply = await engine.command(f'Coding task in "{tmp_path.as_posix()}": solve Tutorial 3', RunControl(), AsyncMock(), lambda *a: None)
    # Windows literal drive paths are accepted; POSIX quoted paths support test environments.
    assert reply == 'Saved code'
    engine.brain.think.assert_not_called()


def test_approval_exposes_folder_usage_and_changes():
    request = PlannedAction('coding_request', {'workspace': 'C:/project', 'goal': 'solve'})
    assert 'signed-in account' in describe_action(request)
    apply = PlannedAction('coding_apply', {'workspace': 'C:/project', 'proposal': 'C:/report/proposal.json',
                         'files': [{'path': 'answer.py', 'before_sha256': None, 'after_sha256': '123', 'preview': '+pass'}]})
    description = describe_action(apply)
    assert all(value in description for value in ['answer.py', '+pass', '123', 'C:/report/proposal.json'])


def test_propose_uses_read_only_schema_and_parses_fake_cli(tmp_path, monkeypatch):
    import subprocess
    import sys
    import threading
    staging = tmp_path / 'snapshot'
    staging.mkdir()
    directory = tmp_path / 'run'
    directory.mkdir()
    actual_popen = subprocess.Popen
    recorded = []
    payload = plan(('answer.py', 'answer = 42\n')).model_dump_json()
    def spawn(args, **kwargs):
        recorded.extend(args)
        output = args[args.index('--output-last-message') + 1]
        script = 'import sys,pathlib; sys.stdin.read(); pathlib.Path(sys.argv[1]).write_text(sys.argv[2],encoding="utf-8")'
        return actual_popen([sys.executable, '-c', script, output, payload], **kwargs)
    monkeypatch.setattr(cw, 'coding_executable', lambda: 'fake-codex')
    monkeypatch.setattr(cw.subprocess, 'Popen', spawn)
    result = cw.propose('solve tutorial', staging, directory, RunControl())
    assert result.files[0].path == 'answer.py'
    assert recorded[recorded.index('--sandbox') + 1] == 'read-only'
    assert '--ignore-user-config' in recorded and '--output-schema' in recorded
    assert not (staging / 'answer.py').exists()


def test_cancel_terminates_fake_coding_process(tmp_path, monkeypatch):
    import subprocess
    import sys
    import threading
    staging = tmp_path / 'snapshot'
    staging.mkdir()
    directory = tmp_path / 'run'
    directory.mkdir()
    actual_popen = subprocess.Popen
    processes = []
    def spawn(args, **kwargs):
        child = actual_popen([sys.executable, '-c', 'import sys,time;sys.stdin.read();time.sleep(60)'], **kwargs)
        processes.append(child)
        return child
    monkeypatch.setattr(cw, 'coding_executable', lambda: 'fake-codex')
    monkeypatch.setattr(cw.subprocess, 'Popen', spawn)
    control = RunControl()
    timer = threading.Timer(.3, control.cancel)
    timer.start()
    try:
        with pytest.raises(asyncio.CancelledError):
            cw.propose('solve tutorial', staging, directory, control)
    finally:
        timer.cancel()
    assert processes[0].poll() is not None
    assert not list(staging.iterdir())
