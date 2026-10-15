"""Keep editable settings and persistent data outside the frozen bundle."""

from importlib import import_module, util
from pathlib import Path
import sys


def app_directory():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_path(value):
    return app_directory() / value


def load_config():
    if not getattr(sys, 'frozen', False):
        return import_module('config')

    filename = app_directory() / 'config.py'
    if not filename.is_file():
        raise FileNotFoundError(f'Place config.py beside the executable: {filename}')
    spec = util.spec_from_file_location('config', filename)
    module = util.module_from_spec(spec)
    # Read the editable file on every launch, without a stale bytecode cache.
    exec(compile(filename.read_bytes(), str(filename), 'exec'), module.__dict__)
    sys.modules['config'] = module
    return module
