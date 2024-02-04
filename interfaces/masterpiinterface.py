# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import sys, os, cv2, time, queue, logging, threading, math, logging
sys.path.append('/home/pi/MasterPi')
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import numpy as np
import HiwonderSDK.Sonar as sonar
import HiwonderSDK.mecanum as mecanum
import HiwonderSDK.Board as Board
import HiwonderSDK.ActionGroupControl as actiongroup

from loggerinterface import setup_logger

class MasterPiInterface():

    #Initialise timelimit and logging
    def __init__(self):
        self.sonar = sonar.Sonar()
        self.sonar.setRGBMode(0)
        self.chassis = mecanum.MecanumChassis()
        self.status = "Ready"
        self.arm_rotation = 1500 #centre position
        self.camera_pos = "default"
        self.logger = logging.getLogger('Robot')
        setup_logger(self.logger, '../logs/robot.log')
        return
    
    #turn buzzer on for timelimit
    def set_buzzer_time(self, timelimit=1):
        endtime = time.time() + timelimit
        Board.setBuzzer(1)
        while (time.time() < endtime):
            continue
        Board.setBuzzer(0)
        return

    #get sonar distance
    def get_sonar_distance(self):
        distance = self.sonar.getDistance()
        time.sleep(0.1)
        return distance

    #set sonar eye color
    def set_sonarLED_colortuple(self, rgbtuple=(255,0,0)):
        self.sonar.setPixelColor(0, Board.PixelColor(*rgbtuple))
        self.sonar.setPixelColor(1, Board.PixelColor(*rgbtuple))
        return
    
    #set sonar eye color
    def set_sonarLED_color(self, colour="black"):
        red = (255,0,0)
        green = (0,255,0)
        blue = (0,0,255)
        yellow = (255,255,0)
        purple = (128,0,128)
        black = (0,0,0)
        white = (255,255,255)
        self.sonar.setPixelColor(0, Board.PixelColor(*eval(colour)))
        self.sonar.setPixelColor(1, Board.PixelColor(*eval(colour)))
        return    
    
    #set the leds on the board
    def set_boardLED_colortuple(self, rgbtuple=(0,0,0)):
        Board.RGB.setPixelColor(0, Board.PixelColor(*rgbtuple))
        Board.RGB.setPixelColor(1, Board.PixelColor(*rgbtuple))
        Board.RGB.show()
        return
    
    #set the leds on the board
    def set_boardLED_color(self, colour="black"):        
        red = (255,0,0)
        green = (0,255,0)
        blue = (0,0,255)
        yellow = (255,255,0)
        purple = (128,0,128)
        black = (0,0,0)
        white = (255,255,255)
        Board.RGB.setPixelColor(0, Board.PixelColor(*eval(colour)))
        Board.RGB.setPixelColor(1, Board.PixelColor(*eval(colour)))
        Board.RGB.show()
        return
    
    #rotate angular speed (radians) negative will rotate anticlockwise
    def rotate_speed_time(self, rotationspeed=0.1, timelimit=3):
        self.status = "Rotating"
        self.chassis.set_velocity(24, 90, rotationspeed) 
        endtime = time.time() + timelimit
        while ((time.time() < endtime) and (self.status == "Rotating")):
            continue
        self.stop()
        return
    
    # Rotate forever - this is dangerous - you must called stop() afterwards or it will spin forever
    def rotate_speed(self, rotationspeed=0.1):
        self.status = "Rotating"
        self.chassis.set_velocity(24, 90, rotationspeed) 
        return
    
    # Move in the direction the chasis travels in. 90 is forward, 0 is right, 180 left.
    def move_direction_time(self, power=35, direction=90, rotationspeed=0, timelimit=5):
        self.status = "Moving"
        self.chassis.set_velocity(power, direction, rotationspeed) 
        endtime = time.time() + timelimit
        while ((time.time() < endtime) and (self.status == "Moving")):
            continue
        self.stop()
        return
    
    # Move in the direction, this is dangerous, you must call stop() afterwards or it will move forward forever
    def move_direction(self, power=35, direction=90, rotationspeed=0):
        self.status = "Moving"
        self.chassis.set_velocity(power, direction, rotationspeed) 
        return
    
    def get_status(self):
        return self.status

    # Stop all movement
    def stop(self):
        self.status = "Stopped"
        self.chassis.set_velocity(0,0,0)
        return
    
    #run an action (filename) excluding file extention e.g. 
    def run_arm_action(self, actionname="default"):
        actiongroup.runAction(actionname)
        return
    
    #reset the arm
    def reset_arm(self):
        actiongroup.runAction("default")
        self.camera_pos = "default"
        return
    
    #reset the arm
    def look_down(self):
        actiongroup.runAction("lookdown")
        self.camera_pos = "lookdown"
        return
    
    #robot lookup
    def look_up(self):
        actiongroup.runAction("lookup")
        self.camera_pos = "lookup"
        return        
    
    # Stop current arm action
    def stop_current_arm_action(self):
        actiongroup.stop_action_group()
        return
    
    # Pick up a horizontally aligned object but adjust for the vertical position of the object
    def rotate_arm_to_left_extreme(self):
        Board.setPWMServoPulse(6, 2500, 1500)
        time.sleep(1.5)
        self.arm_rotation = 2500
        return
    
    # Pick up a horizontally aligned object but adjust for the vertical position of the object
    def grab_with_current_arm_rotation(self, deltaY=40): #set up to use a range between 0 and 300
        Board.setPWMServoPulse(1, 1864, 1000)
        time.sleep(1)
        #Board.setPWMServoPulse(3, 800+deltaY*2, 2000)   #Board.setPWMServoPulse(3, 1000, 2000)
        Board.setPWMServoPulse(3, 900+int(deltaY/1.5), 2000) #900+int(deltaY/2)
        time.sleep(2)
        Board.setPWMServoPulse(4, 2500-int(deltaY*1.7), 2000)  #Board.setPWMServoPulse(4, 1800, 2000) #2500-int(deltaY*2)
        time.sleep(2)
        Board.setPWMServoPulse(5, 2050+int(deltaY*1.25), 2000)  #Board.setPWMServoPulse(5, 2400, 2000)  #2000+deltaY
        time.sleep(2)
        Board.setPWMServoPulse(1, 1600, 2000) 
        time.sleep(2)
        return
    
    #rotate the arm between 500 and 2500
    def rotate_arm(self, rotation=100):
        
        if abs(rotation) <= 5:  #make the degrees either slow i.e 1 degree at a time
            rotation = int(math.copysign(1, rotation)) 
        elif abs(rotation) >= 100: #or cap the speed at 100 or -100
            rotation = int(math.copysign(100, rotation))
            
        self.arm_rotation = self.arm_rotation + rotation
                
        if self.arm_rotation < 500:
            self.arm_rotation = 500
        elif self.arm_rotation > 2500:
            self.arm_rotation = 2500
        else:
            dtime = abs(rotation)*10        
            Board.setPWMServoPulse(6, self.arm_rotation, dtime)
            time.sleep(dtime/1000)
        return

#main execution point for testing purposes
if __name__ == '__main__':
    ROBOT = MasterPiInterface()
    ROBOT.stop()
    ROBOT.look_up()
    ROBOT.grab_with_current_arm_rotation()

