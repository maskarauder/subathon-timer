#!/usr/bin/env python3
import asyncio
import argparse
import sys
import traceback
from app_paths import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description='Twitch Subathon Timer')
    parser.add_argument('--check-config', action='store_true',
                        help='load config and dependencies without connecting')
    args = parser.parse_args(argv)
    config = load_config()
    from twitch import setup_twitch_listener

    if args.check_config:
        print(f'Configuration and dependencies loaded: {config.__file__}')
        return
    asyncio.run(setup_twitch_listener())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        if getattr(sys, 'frozen', False) and sys.stdin is not None and sys.stdin.isatty():
            try:
                input('Press Enter to close...')
            except (EOFError, KeyboardInterrupt):
                pass
        sys.exit(1)
