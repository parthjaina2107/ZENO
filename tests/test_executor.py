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
