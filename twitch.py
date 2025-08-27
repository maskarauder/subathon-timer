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

from csv import writer

import webbrowser

obs_thread = OBSThread()

async def write_to_logfile(file: str, message: list):
    with open(path.join(LOG_DIRECTORY, file), 'a+') as f:
        w = writer(f)
        w.writerow(message)


async def callback_bits(data: ChannelBitsUseEvent) -> None:
    global obs_thread

    nbits = data.event.bits
    if nbits >= TRIGGER_BITS_VALUE:
        obs_thread.update_time(nbits * BITS_VALUE)

    if not LOG_ENABLED:
        return
    
    user_login = data.event.user_login
    public_name = data.event.user_name

    if not user_login:
        user_login = 'anon'
    if not public_name:
        public_name = 'anon'

    msg = data.event.message.text

    await write_to_logfile(BITS_LOGFILE, [user_login, public_name, nbits, msg, nbits * BITS_VALUE])
    

async def callback_channelpoints(data: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    global obs_thread

    reward = data.event.reward.title
    if reward.lower() != CHANELLPOINTS_REWARD_NAME.lower():
        return
    
    obs_thread.update_time(CHANNELPOINTS_REWARD_VALUE)

def add_sub_time(tier: str) -> None:
    global obs_thread

    match tier:
        case '1000':
            obs_thread.update_time(TIER_1_VALUE)
        case '2000':
            obs_thread.update_time(TIER_2_VALUE)
        case '3000':
            obs_thread.update_time(TIER_3_VALUE)
        case _:
            raise Exception('Twitch added some new kind of sub?')


# This includes those new subs from Gift Subs
async def callback_new_subscriber(data: ChannelSubscribeEvent) -> None:
    tier = data.event.tier
    add_sub_time(tier)

    if not LOG_ENABLED:
        return
    
    login_name = data.event.user_login
    public_name = data.event.user_name

    if data.event.tier == '1000':
        tier = '1'
    elif data.event.tier == '2000':
        tier = '2'
    elif data.event.tier == '3000':
        tier = '3'

    if data.event.is_gift:
        msg = 'gifted'
    else:
        msg = 'new sub'

    await write_to_logfile(SUBSCRIPTION_LOGFILE, [login_name, public_name, 0, tier, msg])


async def callback_resubscriber(data: ChannelSubscriptionMessageEvent) -> None:
    tier = data.event.tier
    add_sub_time(tier)

    if not LOG_ENABLED:
        return

    login_name = data.event.user_login
    public_name = data.event.user_name
    value = 0

    if data.event.tier == '1000':
        tier = '1'
        value = TIER_1_VALUE
    elif data.event.tier == '2000':
        tier = '2'
        value = TIER_2_VALUE
    elif data.event.tier == '3000':
        tier = '3'
        value = TIER_3_VALUE

    # TODO: Maybe support multimonth subs?
    # data.event.duration_months?
    await write_to_logfile(SUBSCRIPTION_LOGFILE, [login_name, public_name, data.event.cumulative_months, tier, data.event.message.text, value])


# This is to track who is gifting the subs, does not interact with the timer
async def callback_somebody_gifted(data: ChannelSubscriptionGiftEvent) -> None:
    if data.event.is_anonymous:
        login_name = 'anon'
        public_name = 'anon'
    else:
        login_name = data.event.user_login
        public_name = data.event.user_name

    nsubs = data.event.total
    if data.event.tier == '1000':
        tier = '1'
    elif data.event.tier == '2000':
        tier = '2'
    elif data.event.tier == '3000':
        tier = '3'
    
    await write_to_logfile(GIFT_PACKS_LOGFILE, [login_name, public_name, nsubs, tier])


async def setup_twitch_listener():
    global obs_thread

    twitch = await Twitch(APP_TOKEN, None, authenticate_app=False)

    target_scope = TARGET_SCOPE

    auth = CodeFlow(twitch, target_scope)

    code, url = await auth.get_code()
    browser = webbrowser.get(None)
    browser.open(url, new=2)

    print(f'Please enter code {code} in the browser to continue.')
    token, refresh_token = await auth.wait_for_auth_complete()

    #add User authentication
    await twitch.set_user_authentication(token, target_scope, refresh_token)
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

        if not path.exists(LOG_DIRECTORY):
            makedirs(LOG_DIRECTORY)

        if not path.exists(path.join(LOG_DIRECTORY, SUBSCRIPTION_LOGFILE)):
            await write_to_logfile(SUBSCRIPTION_LOGFILE, ['User login', 'Username', 'Streak', 'Tier', 'Resub message or source of new sub', 'Time added'])
        if not path.exists(path.join(LOG_DIRECTORY, BITS_LOGFILE)):
            await write_to_logfile(BITS_LOGFILE, ['User login', 'Username', 'Bits amount', 'Message', 'Time added'])
        if not path.exists(path.join(LOG_DIRECTORY, GIFT_PACKS_LOGFILE)):
            await write_to_logfile(GIFT_PACKS_LOGFILE, ['User login', 'Username', '# Subs', 'Tier'])

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