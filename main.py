#!/usr/bin/env python3
import asyncio
from twitch import setup_twitch_listener


def main():
    asyncio.run(setup_twitch_listener())
    
if __name__ == '__main__':
    main()