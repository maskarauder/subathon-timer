# Twitch Subathon Timer in Python  

## Getting Started  
### Quickstart
Download `SubathonTimer-Windows.zip` from a successful [Release](/releases/download/v1.0.0/SubathonTimer-Windows.zip)  
Extract it  
Edit `config.py` using the OBS/Twitch settings below  
Double-click `SubathonTimer.exe`  
Keep the folder writable: saved login tokens and relative log paths stay beside the app.  
When updating, you can keep your existing `config.py`, `user_token.json`, and logs.

## OBS:  
Tools -> WebSocket Server Settings -> Enable WebSocket Server  
Tools -> WebSocket Server Settings -> Enable authentication  
Tools -> WebSocket Server Settings -> Show Connect Info  
Copy the password to config.py into the field OBS_WEBSOCKET_PASSWORD  

Create a Text (GDI+) Source and add it to a scene.  
Put the name of the Source into config.py as the field OBS_SCENEITEM_NAME

## Twitch:  
The first time you run the app, your default browser will prompt you to authorize it. The tokens are stored in `user_token.json`, reused, and refreshed automatically. You will only be prompted again if the stored authorization can no longer be used or the requested scopes change. Do not share this file; it is already excluded from Git.

## Terminal Commands
- integer or HH:MM:SS value -> add (or remove if negative) time from the clock
- p -> pause the timer, it will still receive donations, just will not count down
- r -> resume the timer or restart from DEFAULT_START_TIME if timer hits 0 or the text is no longer able to be read
- q -> quit the timer, kill the Twitch and OBS connections and let the app die gracefully
- s -> set the timer to an exact time, there will be a follow on prompt to input seconds or HH:MM:SS times  

## Working with the project
### uv
Install [uv](https://docs.astral.sh/uv/getting-started/installation/)  
On windows you can use the command `winget install --id astral-sh.uv -e` in the terminal that's open.  
`uv` manages Python, dependencies, and the virtual environment automatically.

## Running the app
`uv run main.py`

## Running the tests
`uv run pytest -q`

## Building a download
`uv run --locked --group build python build.py` creates a ZIP in `dist/` for the current OS. Build Windows executables on Windows; use a clean `config.py` before sharing the ZIP.

## How it works  
### Twitch Thread
The app works by connecting to the Twitch EventSub WebSocket in one thread to receive incoming Bits, Subscription, and/or Channel Points events. When a Bits donation above the TRIGGER_BIT_VALUE threshhold (defined in config.py) is received or a subscription is received, the value is calculated based on the related constant in the config.py and added to the timer.

This is not an atomic clock and it may add very minute fractions of seconds over time due to runtime, but it shouldn't be an exceptional amount of time added and shouldn't even be noticable. If it is, post an issue to GitHub and I'll try and refine it further.

### OBS Thread  
The OBS Thread is spun up as needed and only exists while there is a timer counting down.  

The OBS Thread will connect to the OBS WebSocket and attempt to find the correct text source. It will then change the text to the body of the timer.

The thread continues this loop until the timer hits 0, and then dies gracefully, closing the connection to the OBS WebSocket in the process.

## TODO
- Revisit the time parsing section.
- Add support for multimonth subs?

## Considerations  
*How do I pause the timer?*  
Type p in the terminal where the timer is running and hit enter, or make the OBS SceneItem hidden. It will resume when you either unhide the sceneitem or type r and hit enter to resume.  

*How can I quickly add or remove time from the timer?*  
Just type a time as either seconds or HH:MM:SS format in the terminal and hit enter. To remove time, type something like -1:30 or -600.

*Can you make a nice web page as a landing zone to let me see click buttons instead of typing in the terminal?*  
No.  

*Some weird error came up or something just isn't working for me.*  
Email a screenshot and anything helpful you can add to support@maskarauder.com, I'll get to it when I can.
