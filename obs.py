#!/usr/bin/env python3

# OBS API
import obsws_python as obs

# App Specific
from config import *
from time import sleep
from helpers import fuzzy_strtime_to_int, int_to_strtime
from threading import Thread

# Can't figure out how to completely remove the need for globals for the event client
source = None

def on_scene_item_enable_state_changed(data):
    global source

    if data['sceneItemId'] == source['sceneItemId']:
        if data['sceneItemEnabled']:
            OBSThread.pause = False
        else:
            OBSThread.pause = True

class OBSThread(Thread):
    pause = False
    ready_to_die = False

    def run(self) -> None:
        while not self.connect_to_obs():
            print('Failed to connect to OBS. Retrying in 1 sec...')
            sleep(1)
            return
        
        self.ecl.callback.register(on_scene_item_enable_state_changed)

        current = self.get_time()
        if current == 0:
            self.remaining_time = DEFAULT_START_TIME
        else:
            self.remaining_time = current

        self.set_time(self.remaining_time)

        while self.remaining_time > 0:
            if self.ready_to_die:
                return
            elif not self.pause:
                self.update_time(-1)
            sleep(1)
        
        print('\nTimer finished! r to restart.')


    def __init__(self):
        self.cl = None
        self.ecl = None
        self.inputobj = None
        self.remaining_time = 1
        self.waiting_to_be_added = 0
        Thread.__init__(self)

    def __del__(self):
        try:
            if self.ecl:
                self.ecl.disconnect()
        except Exception:
            pass

        try:
            if self.cl:
                self.cl.disconnect()
        except Exception:
            pass


    def get_time(self) -> int:
        if not self.cl:
            raise Exception('OBS WebSocket not connected!')
        
        settings = self.cl.get_input_settings(self.inputobj['inputName'])
        self.remaining_time = fuzzy_strtime_to_int(settings.input_settings['text'])
        return self.remaining_time


    def set_time(self, seconds: int) -> None:
        if not self.cl:
            raise Exception('OBS WebSocket not connected!')
        
        settings = self.cl.get_input_settings(self.inputobj['inputName'])
        settings.input_settings['text'] = int_to_strtime(seconds)
        self.cl.set_input_settings(self.inputobj['inputName'], settings.input_settings, True)


    def update_time(self, change: int) -> None:
        try:
            self.get_time()
            self.set_time(self.remaining_time + change)
        except ValueError:
            OBSThread.pause = True

    def add_time(self, seconds: int) -> None:
        self.update_time(seconds)


    def connect_to_obs(self) -> bool:
        global source
        cl = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_WEBSOCKET_PASSWORD, timeout=3)

        scene = OBS_SCENE_NAME
        inputobj = None
        source = None

        if not scene:
            scene = cl.get_current_program_scene().scene_name
        if scene is None:
            cl.disconnect()
            return False

        sceneitems = cl.get_scene_item_list(scene)
        if sceneitems is None:
            cl.disconnect()
            return False

        inputs = cl.get_input_list()
        if inputs is None:
            cl.disconnect()
            return False

        for i in inputs.inputs:
            if i['inputName'] == OBS_SCENEITEM_NAME:
                inputobj = i
                break

        if inputobj is None:
            cl.disconnect()
            return False

        for sceneitem in sceneitems.scene_items:
            if sceneitem['sourceName'] == OBS_SCENEITEM_NAME:
                source = sceneitem
                break
        
        if source is None:
            cl.disconnect()
            return False

        ecl = obs.EventClient(host=OBS_HOST, port=OBS_PORT, password=OBS_WEBSOCKET_PASSWORD, timeout=3)
        if ecl is None:
            cl.disconnect()
            return False
        
        self.cl = cl
        self.ecl = ecl
        self.inputobj = inputobj
        return True