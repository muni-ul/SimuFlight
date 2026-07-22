import subprocess
import sys


def test_module_entrypoint_help():
    result = subprocess.run([sys.executable, "-m", "astraloop", "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "list-scenarios" in result.stdout
    assert "run" in result.stdout
