import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import twitch


class StartupLogTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / 'logs' / 'custom-events.jsonl'
        settings = patch.multiple(twitch, LOG_ENABLED=True,
                                  LOG_DIRECTORY=str(self.source.parent),
                                  EVENTS_LOGFILE=self.source.name)
        settings.start()
        self.addCleanup(settings.stop)

    def records(self):
        return [json.loads(line) for line in self.source.read_text(encoding='utf-8').splitlines()]

    def test_startup_captures_effective_rules_and_excludes_private_or_unknown_settings(self):
        private = 'private-sentinel-do-not-log'
        with patch.multiple(twitch, APP_TOKEN=private, OBS_WEBSOCKET_PASSWORD=private,
                            OBS_HOST=private, OBS_SCENE_NAME=private, OBS_SCENEITEM_NAME=private,
                            TOKEN_STORAGE_PATH=Path(private),
                            NEW_PRIVATE_SETTING=private, create=True), \
                patch.multiple(twitch, TIER_1_VALUE=712.8, RANDOMIZER_ENABLED=True,
                               RANDOMIZER_SUBS_SETTINGS={1: (750, 1500)},
                               RANDOMIZER_BITS_SETTINGS={100: (30, 120)},
                               RANDOMIZER_BUNDLE_SETTINGS={5: (60, 300)}):
            twitch.write_startup_log()
        record = self.records()[0]
        self.assertEqual(record['record_type'], 'startup')
        self.assertEqual(set(record['config']), {
            'TARGET_CHANNEL', 'DEFAULT_START_TIME', 'TRIGGER_BITS_VALUE', 'BITS_VALUE',
            'TIER_1_VALUE', 'TIER_2_VALUE', 'TIER_3_VALUE', 'CHANNELPOINTS_ALLOWED',
            'CHANELLPOINTS_REWARD_NAME', 'CHANNELPOINTS_REWARD_VALUE', 'RANDOMIZER_ENABLED',
            'RANDOMIZER_BITS_SETTINGS', 'RANDOMIZER_SUBS_SETTINGS', 'RANDOMIZER_BUNDLE_SETTINGS',
            'TARGET_SCOPE',
        })
        self.assertEqual(record['config']['TIER_1_VALUE'], 712.8)
        self.assertEqual(record['config']['RANDOMIZER_SUBS_SETTINGS'], {'1': [750, 1500]})
        self.assertEqual(record['config']['RANDOMIZER_BITS_SETTINGS'], {'100': [30, 120]})
        self.assertEqual(record['config']['RANDOMIZER_BUNDLE_SETTINGS'], {'5': [60, 300]})
        self.assertEqual(record['config']['TARGET_SCOPE'], [scope.name for scope in twitch.TARGET_SCOPE])
        self.assertNotIn(private, self.source.read_text(encoding='utf-8'))
        self.assertNotIn(str(self.source.parent), self.source.read_text(encoding='utf-8'))
        self.assertEqual(datetime.fromisoformat(record['received_at']).utcoffset(), timedelta(0))
        UUID(record['run_id'])

    def test_startup_is_first_before_auth_and_events_share_its_run_id(self):
        payload = dict(subscription=dict(type='channel.subscribe'), event=dict(tier='1000'))
        event = SimpleNamespace(to_dict=lambda: payload)

        async def authenticate(*args, **kwargs):
            self.assertEqual([r['record_type'] for r in self.records()], ['startup'])
            await twitch.write_event_log(event, 500, 'credited')
            raise ConnectionError('test stops before connecting')

        with patch.object(twitch, 'Twitch', AsyncMock(side_effect=authenticate)), \
                patch.object(twitch, 'obs_thread', MagicMock()) as obs:
            with self.assertRaises(ConnectionError):
                asyncio.run(twitch.setup_twitch_listener())
        startup, credited = self.records()
        self.assertEqual(credited['record_type'], 'event')
        self.assertEqual(credited['run_id'], startup['run_id'])
        self.assertEqual(credited['timer_delta_seconds'], 500)
        self.assertEqual(credited['payload'], payload)
        obs.update_time.assert_not_called()

    def test_logging_disabled_creates_no_file_for_startup_or_events(self):
        with patch.object(twitch, 'LOG_ENABLED', False):
            twitch.write_startup_log()
            asyncio.run(twitch.write_event_log(SimpleNamespace(), 0, 'credited'))
        self.assertFalse(self.source.parent.exists())


if __name__ == '__main__':
    unittest.main()
