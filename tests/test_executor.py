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


def test_echo_preserves_spaces_in_quoted_text():
    assert SystemOps().run_command('echo "Hello  ZENO!"').output == "Hello  ZENO!"


def test_close_app_targets_exact_executable_and_preserves_other_processes(monkeypatch):
    from unittest.mock import Mock
    import win32con
    processes = {1: "chrome.exe", 2: "chrome-helper.exe", 3: "chrome.exe"}
    monkeypatch.setattr("win32gui.EnumWindows", lambda fn, arg: [fn(hwnd, arg) for hwnd in processes])
    monkeypatch.setattr("win32gui.IsWindowVisible", lambda hwnd: True)
    monkeypatch.setattr("win32gui.GetWindowText", lambda hwnd: "Document")
    monkeypatch.setattr("win32process.GetWindowThreadProcessId", lambda hwnd: (0, hwnd))
    from types import SimpleNamespace
    monkeypatch.setattr("psutil.Process", lambda pid: SimpleNamespace(name=lambda: processes[pid]))
    post = Mock()
    monkeypatch.setattr("win32gui.PostMessage", post)
    monkeypatch.setattr("win32gui.GetForegroundWindow", lambda: 2)
    ops = SystemOps()
    assert ops.close_app("Google Chrome").error == "AMBIGUOUS_WINDOW"
    post.assert_not_called()
    monkeypatch.setattr("win32gui.GetForegroundWindow", lambda: 3)
    assert ops.close_app("Google Chrome").success
    post.assert_called_once_with(3, win32con.WM_CLOSE, 0, 0)
    for text in ["", "host", "svchost", "file explorer"]:
        assert not ops.close_app(text).success


def test_secret_files_and_parent_trees_are_protected(tmp_path):
    import os
    ops = FileOps([str(tmp_path)])
    folder = tmp_path / "project"
    folder.mkdir()
    secret = folder / ".env.local"
    secret.write_text("fake-private-value")
    alias = tmp_path / "notes.txt"
    os.link(secret, alias)
    for path in (alias, secret):
        assert not ops.file_read(str(path)).success
        assert not ops.file_copy(str(path), str(tmp_path / "revealed.txt")).success
    assert not ops.file_copy(str(folder), str(tmp_path / "backup")).success
    assert not ops.file_move(str(folder), str(tmp_path / "moved")).success
    assert not ops.file_delete(str(folder), permanent=True).success
    assert ops.file_search(str(tmp_path), "**/*").output == []
    assert secret.exists()


def test_read_preview_bounds_single_line_and_line_count(tmp_path):
    from executor.file_ops import MAX_READ_BYTES
    ops = FileOps([str(tmp_path)])
    path = tmp_path / "large.txt"
    path.write_bytes(b"x" * (MAX_READ_BYTES * 3))
    result = ops.file_read(str(path))
    assert result.success and result.output == "x" * MAX_READ_BYTES
    assert "truncated" in result.message
    path.write_bytes(b"x\r\n" * 250)
    assert ops.file_read(str(path)).output == "x\n" * 200


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
