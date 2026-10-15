"""Build a portable ZIP for the current OS: uv run --group build python build.py."""

from pathlib import Path
import platform
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parent
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--onefile', '--console', '--name', 'SubathonTimer',
        '--exclude-module', 'config', '--hidden-import', 'twitchAPI.type',
        'main.py',
    ], cwd=root, check=True)

    executable = 'SubathonTimer.exe' if sys.platform == 'win32' else 'SubathonTimer'
    archive = root / 'dist' / f'SubathonTimer-{platform.system()}.zip'
    # Explicit list: never sweep tokens, logs, or other local files into the ZIP.
    with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
        bundle.write(root / 'dist' / executable, f'SubathonTimer/{executable}')
        bundle.write(root / 'config.py', 'SubathonTimer/config.py')
        bundle.write(root / 'LICENSE', 'SubathonTimer/LICENSE')
        bundle.writestr('SubathonTimer/README.txt', (
            'Extract the whole folder to a writable location.\n'
            'Edit config.py (channel, OBS password, text source, and timer rules),\n'
            f'then run {executable}. Python and uv are not needed.\n'
            'Enable the OBS WebSocket server and create the configured text source.\n'
            'Follow the browser prompt to authorize Twitch on the first run.\n'
            'Keep config.py, user_token.json, and logs when updating the executable.\n'
            'Do not share user_token.json or a config containing your OBS password.\n'
            'Commands: p=pause, r=resume, e=export CSV, q=quit, s=set time.\n'
            'https://github.com/maskarauder/subathon-timer\n'
        ))
    print(f'Built {archive}')


if __name__ == '__main__':
    main()
