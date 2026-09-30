import asyncio
import itertools
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import twitch


class SubscriptionDeduplicationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.obs = MagicMock()
        self.ids = itertools.count()
        settings = patch.multiple(
            twitch, obs_thread=self.obs, LOG_ENABLED=True,
            LOG_DIRECTORY=str(self.directory / 'logs'), RANDOMIZER_ENABLED=False,
            _subscription_credits={}, _subscription_event_ids={})
        settings.start()
        self.addCleanup(settings.stop)
        clock = patch.object(twitch, 'monotonic', return_value=0)
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    def event(self, tier='1000', months=None, user='wooper64', event_id=None, gifted=False):
        kind = 'channel.subscribe' if months is None else 'channel.subscription.message'
        payload = dict(user_id=user, user_login=user, user_name=user,
                       broadcaster_user_id='channel', tier=tier, is_gift=gifted)
        if months is not None:
            payload.update(cumulative_months=months, duration_months=1,
                           message=dict(text='hello\nthere', emotes=[]))
        event_class = (twitch.ChannelSubscribeEvent if months is None
                       else twitch.ChannelSubscriptionMessageEvent)
        return event_class(
            event=payload, subscription=dict(type=kind, id='subscription'),
            metadata=dict(message_id=event_id or f'event-{next(self.ids)}',
                          message_type='notification', subscription_type=kind,
                          subscription_version='1',
                          message_timestamp='2026-09-30T19:00:00Z'))

    def apply(self, data, value=500, bonus=0):
        return twitch.apply_subscription_time(data, int(data.event.tier) // 1000, value, bonus)

    def test_start_then_message_awards_once(self):
        self.apply(self.event(), bonus=10)
        self.assertEqual(self.apply(self.event(months=42), bonus=30),
                         (0, 0, 'duplicate_subscription'))
        self.obs.update_time.assert_called_once_with(510)

    def test_message_then_start_awards_once(self):
        self.apply(self.event(months=42))
        self.apply(self.event())
        self.obs.update_time.assert_called_once_with(500)

    def test_delayed_message_inside_window_awards_once(self):
        self.apply(self.event())
        self.clock.return_value = 23 * 60 * 60
        self.apply(self.event(months=42))
        self.obs.update_time.assert_called_once_with(500)

    def test_same_month_message_is_ignored_after_window(self):
        self.apply(self.event(months=42))
        self.clock.return_value = 2 * 24 * 60 * 60
        self.apply(self.event(months=42))
        self.obs.update_time.assert_called_once_with(500)

    def test_next_month_still_awards_inside_window(self):
        self.apply(self.event(months=42))
        self.apply(self.event(months=43))
        self.assertEqual(self.obs.update_time.call_args_list, [call(500), call(500)])

    def test_stale_month_does_not_replace_current_credit(self):
        self.apply(self.event(months=43))
        self.assertEqual(self.apply(self.event(months=42)), (0, 0, 'stale_subscription'))
        self.apply(self.event(months=43))
        self.obs.update_time.assert_called_once_with(500)

    def test_duplicate_message_id_is_ignored_after_window(self):
        data = self.event(event_id='same-id')
        self.apply(data)
        self.clock.return_value = 2 * 24 * 60 * 60
        self.assertEqual(self.apply(data), (0, 0, 'duplicate_event'))
        self.obs.update_time.assert_called_once_with(500)

    def test_unmatched_start_can_award_after_window(self):
        self.apply(self.event())
        self.clock.return_value = 24 * 60 * 60
        self.apply(self.event())
        self.assertEqual(self.obs.update_time.call_args_list, [call(500), call(500)])

    def test_upgrade_tops_up_total_including_bonus(self):
        self.apply(self.event(), value=712.8, bonus=402)
        self.apply(self.event(months=42), value=712.8, bonus=219)
        value, bonus, reason = self.apply(self.event(tier='3000'), value=4104, bonus=2404)
        self.assertEqual(reason, 'tier_upgrade')
        self.assertAlmostEqual(value + bonus, 6508 - 1114.8)
        self.apply(self.event(tier='3000', months=42), value=4104, bonus=505)
        self.assertAlmostEqual(sum(c.args[0] for c in self.obs.update_time.call_args_list), 6508)

    def test_lower_tier_after_upgrade_is_ignored(self):
        self.apply(self.event(tier='3000', months=42), value=2500)
        self.apply(self.event(), value=500)
        self.obs.update_time.assert_called_once_with(2500)

    def test_upgrade_with_lower_random_total_never_removes_time(self):
        self.apply(self.event(), value=500, bonus=1000)
        self.assertEqual(sum(self.apply(self.event(tier='2000'), value=1000)[:2]), 0)
        self.obs.update_time.assert_called_once_with(1500)

    def test_gift_recipient_and_message_award_once(self):
        self.apply(self.event(gifted=True))
        self.apply(self.event(months=42))
        self.obs.update_time.assert_called_once_with(500)

    def test_different_recipients_are_independent(self):
        self.apply(self.event(user='one', gifted=True))
        self.apply(self.event(user='two', gifted=True))
        self.assertEqual(self.obs.update_time.call_args_list, [call(500), call(500)])

    def test_obs_exception_leaves_event_retryable(self):
        data = self.event()
        self.obs.update_time.side_effect = ConnectionError('offline')
        with self.assertRaises(ConnectionError):
            self.apply(data)
        self.assertEqual(twitch._subscription_credits, {})
        self.assertEqual(twitch._subscription_event_ids, {})
        self.obs.update_time.side_effect = None
        self.assertEqual(self.apply(data), (500, 0, 'credited'))

    def test_callbacks_write_audit_for_award_and_duplicate(self):
        asyncio.run(twitch.callback_new_subscriber(self.event()))
        asyncio.run(twitch.callback_resubscriber(self.event(months=42)))
        records = [json.loads(line) for line in (self.directory / 'logs/events.jsonl').read_text().splitlines()]
        self.assertEqual([r['timer_delta_seconds'] for r in records], [twitch.TIER_1_VALUE, 0])
        self.assertEqual(records[1]['reason'], 'duplicate_subscription')
        self.assertEqual(records[1]['requested_seconds'], twitch.TIER_1_VALUE)
        self.assertEqual(records[1]['payload']['event']['cumulative_months'], 42)
        self.assertEqual(records[1]['payload']['event']['message']['text'], 'hello\nthere')
        self.assertEqual(records[1]['payload']['subscription']['type'], 'channel.subscription.message')
        self.assertEqual(records[1]['payload']['metadata']['message_id'], 'event-1')
        sent = datetime.fromisoformat(records[1]['payload']['metadata']['message_timestamp'])
        received = datetime.fromisoformat(records[1]['received_at'])
        self.assertEqual(sent.tzinfo, timezone.utc)
        self.assertEqual(received.tzinfo, timezone.utc)
        self.assertEqual([p.name for p in (self.directory / 'logs').iterdir()], ['events.jsonl'])

    def test_all_event_types_share_one_log_file(self):
        asyncio.run(twitch.callback_new_subscriber(self.event()))
        asyncio.run(twitch.callback_bits(twitch.ChannelBitsUseEvent(
            event=dict(bits=100, message=None, user_login='cheerer', user_name='Cheerer'))))
        asyncio.run(twitch.callback_somebody_gifted(twitch.ChannelSubscriptionGiftEvent(
            event=dict(total=2, tier='1000', is_anonymous=True))))
        asyncio.run(twitch.callback_channelpoints(twitch.ChannelPointsCustomRewardRedemptionAddEvent(
            event=dict(reward=dict(title=twitch.CHANELLPOINTS_REWARD_NAME)))))
        log_directory = self.directory / 'logs'
        self.assertEqual([p.name for p in log_directory.iterdir()], ['events.jsonl'])
        records = [json.loads(line) for line in (log_directory / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([r['timer_delta_seconds'] for r in records],
                         [twitch.TIER_1_VALUE, int(100 * twitch.BITS_VALUE),
                          0, twitch.CHANNELPOINTS_REWARD_VALUE])
        self.assertIsNone(records[1]['payload']['event'].get('message'))
        self.assertTrue(records[2]['payload']['event']['is_anonymous'])

    def test_logging_can_be_disabled(self):
        with patch.object(twitch, 'LOG_ENABLED', False):
            asyncio.run(twitch.callback_new_subscriber(self.event()))
            asyncio.run(twitch.callback_resubscriber(self.event(months=42)))
        self.assertFalse((self.directory / 'logs').exists())
        self.obs.update_time.assert_called_once_with(twitch.TIER_1_VALUE)


if __name__ == '__main__':
    unittest.main()
