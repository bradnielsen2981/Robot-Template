#This is where your main robot code resides. It extendeds from the BrickPi Interface File
#It includes all the code inside brickpiinterface. The CurrentCommand and CurrentRoutine are important because they can keep track of robot functions and commands. Remember Flask is using Threading (e.g. more than once process which can confuse the robot)
from interfaces.robotinterface import RobotInterface
import logging, sys, os

class Robot(RobotInterface): 
    
    def __init__(self, DATABASE):
        super().__init__()
        self.DATABASE = DATABASE
        self.CurrentRoutine = "Ready" #use this stop or start routines
        return
     
    # Write a function for automated search, pickup and putdown, and save instructions to the database
    def automatedSearch(self):
        self.CurrentRoutine = "Automated Search"
        self.SOUND.load_mp3("../static/music/missionimpossible.mp3")
        self.SOUND.play_music(1)
        self.SOUND.say("Searching for colours")
        print("Searching for colours")
        data = self.move_direction_until_detection(movetype='turnleft', distanceto=250, detection_types=['colour'],
                                                detection_colours=['red','green','blue'], timelimit=5, confirmlevel=1)
        print(data)
        colour_detected = None
        for colour in data['detect_colour'].keys():
            if 'found' in data['detect_colour'][colour]:
                colour_detected = colour
                break  #choose the first colour found
    
        if colour_detected:
            self.SOUND.say(colour_detected + " was detected.")
            self.SOUND.say("Moving towards colour.")
            print("Moving towards colour.")
            data = self.move_toward_colour_detected(colour=colour_detected)
            print(data)
        
            self.look_down()
            self.SOUND.say("Moving closer to colour.")
            print("Moving closer to colour.")
            data = self.move_toward_colour_detected(colour=colour_detected) #get closer
            print(data)
        
            self.SOUND.say("Rotating arm to initiate pickup.")
            print("Rotating arm.")
            data = self.rotate_arm_until_colour_detected_is_centered(colour=colour_detected)
            print(data)
            
            print("Pick up centered object")
            data = self.pick_up_centered_object_with_look_down(data['y'])
            print(data)
            
            print("Check if pick up was successful")
            data = self.was_object_pickup_successful(colour=colour_detected)
            print(data)
            
            if data['success'] == True:
                self.SOUND.say("Pick up successful")        
            elif data['success'] == False:
                self.SOUND.say("Pick up unsuccessful")
        
        self.SOUND.stop_music()
        return
    
# Only execute if this is the main file, good for testing code
if __name__ == '__main__':
    input("Press enter to begin testing:")