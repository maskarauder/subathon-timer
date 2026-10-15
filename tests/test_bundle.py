"""Offline integration checks, enabled after running build.py."""

from pathlib import Path
import platform
import subprocess
import sys
from zipfile import ZipFile

import pytest


ARCHIVE = Path(__file__).resolve().parents[1] / 'dist' / f'SubathonTimer-{platform.system()}.zip'
pytestmark = pytest.mark.skipif(not ARCHIVE.is_file(), reason='Run build.py to test the executable')


@pytest.fixture
def bundle(tmp_path):
    executable = 'SubathonTimer.exe' if sys.platform == 'win32' else 'SubathonTimer'
    with ZipFile(ARCHIVE) as archive:
        assert set(archive.namelist()) == {
            f'SubathonTimer/{executable}', 'SubathonTimer/config.py',
            'SubathonTimer/LICENSE', 'SubathonTimer/README.txt',
        }
        archive.extractall(tmp_path)
    binary = tmp_path / 'SubathonTimer' / executable
    if sys.platform != 'win32':
        binary.chmod(0o755)
    return binary


def check_config(binary, cwd):
    return subprocess.run([str(binary), '--check-config'], cwd=cwd,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)


def test_bundle_loads_dependencies_and_external_config(bundle, tmp_path):
    result = check_config(bundle, tmp_path)
    assert result.returncode == 0, result.stderr
    assert str(bundle.with_name('config.py')) in result.stdout
    assert not bundle.with_name('user_token.json').exists()
    assert not bundle.with_name('logs').exists()


def test_bundle_uses_edited_config_and_fails_clearly_if_missing(bundle, tmp_path):
    config = bundle.with_name('config.py')
    with config.open('a', encoding='utf-8') as stream:
        stream.write("\nraise RuntimeError('edited external config was loaded')\n")
    result = check_config(bundle, tmp_path)
    assert result.returncode != 0
    assert 'edited external config was loaded' in result.stderr
    config.unlink()
    result = check_config(bundle, tmp_path)
    assert result.returncode != 0
    assert 'Place config.py beside the executable' in result.stderr
