#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import pygame
import speake3
from loggerinterface import setup_logger
import logging

class SoundInterface():
    
    def __init__(self):
        self.engine = speake3.Speake()
        self.engine.set('voice', 'en-scotish')
        self.engine.set('speed', '150')
        self.engine.set('pitch', '60')
        pygame.mixer.init() #load music player
        self.logger = logging.getLogger('SoundInterface')
        setup_logger(self.logger, '../logs/sound.log')
        return
    
    def get_all_voices(self):
        voices = self.engine.get("voices") #shows all the voices that could be selected
        for voice in voices:
            print(voice)
        voices_2 = self.engine.get("voices", "en") #shows all english voices
        for voice in voices_2:
            print(voice)
        return
    
    def say(self, message):
        #self.logger.info("Sound Interface: say " + message)
        self.engine.say(message) #gets robot to speak word or phrase
        self.engine.talkback()
        return

    def load_mp3(self, song): #saves the song as something recogniseable
        pygame.mixer.music.load(song)
        return
    
    def play_music(self, times=-1):
        pygame.mixer.music.play(times)
        return
    
    def pause_music(self):
        pygame.mixer.music.pause()
        return
    
    def unpause_music(self):
        pygame.mixer.music.unpause()
        return

    def stop_music(self):
        pygame.mixer.music.stop()
        return

    def set_volume(self, v=0.8):
        pygame.mixer.music.set_volume(v)
        return

#---------------------------------------------
#only execute if this is the main file, good for testing code.   
if __name__ == "__main__":
    SOUND = SoundInterface()
    SOUND.load_mp3("static/music/missionimpossible.mp3")
    SOUND.say("Hello, my name is WALLEE")
    SOUND.play_music(1)
    response = input("Press Enter to stop")
    SOUND.stop_music()