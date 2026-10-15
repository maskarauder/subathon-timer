from pathlib import Path
import sys

import pytest

import app_paths
import twitch


@pytest.fixture
def frozen_app(tmp_path, monkeypatch):
    directory = tmp_path / 'app'
    directory.mkdir()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(directory / 'SubathonTimer.exe'))
    monkeypatch.chdir(tmp_path)
    return directory


def test_source_paths_stay_beside_source_after_chdir(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.chdir(tmp_path)
    assert app_paths.data_path('user_token.json') == Path(app_paths.__file__).parent / 'user_token.json'


def test_frozen_paths_and_log_writes_stay_beside_executable(frozen_app, monkeypatch):
    assert app_paths.data_path('user_token.json') == frozen_app / 'user_token.json'
    monkeypatch.setattr(twitch, 'LOG_ENABLED', True)
    monkeypatch.setattr(twitch, 'LOG_DIRECTORY', 'logs')
    monkeypatch.setattr(twitch, 'EVENTS_LOGFILE', 'events.jsonl')
    twitch._write_log_record({'record_type': 'test'})
    assert (frozen_app / 'logs' / 'events.jsonl').is_file()
    assert not (frozen_app.parent / 'logs').exists()
    absolute = frozen_app.parent / 'custom-logs'
    assert app_paths.data_path(absolute) == absolute


def test_frozen_config_uses_edits_and_rejects_missing_file(frozen_app, monkeypatch):
    # Restore the original module when the test ends.
    monkeypatch.setitem(sys.modules, 'config', sys.modules['config'])
    filename = frozen_app / 'config.py'
    filename.write_text('TIER_1_VALUE = 123\n', encoding='utf-8')
    assert app_paths.load_config().TIER_1_VALUE == 123
    filename.write_text('TIER_1_VALUE = 456\n', encoding='utf-8')
    assert app_paths.load_config().TIER_1_VALUE == 456
    assert sys.modules['config'].__file__ == str(filename)
    filename.unlink()
    with pytest.raises(FileNotFoundError, match='Place config.py beside the executable'):
        app_paths.load_config()
