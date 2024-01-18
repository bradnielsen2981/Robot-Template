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
        
        
        return
    
# Only execute if this is the main file, good for testing code
if __name__ == '__main__':
    input("Press enter to begin testing:")