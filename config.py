#!/usr/bin/env python3
from twitchAPI.type import AuthScope
from queue import Queue
from typing import List

# Twitch Specific Settings
APP_TOKEN:str = '0alklgv5ftv7ohq3jns3ou8467ff69'        # The app token for subathon-timer-python, replace this with your own if you are making your own app.
TARGET_CHANNEL:str = 'maskarauder'                      # The channel name of your account, ie. maskarauder, SwiftIke, etc

# OBS Specific Settings
OBS_HOST:str = 'localhost'                              # From OBS, default to 'localhost'
OBS_PORT:int = 4455                                     # From OBS, default to 4455
OBS_WEBSOCKET_PASSWORD:str = ''                         # From OBS, can regenerate the password whenever you wish or disable it altogether.
OBS_SCENE_NAME:str = None                               # The scene to search for the OBS source within, None = the current scene
OBS_SCENEITEM_NAME:str = 'subathon_clock'               # The name of the OBS Text Source for the clock

# App Specific Settings
DEFAULT_START_TIME:int = 60 * 60                        # Default to 1 hour start time

# Bits Settings
TRIGGER_BITS_VALUE:int =   1                            # Minimum cheer to trigger adding time to the timer
BITS_VALUE:float       =   1                            # Seconds to add per bit (accepts decimal values)

# Subs Settings
TIER_1_VALUE:float     =   500                          # Seconds to add per tier 1 (accepts decimal values)
TIER_2_VALUE:float     =   1000                         # Seconds to add per tier 2 (accepts decimal values)
TIER_3_VALUE:float     =   2500                         # Seconds to add per tier 3 (accepts decimal values)

# Channel Point Settings
CHANNELPOINTS_ALLOWED:bool = False                      # Allow running for free via Channel Points
CHANELLPOINTS_REWARD_NAME:str = 'Add to Subathon'       # The case-insensitive name of the Channel Points reward to listen for
CHANNELPOINTS_REWARD_VALUE:float = 100                  # Seconds to add per channel points redemption (accepts decimal values)

# Log Settings
LOG_ENABLED:bool = True                                 # Log donations to various CSV files
LOG_DIRECTORY:str = './logs/'                           # The folder where to store the logs (absolute paths work)
GIFT_PACKS_LOGFILE:str = 'gifted_subs.csv'              # The file where information on who gifted subs is stored
SUBSCRIPTION_LOGFILE:str = 'subscriptions.csv'          # The file where information on all subscriptions is stored (as well as timer interactions)
BITS_LOGFILE:str = 'bits.csv'                           # The file where information on bits donations is stored (+ timer interactions)

# Globals, don't touch this unless you know what you're doing.
TARGET_SCOPE:List[AuthScope] = [AuthScope.BITS_READ, AuthScope.CHANNEL_READ_SUBSCRIPTIONS]
if CHANNELPOINTS_ALLOWED:
    TARGET_SCOPE.append(AuthScope.CHANNEL_READ_REDEMPTIONS)