# -*- coding: utf-8 -*-
# container for more advanced functionality
# use Ctrl + K, Ctrl + 0 to minimise all coding blocks in VSCODE
import time, sys, os, math, logging
import numpy as np
import cv2

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from masterpiinterface import MasterPiInterface
from soundinterface import SoundInterface
from camerainterface import CameraInterface

class RobotInterface(MasterPiInterface):
     
    def __init__(self):
        self.command = "Ready" # keep track of user commands
        self.show_camera = False # only turn this on to see the camera window, will slow down performance when using VNC
        self.SOUND = SoundInterface()
        
        self.CAMERA = CameraInterface()
        self.CAMERA.start()
        time.sleep(2) # Camera warmup time since it runs in a background thread now
        
        super().__init__()
        self.starttime = time.time() # when did robot get created
        return
    
    # stop the robot in its current process
    def stop_command(self):
        self.command = "Ready"
        self.stop()
        return

    # Moves towards an object in camera view - can either turn or slide
    def move_toward_colour_detected(self, colour="red", timelimit=5, mode='turning'):
        self.command = "move_toward_colour_detected"
        data = {
            'command': self.command,
            'starttime': time.time()
        }
        
        self.set_boardLED_color(colour)
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        endtime = time.time() + timelimit
        
        distance = 145
        if self.camera_pos == "lookdown":
            distance = 250
        elif self.camera_pos == "lookup":
            distance = 90 # FIXED: Removed the stray 'ac' typo here
        elif self.camera_pos == "default":
            distance = 145    
            
        while (time.time() < endtime) and (self.command == "move_toward_colour_detected"):
            if not self.show_camera_window():
                break
            
            data.update(self.CAMERA.get_detection_data())
            
            # Streamlined dictionary checking using .get()
            colour_data = data.get('detect_colour', {}).get(colour, {})
            if colour_data.get('found'):
                center, size, angle = colour_data['rect']
                x, y = center
                deltaY = 480 - y
                deltaX = 320 - x
                theta_degrees = int(math.degrees(math.atan2(deltaX, deltaY)) + 90)
                
                if deltaY > distance:
                    if mode == 'drifting':
                        self.move_direction(power=33, direction=theta_degrees, rotationspeed=0)
                    elif mode == 'turning':
                        turn = round(math.radians(theta_degrees - 90) / 8, 2)
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

    # Move in direction until detection
    # Fixed mutable default arguments (lists in function definition)
    def move_direction_until_detection(self, movetype='forward', distanceto=250, detection_types=None,
                                       detection_colours=None, timelimit=5, confirmlevel=1, target_class='person'):
        if detection_types is None:
            detection_types = ['colour']
        if detection_colours is None:
            detection_colours = ['red']
            
        self.command = "move_direction_until_detection"
        data = {'command': self.command}
        detections = []
        
        if 'all' in detection_types:
            self.CAMERA.detect_all()
        else:            
            if 'line' in detection_types:
                self.CAMERA.add_detection_task("detect_line")
            if 'colour' in detection_types:
                self.CAMERA.add_detection_task('detect_colour')
                self.CAMERA.set_detection_colours(detection_colours)
            if 'model' in detection_types:
                self.CAMERA.load_detection_model()
                self.CAMERA.add_detection_task("detect_model")
          
        data['starttime'] = time.time()
        endtime = time.time() + timelimit
        
        if movetype:
            if movetype == "forward":
                self.move_direction(power=33, direction=90, rotationspeed=0) 
            elif movetype == "turnright":
                self.rotate_speed(rotationspeed=0.08)
            elif movetype == "turnleft":
                self.rotate_speed(rotationspeed=-0.08)
            elif movetype == "circleright":
                self.move_direction(power=35, direction=90, rotationspeed=0.08)
            elif movetype == "circleleft":
                self.move_direction(power=35, direction=90, rotationspeed=-0.08)
            elif movetype == "slideright":
                self.move_direction(power=40, direction=0, rotationspeed=0)
            elif movetype == "slideleft":
                self.move_direction(power=40, direction=-180, rotationspeed=0)    
        
        while (time.time() < endtime) and (self.command == "move_direction_until_detection"):
            num_detections_processed = 0
            if not self.show_camera_window():
                break
            
            data.update(self.CAMERA.get_detection_data())
                    
            if 'sonar' in detection_types or 'all' in detection_types:
                sonar_distance = self.get_sonar_distance()
                # print(sonar_distance)
                data['detect_sonar'] = { 'distance': sonar_distance }
                self.CAMERA.output_message += f" Sonar: {sonar_distance}"
                
                if sonar_distance < distanceto:
                    print("Sonar detected!")
                    if 'sonar' not in detections:
                        detections.append('sonar')
                        if len(detections) == confirmlevel:
                            break
                
                num_detections_processed += 1
                if num_detections_processed == len(detection_types):
                    continue
            
            if 'line' in detection_types or 'all' in detection_types:
                line_data = data.get('detect_line', {})
                if line_data.get('found'):
                    line = line_data['line']
                    cx = (line[0][0] + line[1][0]) / 2
                    cy = (line[0][1] + line[1][1]) / 2
                    
                    if (480 - cy < distanceto):
                        angle_rad = np.arctan2(line[1][1] - line[0][1], line[1][0] - line[0][0])
                        angle = np.degrees(angle_rad)
                        if -45 < angle < 45: # somewhat horizontal lines
                            print("Line detected!")
                            if 'line' not in detections:
                                detections.append('line')
                                if len(detections) == confirmlevel:
                                    break
                                
                num_detections_processed += 1
                if num_detections_processed == len(detection_types):
                    continue
                
            if 'colour' in detection_types or 'all' in detection_types:
                for col in data.get('detect_colour', {}).keys():
                    col_data = data['detect_colour'][col]
                    if col_data.get('found'):
                        print(f"{col} detected!")
                        if col not in detections:
                            detections.append(col)
                            if len(detections) == confirmlevel:
                                break
                
                if len(detections) == confirmlevel:
                    break
                
                num_detections_processed += 1
                if num_detections_processed == len(detection_types):
                    continue
                
            if 'model' in detection_types or 'all' in detection_types: 
                model_data = data.get('detect_model', {})
                if model_data.get('found'):
                    for target in model_data['targets']:
                        if target['class'] == target_class:
                            if 'model' not in detections:
                                print(f"{target_class} detected!")
                                detections.append('model')
                                if len(detections) == confirmlevel:
                                    break
                                    
                    if len(detections) == confirmlevel:
                        break

        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data

    # Rotate arm clockwise from left to right to find a colour
    def rotate_arm_until_colour_detected(self, colour="red", timelimit=10):
        self.command = "rotate_arm_until_colour_detected"
        data = {
            'command': self.command,
            'starttime': time.time()
        }
        
        self.rotate_arm_to_left_extreme()
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        
        endtime = time.time() + timelimit
        while (time.time() < endtime) and (self.command == "rotate_arm_until_colour_detected"):
            if not self.show_camera_window():
                break
            
            data.update(self.CAMERA.get_detection_data())
            
            colour_data = data.get('detect_colour', {}).get(colour, {})
            if colour_data.get('found'):
                center, size, angle = colour_data['rect']
                x, y = center
            elif 'detect_colour' in data: # Only rotate if we've processed a frame
                self.rotate_arm(-100)
                    
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        data['arm_rotation'] = self.arm_rotation
        return data

    # TO DO - Rotate robot until robot is aligned with arm_rotation
    def rotate_robot_to_arm_rotation(self, timelimit=5):
        self.command = "rotate_robot_to_arm_rotation"
        data = {
            'command': self.command,
            'starttime': time.time()
        }
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data
    
    # Rotate arm until current colour in view is centered
    def rotate_arm_until_colour_detected_is_centered(self, colour="red", timelimit=10):
        self.look_down() # must be in look down mode
        self.command = "rotate_arm_until_colour_detected_is_centered"
        data = {
            'command': self.command,
            'starttime': time.time()
        }
        
        self.CAMERA.add_detection_task("detect_colour")
        self.CAMERA.add_detection_colour(colour)
        self.set_boardLED_color(colour)
        
        centered = False
        x, y = 0, 0
        endtime = time.time() + timelimit
        
        while (time.time() < endtime) and (self.command == "rotate_arm_until_colour_detected_is_centered"):
            if not self.show_camera_window():
                break
            
            data.update(self.CAMERA.get_detection_data())
            
            colour_data = data.get('detect_colour', {}).get(colour, {})
            if colour_data.get('found') and not centered:
                center, size, angle = colour_data['rect']
                x, y = center
                deltaX = 320 - x
                rotation = int(deltaX / 320 * 500)
                
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

    # Pick up a centered colour object in the look down position
    def pick_up_centered_object_with_look_down(self, y):
        self.command = "pick_up_centered_object_with_look_down"
        data = {
            'command': self.command,
            'starttime': time.time()
        }
        
        if y >= 100:
            deltaY = int((480 - y) / 240 * 300)
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
        
        data = {
            'command': self.command,
            'success': False,
            'starttime': time.time()
        }
        
        endtime = time.time() + timelimit
        while (time.time() < endtime) and (self.command == "was_object_pickup_successful"):
            if not self.show_camera_window():
                break
            
            data.update(self.CAMERA.get_detection_data())
            
            colour_data = data.get('detect_colour', {}).get(colour, {})
            if colour_data.get('found'):
                center, size, angle = colour_data['rect']
                width, height = size
                x, y = center
                deltaY = 480 - y
                
                if (deltaY < 100) and (250 < width < 500) and (abs(angle) < 5):
                    data['success'] = True
                    break
                
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        return data
 
    # Show a camera window until q is pressed
    def show_camera_window(self):
        if not self.show_camera:
            return True
        
        frame = self.CAMERA.get_frame()
        cv2.imshow('Detection Mode', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return False
        return True
    
    # Stationary auto detection
    def auto_detection(self, timelimit=100000000): 
        self.command = "auto_detection"
        data = {
            'command': self.command,
            'starttime': time.time()
        }
        
        endtime = time.time() + timelimit
        self.CAMERA.detect_all()
        
        while (time.time() < endtime) and (data['command'] == "auto_detection"): 
            if not self.show_camera_window():
                break
            data.update(self.CAMERA.get_detection_data())
            
        self.stop_command()
        self.CAMERA.end_detection()
        data['endtime'] = time.time()
        self.CAMERA.detection_data_expire_time = 1
        return data

    def cycle_through_all_detection_tasks(self, duration_per_task=5):
        """
        Cycles through a baseline (no detection) and each detection task (line, colour, model) 
        individually to allow the user to observe and compare the impact on the camera's framerate.
        
        Args:
            duration_per_task (int, optional): How long to run each task in seconds. Defaults to 5.
        """
        self.command = "cycle_through_all_detection_tasks"
        
        tasks_to_test = ['baseline', 'detect_line', 'detect_colour', 'detect_model']
        
        # Pre-load dependencies
        self.CAMERA.set_detection_colours(['red', 'green', 'blue'])
        self.CAMERA.load_detection_model()
        self.CAMERA.turn_on_output_text() 
        
        print("\n========================================")
        print(" STARTING DETECTION PERFORMANCE PROFILER")
        print("========================================\n")
        
        for task in tasks_to_test:
            # 1. Clear the tasks so the camera stops looking
            self.CAMERA.clear_detection_tasks()
            # 2. CLEAR THE DATA so the old text disappears instantly!
            self.CAMERA.clear_detection_data() 
            
            if task == 'baseline':
                print(f">>> Testing 'Baseline (No Detection)' for {duration_per_task} seconds...")
                self.SOUND.say("baseline test")
                self.CAMERA.set_output_message("BASELINE - RAW FEED")
            else:
                print(f">>> Testing '{task}' for {duration_per_task} seconds...")
                self.SOUND.say(task.replace('_', ' '))
                self.CAMERA.add_detection_task(task)
                self.CAMERA.set_output_message(task.upper())
            
            endtime = time.time() + duration_per_task
            
            while (time.time() < endtime) and (self.command == "cycle_through_all_detection_tasks"):
                if not self.show_camera_window():
                    self.command = "Stop" 
                    break
            
            if self.command != "cycle_through_all_detection_tasks":
                print("\n[!] Test aborted by user.")
                break 
                
        print("\n========================================")
        print(" CYCLE COMPLETE ")
        print("========================================\n")
        
        # Clean up
        self.CAMERA.set_output_message("")
        self.stop_command()
        self.CAMERA.end_detection()
        return

    
    # Shutdown the robot
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
    print("\033c")
    input("Press Enter to Start: ")
    
    ROBOT.CAMERA.create_detection_window()
    ROBOT.show_camera = True #THIS WILL SLOW DOWN THE FRAME RATE IF ON VNC
    print("Voltage: ", ROBOT.get_voltage())
    
    ROBOT.look_up()
    ROBOT.SOUND.say("Robot ready")

    # Test all detection tasks
    ROBOT.cycle_through_all_detection_tasks(duration_per_task=20)
    
    # Uncomment below to test movements
    #data = ROBOT.move_direction_until_detection(movetype='turnleft', distanceto=250, detection_types=['colour','sonar'], confirmlevel=2, detection_colours=['red'], timelimit=10)
    #print(data)
    ROBOT.stop()
    
    sys.exit(0)