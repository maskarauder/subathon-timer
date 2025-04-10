#!/usr/bin/env python3

# Twitch API
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import CodeFlow, UserAuthenticationStorageHelper
from twitchAPI.helper import first
from twitchAPI.object.eventsub import ChannelCheerEvent, ChannelSubscribeEvent, ChannelSubscriptionGiftEvent, ChannelSubscriptionMessageEvent, ChannelPointsCustomRewardRedemptionAddEvent
from twitchAPI.eventsub.websocket import EventSubWebsocket
from uuid import UUID

# App Specific
from helpers import fuzzy_strtime_to_int
from config import *
from obs import *
from threading import Thread

import webbrowser

obs_thread = OBSThread()

async def callback_bits(data: ChannelCheerEvent) -> None:
    global obs_thread

    nbits = data.event.bits
    if nbits >= TRIGGER_BITS_VALUE:
        obs_thread.add_time(nbits * BITS_VALUE)

async def callback_channelpoints(data: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    global obs_thread

    reward = data.event.reward.title
    if reward.lower() != CHANELLPOINTS_REWARD_NAME.lower():
        return
    
    obs_thread.add_time(CHANNELPOINTS_REWARD_VALUE)

def add_sub_time(tier: str) -> None:
    global obs_thread

    if tier == '1000':
        obs_thread.add_time(TIER_1_VALUE)
    elif tier == '2000':
        obs_thread.add_time(TIER_2_VALUE)
    elif tier == '3000':
        obs_thread.add_time(TIER_3_VALUE)
    else:
        raise Exception('Twitch added some new kind of sub?')


# This includes those new subs from Gift Subs
async def callback_new_subscriber(data: ChannelSubscribeEvent) -> None:
    tier = data.event.tier
    add_sub_time(tier)

async def callback_resubscriber(data: ChannelSubscriptionMessageEvent) -> None:
    # TODO: Maybe support multimonth subs?
    tier = data.event.tier
    add_sub_time(tier)


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
        await eventsub.listen_channel_cheer(user.id, callback_bits)
    if AuthScope.CHANNEL_READ_SUBSCRIPTIONS in target_scope:
        # First time subscribers and gift subs
        await eventsub.listen_channel_subscribe(user.id, callback_new_subscriber)
        # Resubs
        await eventsub.listen_channel_subscription_message(user.id, callback_resubscriber)
    if AuthScope.CHANNEL_READ_REDEMPTIONS in target_scope:
        await eventsub.listen_channel_points(user.id, callback_channelpoints)

    running = True
    while running:
        try:
            user_input = input('Enter time or seconds to adjust time (p=pause, r=resume, q=quit, s=set exact):')
            if user_input == 'p':
                OBSThread.pause = True
            elif user_input == 'r':
                if not obs_thread.is_alive():
                    obs_thread = OBSThread()
                    obs_thread.start()
                OBSThread.pause = False
            elif user_input == 'q':
                obs_thread.ready_to_die = True
                obs_thread.join()
                running = False
            elif user_input == 's':
                user_input = input('Input new value (exact seconds or HH:MM:ss, anything else cancels):')
                try:
                    new_time = fuzzy_strtime_to_int(user_input)
                    obs_thread.set_time(new_time)
                except ValueError:
                    print('Input not recognized.')
            else:
                try:
                    time_to_add = fuzzy_strtime_to_int(user_input)
                    obs_thread.add_time(time_to_add)
                except ValueError:
                    print('Input not recognized.')
        except EOFError:
            print('Dying...')
            break
            
    await eventsub.stop()
    await twitch.close()