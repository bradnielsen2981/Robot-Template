# -*- coding: utf-8 -*-
#container for more advanced functionality
# use Ctrl + K, Ctrl + 0 to minimise all coding blocks in VSCODE
import time, sys, os, math, logging
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from masterpiinterface import MasterPiInterface
from soundinterface import SoundInterface
from camerainterface import CameraInterface

import numpy as np
import cv2

class RobotInterface(MasterPiInterface):
    
    def __init__(self):
        self.command = "Ready" #keep track of user commands
        self.show_camera = False #only turn this on to see the camera window
        self.SOUND = SoundInterface()
        self.CAMERA = CameraInterface()
        self.CAMERA.start(drawing=True) #if drawing is off, the frame will not contain drawing - speed increased
        super().__init__()
        self.starttime = time.time() #when did robot get created - takes 3 seconds to start the camera
        return
    
    # stop the robot in its current process - most processes using timelimit and var self.command to exit loops
    def stop_command(self):
        self.command = "Ready"
        self.stop()
        return

    # Move in direction until distance from detection. Movetypes can be none, forward, turn, circle, slideright, slideleft 
    # Multiple detection types can be included: sonar, line, colour, model, letter, all. (Model has not been implemented)
    # Confirmlevel is the number of unique detection types required before a stop.
    def move_direction_until_detection(self, movetype="forward", distanceto=250, detection_types=['sonar'],
                                       detection_colours=['red'], timelimit=5, confirmlevel=1):
        self.command = "move_direction_until_detection"
        data = {}
        data['command'] = self.command
        detections = []
        temp_detection_types = detection_types.copy()
        
        if 'all' in detection_types:
            self.CAMERA.detect_all()
        else:            
            if 'line' in detection_types: #line detection
                self.CAMERA.add_detection_task("detect_line")
                
            if 'colour' in detection_types:
                self.CAMERA.add_detection_task('detect_colour')
                self.CAMERA.set_detection_colours(detection_colours)
                
            if 'model' in detection_types: #TODO: add detect_model to camera
                self.CAMERA.add_detection_task("detect_model")
                
            if 'letter' in detection_types: #TODO: add detect_model to camera
                self.CAMERA.add_detection_task("detect_letter")
          
        time.sleep(1) #camera needs time to get ready..
        data['starttime'] = time.time()
        endtime = time.time() + timelimit
        
        if movetype != None:
            if movetype == "forward":
                self.move_direction(power=33, direction=90, rotationspeed=0) #currently this moving forward but could easily be circular, or drifting
            elif movetype == "turnright":
                self.rotate_speed(rotationspeed=0.08)
            elif movetype == "turnleft":
                self.rotate_speed(rotationspeed=-0.08)
            elif movetype == "circleright":
                self.move_direction(power=38, direction=90, rotationspeed=0.08)
            elif movetype == "circleleft":
                self.move_direction(power=38, direction=90, rotationspeed=-0.08)
            elif movetype == "slideright":
                self.move_direction(power=35, direction=0, rotationspeed=0)
            elif movetype == "slideleft":
                self.move_direction(power=35, direction=-180, rotationspeed=0)    
        
        while ((time.time() < endtime) and (self.command == "move_direction_until_detection")):
            
            num_detections_processed = 0
            
            if not self.show_camera_window():
                break
                    
            if 'sonar' in detection_types or 'all' in detection_types:
                sonar_distance = self.get_sonar_distance()
                if sonar_distance < distanceto:
                    data['detect_sonar'] = { 'distance':sonar_distance }
                    print("Sonar detected!")
                    if 'sonar' not in detections:
                        detections.append('sonar')
                        if len(detections) == confirmlevel:
                            break
                num_detections_processed += 1
                if num_detections_processed == len(detection_types): #skip the rest for efficiency
                    continue
            
            #read in the camera detection data and then update the current dictionary
            temp_data = self.CAMERA.get_detection_data()
            data.update(temp_data)
            #time.sleep(0.05)
            
            if 'line' in detection_types or 'all' in detection_types:
                if 'found' in data['detect_line']:
                    line = data['detect_line']['line']
                    cx = (line[0][0] + line[1][0]) / 2
                    cy = (line[0][1] + line[1][1]) / 2
                    center_point = (cx, cy)
                    if (480-cy < distanceto):
                        angle_rad = np.arctan2(line[1][1] - line[0][1], line[1][0] - line[0][0])
                        angle = np.degrees(angle_rad)
                        if angle < 45 and angle > -45: #only somewhat horizontal lines are detected
                            print("Line detected!")
                            if 'line' not in detections:
                                detections.append('line')
                                if len(detections) == confirmlevel:
                                    break
                        else: #detection_break = True #Do i break if i see a vertical line??
                            pass
                num_detections_processed += 1
                if num_detections_processed == len(detection_types): #skip the rest for efficiency
                    continue
                
            if 'colour' in detection_types or 'all' in detection_types:
                
                for colour in data['detect_colour'].keys():
                    if 'found' in data['detect_colour'][colour]:
                        rect = data['detect_colour'][colour]['rect']
                        center, size, angle = rect
                        cx, cy = center
                        #Do i ignore objects too far away. if cy < 100: 
                        print(colour + " detected!")
                        if colour not in detections:
                            detections.append(colour)
                            if len(detections) == confirmlevel:
                                break
                
                if len(detections) == confirmlevel:
                    break
                
                num_detections_processed += 1
                if num_detections_processed == len(detection_types): #skip the rest for efficiency
                    continue
                
            if 'model' in detection_types or 'all' in detection_types: 
                pass # Detect_model has not been implemented in the CameraInterface
            
            if 'letter' in detection_types or 'all' in detection_types: 
                pass # Detect_model has not been implemented in the CameraInterface
               
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data

    # Rotate arm clockwise from left to right to find a colour - could be used in distance or close - can only scan 180 degrees
    def rotate_arm_until_colour_detected(self, colour="red", timelimit=10):
        
        self.command = "rotate_arm_until_colour_detected"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        self.rotate_arm_to_left_extreme()
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        
        endtime = time.time() + timelimit
        while ((time.time() < endtime) and (self.command == "rotate_arm_until_colour_detected")):
            if not self.show_camera_window():
                break
            
            temp_data = self.CAMERA.get_detection_data()
            data.update(temp_data)
            #time.sleep(0.05)
            if colour in data['detect_colour']:
                if 'found' in data['detect_colour'][colour]:
                    rect = data['detect_colour'][colour]['rect']
                    center, size, angle = rect
                    x, y = center
                else:
                    self.rotate_arm(-100)
                    
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        data['arm_rotation'] = self.arm_rotation
        return data

    # TO DO - Rotate robot until robot is aligned with arm_rotation - may need an IMU sensor
    def rotate_robot_to_arm_rotation(self, timelimit=5):
        
        self.command = "rotate_robot_to_arm_rotation"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data
    
    # TO DO - orbit the coloured target until target angle is horizontal
    def orbit_target(self, colour='red', timelimit=5):
        
        self.command = "orbit_target"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data

    # Rotate arm until current colour in view is centered
    def rotate_arm_until_colour_detected_is_centered(self, colour="red", timelimit=10):
        
        self.command = "rotate_arm_until_colour_detected_is_centered"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        self.set_boardLED_color(colour)
        centered = False
        x = 0; y = 0
        endtime = time.time() + timelimit
        while ((time.time() < endtime) and (self.command == "rotate_arm_until_colour_detected_is_centered")):
            if not self.show_camera_window():
                break
            
            temp_data = self.CAMERA.get_detection_data()
            data.update(temp_data)
            #time.sleep(0.05)
            
            #might move back a couple of centimeters if colour is not found
            if colour in data['detect_colour']:
                if 'found' in data['detect_colour'][colour] and not centered:
                    rect = data['detect_colour'][colour]['rect']
                    center, size, angle = rect
                    x, y = center
                    deltaX = 320-x
                    rotation = int(deltaX/320*500)
                    if abs(rotation) > 2:
                        self.rotate_arm(rotation)
                    else:
                        centered = True
                        break
                
        self.stop_command()        
        self.CAMERA.end_detection()
        data['x'] = x
        data['y'] = y
        data['endtime'] = time.time()
        
        return data

    # Pick up a centered colour object in the look down position. Keeps current arm rotation
    def pick_up_centered_object_with_look_down(self, y):
        
        self.command = "pick_up_centered_object_with_look_down"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        #if y >= 225:
        if y >= 100:
            deltaY = int((480-y)/240*300)
            print(deltaY)
            self.grab_with_current_arm_rotation(deltaY)
            self.reset_arm()
            data['pickup'] = True
        else:
            data['pickup'] = False
        self.stop_command()
        data['endtime'] = time.time()
        
        return data
    
    # Check if the pick up was successful
    def was_object_pickup_successful(self, colour='red', timelimit=10):
        
        self.command = "was_object_pickup_successful"
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        time.sleep(1)
        data = {}
        data['command'] = self.command
        data['success'] = False
        data['starttime'] = time.time()
        endtime = time.time() + timelimit
        while ((time.time() < endtime) and (self.command == "was_object_pickup_successful")):
            if not self.show_camera_window():
                break
            
            temp_data = self.CAMERA.get_detection_data()
            data.update(temp_data)
            #time.sleep(0.05)
            
            if colour in data['detect_colour']:
                if 'found' in data['detect_colour'][colour]:
                    rect = data['detect_colour'][colour]['rect']
                    center, size, angle = rect
                    width, height = size
                    x, y = center
                    deltaY = 480-y
                    #print("DeltaY", deltaY, "Width", width, "Angle", angle)
                    if ((deltaY < 100) and (width > 250) and (width < 500) and (abs(angle) < 5)):
                        data['success'] = True
                        break
                
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        
        return data
    
    # Moves towards an object in camera view
    def move_toward_colour_detected(self, colour="red", timelimit=5, mode='turning'):
        
        self.command = "move_toward_colour_detected"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        self.set_boardLED_color(colour)
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        self.set_boardLED_color(colour)
        endtime = time.time() + timelimit
        centered = False
        
        distance = 145
        if self.camera_pos == "lookdown":
            distance = 250
        elif self.camera_pos == "lookup":
            distance = 90
        elif self.camera_pos == "default":
            distance = 145    
            
        while ((time.time() < endtime) and (self.command == "move_toward_colour_detected")):
            if not self.show_camera_window():
                break
            
            temp_data = self.CAMERA.get_detection_data()
            data.update(temp_data)
            #time.sleep(0.05)
            
            if colour in data['detect_colour']:
                if 'found' in data['detect_colour'][colour]:
                    rect = data['detect_colour'][colour]['rect']
                    center, size, angle = rect
                    x, y = center
                    deltaY = 480-y
                    deltaX = 320-x
                    theta_degrees = int(math.degrees(math.atan2(deltaX,deltaY)) + 90)
                    
                    if deltaY > distance:
                        if mode == 'drifting':
                            self.move_direction(power=33, direction=theta_degrees, rotationspeed=0)
                        elif mode == 'turning':
                            turn = round(math.radians(theta_degrees-90)/8, 2)
                            if abs(turn) <= 0.01:
                                turn = 0
                            self.move_direction(power=33, direction=90, rotationspeed=-turn)
                    else:
                        self.move_direction_time(direction=270, rotationspeed=0, power=33, timelimit=0.2)
                        break
                
        self.stop_command()        
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data

    # Show a camera window until q is pressed - use for debugging purposes
    def show_camera_window(self):
        
        if not self.show_camera:
            return True
        frame = self.CAMERA.get_frame()
        time.sleep(0.05)
        cv2.imshow('Detection Mode', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return False
        return True
    
    # Stationary auto detection - once another command is called, autodetection will be turned off.
    # But basic moving forward and turning will not affect autodetection, timelimit is by default unlimited.
    def auto_detection(self, timelimit=100000000): 
        
        self.command = "auto_detection"
        data = {}
        data['command'] = self.command
        data['starttime'] = time.time()
        endtime = time.time() + timelimit
        
        #self.CAMERA.detection_data_expire_time = 0 #when auto_detection is turned off, the expire time will be reset
        self.CAMERA.detect_all(exclude_colours=['black','white'])
        
        while ((time.time() < endtime) and (data['command'] == "auto_detection")): #this can not be running when automated_mode is on
            if not self.show_camera_window():
                break
            temp_data = self.CAMERA.get_detection_data()
            data.update(temp_data)
            #time.sleep(0.05)
            
        self.stop_command()
        self.CAMERA.end_detection()
        #time.sleep(0.05)
        data['endtime'] = time.time()
        self.CAMERA.detection_data_expire_time = 1
        return data
    
    #shutdown the robot
    def shutdown(self):
        
        self.command = "Shutdown"
        self.stop_command()
        self.CAMERA.stop()
        self.set_sonarLED_color()
        self.set_boardLED_color()
        
        return

# TEST ROBOT CODE
if __name__ == '__main__':
    ROBOT = RobotInterface()
    ROBOT.stop()
    ROBOT.look_up()
    input("Press Enter to Start")
    ROBOT.SOUND.say("Loading")
    time.sleep(3) #A 3 second delay is required so the Camera has time to capture the stream

    ROBOT.show_camera = True
    cv2.namedWindow('Detection Mode')
    cv2.resizeWindow('Detection Mode', 640, 480)
    time.sleep(1)
    
    ROBOT.CAMERA.turn_on_output_text()
    ROBOT.auto_detection(timelimit=60)
            
    ROBOT.shutdown() 
    sys.exit(0)
    