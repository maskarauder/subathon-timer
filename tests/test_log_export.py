import asyncio
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import twitch
from log_export import export_csv_logs


class LogExportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.source = self.directory / 'custom-events.jsonl'

    def record(self, kind, delta=500, reason='credited', **event):
        return dict(received_at='2026-09-30T20:00:01+00:00',
                    timer_delta_seconds=delta, requested_seconds=500, reason=reason,
                    payload=dict(subscription=dict(type=kind, id='subscription-id'),
                                 metadata=dict(message_id='message-id', subscription_type=kind,
                                               message_timestamp='2026-09-30T20:00:00+00:00'),
                                 event=event))

    def write(self, *records):
        self.source.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records),
                               encoding='utf-8')

    def read_csv(self, directory, filename):
        with (directory / filename).open(newline='', encoding='utf-8-sig') as report:
            return list(csv.DictReader(report))

    def test_export_preserves_duplicates_upgrades_and_all_event_types(self):
        message = 'Hello, "Wooper"\n¡Gracias!\u2028Next line'
        self.write(
            self.record('channel.subscribe', tier='1000', is_gift=False, user_login='wooper64'),
            self.record('channel.subscription.message', 0, 'duplicate_subscription',
                        tier='1000', cumulative_months=42, duration_months=1,
                        message=dict(text=message), user_login='wooper64'),
            self.record('channel.subscribe', 2000, 'tier_upgrade', tier='3000', user_login='wooper64'),
            self.record('channel.subscription.gift', 0, 'gift_bundle_bonus',
                        tier='1000', total=5, is_anonymous=True, cumulative_total=None),
            self.record('channel.bits.use', 100, bits=100, message=None,
                        power_up=dict(type='gigantify_an_emote')),
            self.record('channel.channel_points_custom_reward_redemption.add', 100,
                        id='redemption', reward=dict(id='reward', title='Add to Subathon', cost=1000),
                        user_input='Please!', status='fulfilled'),
        )
        original = self.source.read_bytes()
        directory, counts, skipped = export_csv_logs(self.source)
        self.assertEqual(skipped, [])
        self.assertEqual(counts, {'subscriptions.csv': 3, 'gifted_subs.csv': 1,
                                 'bits.csv': 1, 'channelpoints.csv': 1, 'events.csv': 6})
        subscriptions = self.read_csv(directory, 'subscriptions.csv')
        self.assertEqual(sum(float(r['timer_delta_seconds']) for r in subscriptions), 2500)
        self.assertEqual([r['reason'] for r in subscriptions],
                         ['credited', 'duplicate_subscription', 'tier_upgrade'])
        self.assertEqual(subscriptions[1]['requested_seconds'], '500')
        self.assertEqual(subscriptions[1]['message'], message)
        self.assertEqual(subscriptions[1]['cumulative_months'], '42')
        self.assertEqual(subscriptions[2]['tier'], '3')
        self.assertEqual(subscriptions[0]['cumulative_months'], '')
        self.assertEqual(subscriptions[0]['message_id'], 'message-id')
        self.assertEqual(subscriptions[0]['message_timestamp'], '2026-09-30T20:00:00+00:00')
        gift = self.read_csv(directory, 'gifted_subs.csv')[0]
        self.assertEqual((gift['total'], gift['is_anonymous'], gift['cumulative_total']), ('5', 'True', ''))
        bits = self.read_csv(directory, 'bits.csv')[0]
        self.assertEqual((bits['bits'], bits['message'], bits['power_up_type']),
                         ('100', '', 'gigantify_an_emote'))
        points = self.read_csv(directory, 'channelpoints.csv')[0]
        self.assertEqual((points['redemption_id'], points['reward_title'], points['reward_cost']),
                         ('redemption', 'Add to Subathon', '1000'))
        self.assertEqual(self.source.read_bytes(), original)

    def test_invalid_and_partial_lines_are_reported_and_valid_rows_survive(self):
        valid = json.dumps(self.record('channel.subscribe', tier='1000')).encode()
        self.source.write_bytes(valid + b'\n\nnot-json\n[]\n{"payload": null}\n{"text": "\xc3')
        directory, counts, skipped = export_csv_logs(self.source)
        self.assertEqual(skipped, [3, 4, 5, 6])
        self.assertEqual(counts['events.csv'], 1)
        self.assertEqual(self.read_csv(directory, 'events.csv')[0]['log_line'], '1')

    def test_repeated_exports_keep_previous_reports_and_empty_files_have_headers(self):
        self.source.touch()
        first, counts, _ = export_csv_logs(self.source)
        original = (first / 'events.csv').read_bytes()
        self.assertTrue(all(count == 0 for count in counts.values()))
        self.assertIn(b'timer_delta_seconds', original)
        self.write(self.record('channel.subscribe'))
        second, counts, _ = export_csv_logs(self.source)
        self.assertNotEqual(first, second)
        self.assertEqual((first / 'events.csv').read_bytes(), original)
        self.assertEqual(counts['events.csv'], 1)

    def test_messages_are_spreadsheet_text_and_numeric_values_remain_numeric(self):
        self.write(self.record('channel.subscription.message', -3,
                               message=dict(text='=SUM(1,2)'), user_name='  @name'))
        directory, _, _ = export_csv_logs(self.source)
        row = self.read_csv(directory, 'subscriptions.csv')[0]
        self.assertEqual(row['message'], "'=SUM(1,2)")
        self.assertEqual(row['user_name'], "'  @name")
        self.assertEqual(row['timer_delta_seconds'], '-3')

    def test_metadata_fallback_and_unrecognised_types_are_in_combined_report(self):
        record = self.record('future.event', 0)
        del record['payload']['subscription']
        self.write(record)
        directory, counts, _ = export_csv_logs(self.source)
        self.assertEqual(counts['events.csv'], 1)
        self.assertEqual(counts['subscriptions.csv'], 0)
        self.assertEqual(self.read_csv(directory, 'events.csv')[0]['event_type'], 'future.event')

    def terminal(self, commands, **extra):
        client = MagicMock(close=AsyncMock())
        socket = MagicMock(stop=AsyncMock())
        obs = MagicMock()
        settings = dict(Twitch=AsyncMock(return_value=client),
                        UserAuthenticationStorageHelper=MagicMock(return_value=MagicMock(bind=AsyncMock())),
                        first=AsyncMock(return_value=SimpleNamespace(id='channel')),
                        EventSubWebsocket=MagicMock(return_value=socket), obs_thread=obs,
                        TARGET_SCOPE=[], LOG_DIRECTORY=str(self.directory), EVENTS_LOGFILE=self.source.name,
                        write_startup_log=MagicMock())
        settings.update(extra)
        with patch.multiple(twitch, **settings), patch('builtins.input', side_effect=commands), \
                patch('builtins.print') as printed:
            asyncio.run(twitch.setup_twitch_listener())
        return obs, printed

    def test_terminal_export_aliases_and_existing_timer_commands(self):
        self.write(self.record('channel.subscribe'))
        obs, printed = self.terminal(['e', 'export', '123', 'p', 'r', 's', '321', 'q'])
        self.assertEqual(len(list((self.directory / 'exports').iterdir())), 2)
        obs.update_time.assert_called_once_with(123)
        obs.set_time.assert_called_once_with(321)
        obs.join.assert_called_once_with()
        self.assertFalse(obs.pause)
        self.assertTrue(any('CSV export saved to' in str(c) for c in printed.call_args_list))

    def test_missing_log_does_not_end_terminal_session(self):
        obs, printed = self.terminal(['e', '123', 'q'])
        obs.update_time.assert_called_once_with(123)
        self.assertFalse((self.directory / 'exports').exists())
        self.assertTrue(any('Could not export logs:' in str(c) for c in printed.call_args_list))

    def test_startup_records_are_not_timer_events_and_export_retains_run_ids(self):
        event = self.record('channel.subscribe', tier='1000')
        event['run_id'] = 'second-run'
        self.write(
            dict(record_type='startup', run_id='first-run', config=dict(TIER_1_VALUE=500)),
            self.record('channel.subscribe', tier='1000'),
            dict(record_type='startup', run_id='second-run', config=dict(TIER_1_VALUE=750)),
            event,
        )
        directory, counts, skipped = export_csv_logs(self.source)
        self.assertEqual(skipped, [])
        self.assertEqual(counts['events.csv'], 2)
        rows = self.read_csv(directory, 'subscriptions.csv')
        self.assertEqual([r['log_line'] for r in rows], ['2', '4'])
        self.assertEqual([r['run_id'] for r in rows], ['', 'second-run'])


if __name__ == '__main__':
    unittest.main()
