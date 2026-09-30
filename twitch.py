#!/usr/bin/env python3

# Twitch API
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import CodeFlow, UserAuthenticationStorageHelper
from twitchAPI.helper import first
from twitchAPI.object.eventsub import ChannelBitsUseEvent, ChannelSubscribeEvent, ChannelSubscriptionGiftEvent, ChannelSubscriptionMessageEvent, ChannelPointsCustomRewardRedemptionAddEvent
from twitchAPI.eventsub.websocket import EventSubWebsocket
from uuid import UUID

# App Specific
from helpers import fuzzy_strtime_to_int
from config import *
from obs import *
from threading import Thread
from os import path, makedirs
from random import randint
from pathlib import Path
from datetime import datetime, timezone
from time import monotonic
import json

import webbrowser

TOKEN_STORAGE_PATH = Path(__file__).with_name("user_token.json")
obs_thread = OBSThread()

# EventSub does not give channel.subscribe a billing-period identifier. Credit
# immediately, then match starts/messages for 24 hours; known months take precedence.
_subscription_credits = {}
_subscription_event_ids = {}


def apply_subscription_time(data, tier, value, bonus):
    metadata = getattr(data, 'metadata', None) or {}
    event_id = (metadata.get('message_id') if isinstance(metadata, dict)
                else getattr(metadata, 'message_id', None))
    if event_id and event_id in _subscription_event_ids:
        return 0, 0, 'duplicate_event'

    event = data.event
    key = (getattr(event, 'broadcaster_user_id', TARGET_CHANNEL),
           getattr(event, 'user_id', None) or event.user_login.lower())
    months = getattr(event, 'cumulative_months', None)
    now = monotonic()
    previous = _subscription_credits.get(key)
    if previous and months is not None and previous['months'] is not None and months < previous['months']:
        return 0, 0, 'stale_subscription'
    same_period = previous and (
        (months is not None and months == previous['months']) or
        (now - previous['at'] < 24 * 60 * 60 and
         (months is None or previous['months'] is None)))
    reason = 'credited'
    record = dict(tier=tier, base=value, total=value + bonus, months=months, at=now)
    if same_period:
        record['months'] = months if months is not None else previous['months']
        record['at'] = previous['at']
        if tier <= previous['tier']:
            record = dict(previous, months=record['months'])
            value, bonus, reason = 0, 0, 'duplicate_subscription'
        else:
            delta = max(0, value + bonus - previous['total'])
            record['total'] = max(record['total'], previous['total'])
            value = min(max(0, value - previous['base']), delta)
            bonus, reason = delta - value, 'tier_upgrade'

    if value + bonus:
        obs_thread.update_time(value + bonus)
    _subscription_credits[key] = record
    if event_id:
        _subscription_event_ids[event_id] = None
        if len(_subscription_event_ids) > 1024:
            del _subscription_event_ids[next(iter(_subscription_event_ids))]
    return value, bonus, reason


async def write_event_log(data, timer_delta, reason, requested=None):
    if not LOG_ENABLED:
        return
    makedirs(LOG_DIRECTORY, exist_ok=True)
    record = dict(received_at=datetime.now(timezone.utc).isoformat(),
                  timer_delta_seconds=timer_delta, reason=reason,
                  requested_seconds=timer_delta if requested is None else requested,
                  payload=data.to_dict())
    with open(path.join(LOG_DIRECTORY, EVENTS_LOGFILE), 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')


async def callback_bits(data: ChannelBitsUseEvent) -> None:
    global obs_thread

    nbits = data.event.bits

    if RANDOMIZER_ENABLED:
        interval = (0, 0)
        for key, value in RANDOMIZER_BITS_SETTINGS.items():
            if nbits < key:
                break

            interval = value
        
        randomized_time = randint(interval[0], interval[1])
    else:
        randomized_time = 0

    if nbits >= TRIGGER_BITS_VALUE:
        value = int(nbits * BITS_VALUE)
        obs_thread.update_time(value + randomized_time)
        await write_event_log(data, value + randomized_time, 'credited')

    else:
        return


async def callback_channelpoints(data: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    global obs_thread

    reward = data.event.reward.title
    if reward.lower() != CHANELLPOINTS_REWARD_NAME.lower():
        return
    
    obs_thread.update_time(CHANNELPOINTS_REWARD_VALUE)
    await write_event_log(data, CHANNELPOINTS_REWARD_VALUE, 'credited')


# This includes those new subs from Gift Subs
async def callback_new_subscriber(data: ChannelSubscribeEvent) -> None:
    tier = data.event.tier

    if tier == '1000':
        tier = 1
        value = TIER_1_VALUE
    elif tier == '2000':
        tier = 2
        value = TIER_2_VALUE
    elif tier == '3000':
        tier = 3
        value = TIER_3_VALUE

    if RANDOMIZER_ENABLED:
        if tier in RANDOMIZER_SUBS_SETTINGS:
            randomized_time = randint(RANDOMIZER_SUBS_SETTINGS[tier][0], RANDOMIZER_SUBS_SETTINGS[tier][1])
    else:
        randomized_time = 0

    requested = value + randomized_time
    value, randomized_time, reason = apply_subscription_time(data, tier, value, randomized_time)
    await write_event_log(data, value + randomized_time, reason, requested)


async def callback_resubscriber(data: ChannelSubscriptionMessageEvent) -> None:
    tier = data.event.tier
    value = 0
    
    if tier == '1000':
        tier = 1
        value = TIER_1_VALUE
    elif tier == '2000':
        tier = 2
        value = TIER_2_VALUE
    elif tier == '3000':
        tier = 3
        value = TIER_3_VALUE

    if RANDOMIZER_ENABLED:
        if tier in RANDOMIZER_SUBS_SETTINGS:
            randomized_time = randint(RANDOMIZER_SUBS_SETTINGS[tier][0], RANDOMIZER_SUBS_SETTINGS[tier][1])
    else:
        randomized_time = 0

    requested = value + randomized_time
    value, randomized_time, reason = apply_subscription_time(data, tier, value, randomized_time)
    await write_event_log(data, value + randomized_time, reason, requested)

    # TODO: Maybe support multimonth subs?
    # data.event.duration_months


# Track the gifter and add only the configured bundle bonus here.
async def callback_somebody_gifted(data: ChannelSubscriptionGiftEvent) -> None:
    nsubs = data.event.total
    if RANDOMIZER_ENABLED:
        interval = (0, 0)
        for key, value in RANDOMIZER_BUNDLE_SETTINGS.items():
            if nsubs < key:
                break

            interval = value
        
        randomized_time = randint(interval[0], interval[1])

        obs_thread.update_time(randomized_time)
    else:
        randomized_time = 0

    await write_event_log(data, randomized_time, 'gift_bundle_bonus')


async def generate_device_tokens(twitch: Twitch, scopes):
    """Run Device Code Flow only when stored credentials are unavailable."""
    auth = CodeFlow(twitch, scopes)

    code, url = await auth.get_code()
    webbrowser.open(url, new=2)

    print(f"Please enter code {code} in the browser to continue.")
    return await auth.wait_for_auth_complete()


async def setup_twitch_listener():
    global obs_thread

    twitch = await Twitch(APP_TOKEN, None, authenticate_app=False)

    target_scope = TARGET_SCOPE

    auth_helper = UserAuthenticationStorageHelper(
        twitch,
        target_scope,
        storage_path=TOKEN_STORAGE_PATH,
        auth_generator_func=generate_device_tokens,
    )

    await auth_helper.bind()
    
    user = await first(twitch.get_users(logins=[TARGET_CHANNEL]))

    # Start EventSub
    eventsub = EventSubWebsocket(twitch)
    eventsub.start()

    obs_thread.start()

    if AuthScope.BITS_READ in target_scope:
        await eventsub.listen_channel_bits_use(user.id, callback_bits)
    if AuthScope.CHANNEL_READ_SUBSCRIPTIONS in target_scope:
        # First time subscribers and gift subs
        await eventsub.listen_channel_subscribe(user.id, callback_new_subscriber)
        # Resubs
        await eventsub.listen_channel_subscription_message(user.id, callback_resubscriber)
    if AuthScope.CHANNEL_READ_REDEMPTIONS in target_scope:
        await eventsub.listen_channel_points_custom_reward_redemption_add(user.id, callback_channelpoints)

    if LOG_ENABLED:
        if AuthScope.CHANNEL_READ_SUBSCRIPTIONS in target_scope:
            await eventsub.listen_channel_subscription_gift(user.id, callback_somebody_gifted)

    running = True
    while running:
        try:
            user_input = input('Enter time or seconds to adjust time (p=pause, r=resume, q=quit, s=set exact):')
            match user_input:
                case 'p':
                    obs_thread.pause = True
                case 'r':
                    if not obs_thread.is_alive():
                        obs_thread = OBSThread()
                        obs_thread.start()
                    obs_thread.pause = False
                case 'q':
                    obs_thread.ready_to_die = True
                    obs_thread.join()
                    running = False
                case 's':
                    user_input = input('Input new value (exact seconds or HH:MM:ss, anything else cancels):')
                    try:
                        new_time = fuzzy_strtime_to_int(user_input)
                        obs_thread.set_time(new_time)
                    except ValueError:
                        print('Input not recognized.')
                case _:
                    try:
                        time_to_add = fuzzy_strtime_to_int(user_input)
                        obs_thread.update_time(time_to_add)
                    except ValueError:
                        print('Input not recognized.')
        except EOFError:
            print('Dying...')
            break
            
    print('Timer dying... This is currently bugged, just close the window.')
    await eventsub.stop()
    await twitch.close()