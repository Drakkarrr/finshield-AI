"""Tests for backup/restore scripts (S4.5)."""
import os
import subprocess
from pathlib import Path

import pytest


def test_backup_script_exists():
    """Test that backup.sh script exists."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    backup_script = scripts_dir / "backup.sh"
    
    assert backup_script.exists(), f"Backup script not found at {backup_script}"


def test_restore_script_exists():
    """Test that restore.sh script exists."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    restore_script = scripts_dir / "restore.sh"
    
    assert restore_script.exists(), f"Restore script not found at {restore_script}"


def test_test_script_exists():
    """Test that test_backup_restore.sh script exists."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    test_script = scripts_dir / "test_backup_restore.sh"
    
    assert test_script.exists(), f"Test script not found at {test_script}"


def test_backup_script_is_executable():
    """Test that backup.sh is executable."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    backup_script = scripts_dir / "backup.sh"
    
    if backup_script.exists():
        assert os.access(backup_script, os.X_OK), "backup.sh is not executable"


def test_restore_script_is_executable():
    """Test that restore.sh is executable."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    restore_script = scripts_dir / "restore.sh"
    
    if restore_script.exists():
        assert os.access(restore_script, os.X_OK), "restore.sh is not executable"


def test_backup_script_has_shebang():
    """Test that backup.sh has proper shebang."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    backup_script = scripts_dir / "backup.sh"
    
    if backup_script.exists():
        with open(backup_script, 'r') as f:
            first_line = f.readline()
        assert first_line.startswith("#!/"), "backup.sh missing shebang"
        assert "bash" in first_line, "backup.sh should use bash"


def test_restore_script_has_shebang():
    """Test that restore.sh has proper shebang."""
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    restore_script = scripts_dir / "restore.sh"
    
    if restore_script.exists():
        with open(restore_script, 'r') as f:
            first_line = f.readline()
        assert first_line.startswith("#!/"), "restore.sh missing shebang"
        assert "bash" in first_line, "restore.sh should use bash"


def test_retention_matrix_exists():
    """Test that retention matrix documentation exists."""
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "operations"
    retention_doc = docs_dir / "RETENTION_MATRIX.md"
    
    assert retention_doc.exists(), f"Retention matrix not found at {retention_doc}"


def test_runbook_exists():
    """Test that backup/restore runbook exists."""
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "operations"
    runbook_doc = docs_dir / "BACKUP_RESTORE_RUNBOOK.md"
    
    assert runbook_doc.exists(), f"Runbook not found at {runbook_doc}"


def test_retention_matrix_has_content():
    """Test that retention matrix has required sections."""
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "operations"
    retention_doc = docs_dir / "RETENTION_MATRIX.md"
    
    if retention_doc.exists():
        content = retention_doc.read_text(encoding='utf-8')
        
        # Check for key sections
        assert "Retention Matrix" in content or "retention" in content.lower()
        assert "Backup" in content or "backup" in content.lower()
        assert "RPO" in content or "recovery point" in content.lower()
        assert "RTO" in content or "recovery time" in content.lower()


def test_runbook_has_procedures():
    """Test that runbook has required procedures."""
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "operations"
    runbook_doc = docs_dir / "BACKUP_RESTORE_RUNBOOK.md"
    
    if runbook_doc.exists():
        content = runbook_doc.read_text()
        
        # Check for key procedures
        assert "Procedure" in content or "Steps" in content
        assert "Backup" in content or "backup" in content.lower()
        assert "Restore" in content or "restore" in content.lower()
        assert "Troubleshoot" in content or "Error" in content


def test_backup_script_syntax():
    """Test that backup.sh has valid bash syntax."""
    import sys
    
    # Skip syntax check on Windows (bash may not be available)
    if sys.platform == "win32":
        pytest.skip("Bash syntax check not available on Windows")
    
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    backup_script = scripts_dir / "backup.sh"
    
    if backup_script.exists():
        # Check syntax with bash -n (dry run)
        result = subprocess.run(
            ["bash", "-n", str(backup_script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"backup.sh has syntax errors: {result.stderr}"


def test_restore_script_syntax():
    """Test that restore.sh has valid bash syntax."""
    import sys
    
    # Skip syntax check on Windows (bash may not be available)
    if sys.platform == "win32":
        pytest.skip("Bash syntax check not available on Windows")
    
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    restore_script = scripts_dir / "restore.sh"
    
    if restore_script.exists():
        # Check syntax with bash -n (dry run)
        result = subprocess.run(
            ["bash", "-n", str(restore_script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"restore.sh has syntax errors: {result.stderr}"
