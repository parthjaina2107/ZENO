"""
Unit tests for Executor subsystems: SystemOps, FileOps, BrowserOps.
"""

from pathlib import Path
from executor.system_ops import SystemOps
from executor.file_ops import FileOps
from executor.browser_ops import BrowserOps
from brain.planner import PlannedAction


def test_system_info_cpu():
    sys_ops = SystemOps()
    res = sys_ops.system_info("cpu")
    assert res.success is True
    assert "CPU" in res.message


def test_system_info_ram():
    sys_ops = SystemOps()
    res = sys_ops.system_info("ram")
    assert res.success is True
    assert "RAM" in res.message


def test_run_command_safety():
    sys_ops = SystemOps()
    # Safe command
    res = sys_ops.run_command("echo Hello Voice Agent")
    assert res.success is True
    assert "Hello Voice Agent" in res.output

    # Blocked command
    res_blocked = sys_ops.run_command("format C:")
    assert res_blocked.success is False
    assert res_blocked.error == "BLOCKED_COMMAND"


def test_run_command_allowlist_enforced():
    sys_ops = SystemOps()
    # Disallowed command (not in allowlist)
    res_disallowed = sys_ops.run_command("calc.exe")
    assert res_disallowed.success is False
    assert res_disallowed.error == "COMMAND_NOT_ALLOWED"
    assert "not in the allowed list" in res_disallowed.message

    # Allowlisted command whoami
    res_whoami = sys_ops.run_command("whoami")
    assert res_whoami.success is True
    assert len(res_whoami.output.strip()) > 0



def test_file_operations_temp(tmp_path):
    # Allow tmp_path in FileOps
    f_ops = FileOps(allowed_dirs=[str(tmp_path)])

    test_file = str(tmp_path / "test_note.txt")
    create_res = f_ops.file_create(test_file, "Voice Agent test line 1")
    assert create_res.success is True
    assert Path(test_file).exists()

    read_res = f_ops.file_read(test_file)
    assert read_res.success is True
    assert "Voice Agent test line 1" in read_res.output

    del_res = f_ops.file_delete(test_file, permanent=True)
    assert del_res.success is True
    assert not Path(test_file).exists()


def test_file_traversal_blocked(tmp_path):
    f_ops = FileOps(allowed_dirs=[str(tmp_path)])
    traversal_path = str(tmp_path / ".." / ".." / "Windows" / "system32" / "secret.txt")
    res = f_ops.file_create(traversal_path, "malicious")
    assert res.success is False
    assert res.error == "PATH_VALIDATION_FAILED"


def test_create_and_copy_never_replace_existing_files(tmp_path, monkeypatch):
    ops = FileOps([str(tmp_path)])
    source, dest = tmp_path / "source", tmp_path / "dest"
    assert ops.file_create(str(source), "Hello ZENO").success
    assert ops.file_copy(str(source), str(dest)).success
    assert ops.file_read(str(dest)).output == "Hello ZENO"
    assert "1 line from" in ops.file_read(str(dest)).message
    dest.write_text("Keep")
    assert not ops.file_create(str(dest), "Hello ZENO").success
    assert not ops.file_copy(str(source), str(dest)).success
    assert not ops.file_move(str(source), str(dest)).success
    assert dest.read_text() == "Keep"

    def partial_copy(src, staged):
        staged.write_text("partial")
        raise OSError("disk full")
    monkeypatch.setattr("executor.file_ops.shutil.copy2", partial_copy)
    assert not ops.file_copy(str(source), str(tmp_path / "new")).success
    assert {p.name for p in tmp_path.iterdir()} == {"source", "dest"}


def test_diagnostic_argument_policy_and_executable_resolution(monkeypatch):
    from unittest.mock import Mock
    run = Mock()
    monkeypatch.setattr("executor.system_ops.subprocess.run", run)
    ops = SystemOps()
    for command in ["echo ok & whoami", "dir | whoami", "echo ok > report.txt", "hostnameex",
                    "ipconfig /release", "route delete 0.0.0.0", "curl -o file https://example.com"]:
        assert not ops.run_command(command).success, command
    run.assert_not_called()
    run.return_value.returncode, run.return_value.stdout = 0, "host"
    assert ops.run_command("HOSTNAME.EXE").output == "host"
    invocation = run.call_args
    assert Path(invocation.args[0][0]).stem.lower() == "hostname"
    assert invocation.kwargs["shell"] is False


def test_close_app_targets_exact_executable_and_preserves_other_processes(monkeypatch):
    from unittest.mock import Mock
    processes = [Mock(info={"name": name}) for name in ["chrome.exe", "chrome-helper.exe", "svchost.exe", None]]
    monkeypatch.setattr("psutil.process_iter", lambda attrs: processes)
    ops = SystemOps()
    assert ops.close_app("Google Chrome").success
    processes[0].terminate.assert_called_once()
    for text in ["", "host", "svchost", "file explorer"]:
        assert not ops.close_app(text).success
    for proc in processes[1:]:
        proc.terminate.assert_not_called()
    assert ops.run_command('echo "Hello  ZENO!"').output == "Hello  ZENO!"


def test_copy_tree_and_search_stay_in_selected_directory(tmp_path):
    ops = FileOps([str(tmp_path)])
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "keep").write_text("Hello ZENO")
    assert not ops.file_copy(str(folder), str(folder / "child")).success
    assert not (folder / "child").exists()
    assert ops.file_copy(str(folder), str(tmp_path / "backup")).success
    assert (tmp_path / "backup" / "keep").read_text() == "Hello ZENO"
    assert not ops.file_copy(str(folder), str(tmp_path / "backup")).success
    assert not ops.file_search(str(folder), "../*").success
    assert ops.file_search(str(folder), "*").output[0]["name"] == "keep"


def test_cross_volume_move_collision_preserves_source(tmp_path, monkeypatch):
    import os
    import errno
    import pytest
    if os.name != "nt":
        pytest.skip("Windows cross-volume move")
    ops = FileOps([str(tmp_path)])
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_text("Keep original")
    rename = os.rename

    def simulate_cross_volume(staged, target):
        if staged == source:
            destination.mkdir()
            raise OSError(errno.EXDEV, "Different volumes")
        return rename(staged, target)

    monkeypatch.setattr(os, "rename", simulate_cross_volume)
    assert not ops.file_move(str(source), str(destination)).success
    assert source.read_text() == "Keep original"
    assert list(destination.iterdir()) == []
