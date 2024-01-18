# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# As soon as the Hiwonder robot starts, an mpg server is running on port 8080
# any time we want we can get the frame from the stream, and detect objects and lines
import sys, os, time, queue, logging, threading
sys.path.append('/home/pi/MasterPi')
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import math
import cv2
import numpy as np
import yaml_handle #lab colours
from loggerinterface import setup_logger
import logging

#helper function for detecting contours
def get_max_contour(contours, min_area=400):
    contour_area_temp = 0
    contour_area_max = 0
    area_max_contour = None
    for c in contours:
        contour_area_temp = math.fabs(cv2.contourArea(c))
        if contour_area_temp > contour_area_max:
            contour_area_max = contour_area_temp
            if contour_area_temp > min_area:
                area_max_contour = c
    return area_max_contour, contour_area_max

# The Camera Object
class CameraInterface():

    #Initialise timelimit and logging
    def __init__(self, timelimit=20, logger=logging.getLogger()):
        self.timelimit=20
        self.logger = logger
        self.thread = None
        self.status = None
        self.frame = None
        self.detection_data = {'detect_line':{},'detect_colour':{},'detect_model':{}} #detection dictionary will contain the name of the task and data that was detected
        self.detection_tasks = []
        self.detection_colour = None
        self.min_detection_area = 300
        self.paused = False
        self.drawing = True
        self.dict_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.logger = logging.getLogger('CameraInterface')
        setup_logger(self.logger, '../logs/camera.log')
        
        #load the colours for detection - uses the colours set in the yaml
        self.lab_colours = yaml_handle.get_yaml_data(yaml_handle.lab_file_path)
        #{'black': {'max': [115, 135, 135], 'min': [0, 0, 0]}, 'blue': {'max': [255, 255, 115], 'min': [0, 0, 0]}, 'green': {'max': [200, 120, 150], 'min': [0, 0, 0]}, 'red': {'max': [255, 255, 255], 'min': [0, 145, 130]}, 'white': {'max': [255, 255, 255], 'min': [193, 0, 0]}}
        
        try:
            self.capture = cv2.VideoCapture('http://127.0.0.1:8080?action=stream')
            self.status = "Ready"
        except:
            self.status = "Fail"
            self.capture = None
            self.logger.error("Video capture could not be accessed.")
        return
    
    def start(self, drawing=True):
        if self.status == "Ready":
            self.drawing = drawing
            self.thread = threading.Thread(target=self.update, args=())
            self.thread.daemon = True
            self.thread.start()
            self.status = "Running"
        return
    
    # Function is run by thread...
    def update(self):
        self.logger.info("Starting Camera Thread")
        img = None
        time.sleep(2) #doesnt work without this, dont know why
        frame = None
        #to exit the thread, set status to Stopped
        while self.status == "Running":
            if self.paused:
                continue
            try:
                ret, img = self.capture.read()
                if not ret:
                    continue
                else:
                    frame = img.copy() #update the current frame
            except:
                continue
            
            if len(self.detection_tasks) > 0:
            
                if "detect_line" in self.detection_tasks:
                    frame, line, dtime = self.detect_line(frame, threshold=100)
                    if dtime != 0:
                        with self.dict_lock:
                            self.detection_data['detect_line']['found'] = True
                            self.detection_data['detect_line']['line'] = line
                            self.detection_data['detect_line']['time'] = dtime
        
                if "detect_colour" in self.detection_tasks:
                    colour = self.detection_colour
                    if colour == None:
                        continue
                    
                    if colour in self.lab_colours.keys():
                        minC = np.array(self.lab_colours[colour]['min']) #min colour range
                        maxC = np.array(self.lab_colours[colour]['max']) #max colour range
                        
                        frame, rect, area, dtime = self.detect_color(frame, minC, maxC)
                        if dtime != 0:
                            with self.dict_lock:
                                self.detection_data['detect_colour'][colour]['found'] = True
                                self.detection_data['detect_colour'][colour]['area'] = area
                                self.detection_data['detect_colour'][colour]['rect'] = rect #detection data will only exist if colour detected
                                self.detection_data['detect_colour'][colour]['time'] = dtime
                            
                if "detect_model" in self.detection_tasks: #i could use keras here...
                    pass
                
            with self.frame_lock:
                self.frame = frame
                
        return
    
    # Get current rendered frame
    def get_frame(self):
        with self.frame_lock:
            return self.frame
    
    # get a jpeg frame so to prepare for web stream
    def get_jpeg_frame(self, quality=50):
        with self.frame_lock:
            #return cv2.imencode('.jpg', self.frame, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()
            ret, frame = cv2.imencode('.jpg', self.frame)
            if ret:
                return frame.tobytes()
    
    # get the current frame
    def save_frame_as_image(self):
        with self.frame_lock:
            cv2.imwrite('frame.jpg', self.frame)
        return
            
        
    # Get current rendered frame
    def get_detection_data(self):
        with self.dict_lock:
            return self.detection_data
    
    # Set detection task to be either 'line', 'colour', 'object', 'model' - model not implemented yet
    def add_detection_task(self, task):
        self.detection_tasks.append(task)
        return
    
    def remove_detection_task(self, task):
        self.detection_tasks.remove(task)
        return
    
    # Stop the detection task
    def clear_detection_tasks(self):
        self.detection_tasks.clear()
        self.detection_colour = None
        return
    
    # Show drawing
    def set_drawing_on(self):
        self.drawing = True
        return
    
    # Hide drawing - will increase speed
    def set_drawing_off(self):
        self.drawing = False
        return
    
    # Set the detection colour - the colour name should have been set using the ARM application
    def set_detection_colour(self, colour):
        with self.dict_lock:
            self.detection_colour = colour
            self.detection_data['detect_colour'][colour] = {}
        return
    
    # Clear detection data
    def clear_detection_data(self):
        with self.dict_lock:
            self.detection_data = {'detect_line':{},'detect_colour':{},'detect_object':{}}
        return
    
    # Detect a contour with colour and return the rectangle of the largest colour
    def detect_color(self, frame, minC, maxC):
        frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        mask = cv2.inRange(frame_lab, minC, maxC) # Create a mask to isolate the colour regions
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_contour, contour_area_max = get_max_contour(contours, self.min_detection_area) #get the largest contour of note and its area
        target_rect = None; dtime = 0
        
        if max_contour is not None: #colour range was found
            target_rect = cv2.minAreaRect(max_contour) #make an area rectangle around the contour
            dtime = time.time()
            box = cv2.boxPoints(target_rect) # Get the four corner points
            
            if self.drawing: # drawing the target on the frame may slow things down
                box = np.int0(box) # Convert to integer type
                cv2.drawContours(frame, [box], 0, (0, 255, 0), 3) 

        return frame, target_rect, contour_area_max, dtime

    # TODO: Detect an object based on a model - could use teachable machine to create a model
    def detect_model(self, frame, model):
        
        rect = [0,0,0,0]
        dtime = time.time()
        conclusion = None

        return frame, rect, conclusion, dtime

    # Detect if a black or white line is in range
    def detect_line(self, frame, threshold=150):
        longest_line = ((0,0),(0,0)); dtime = 0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        #blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        #edges = cv2.Canny(blurred, 50, 150)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=threshold)

        if lines is not None:
            longest_line_length = 1500
            longest_line = None

            for line in lines:
                rho, theta = line[0]
                # Convert polar coordinates to Cartesian coordinates
                a = np.cos(theta)
                b = np.sin(theta)
                x0 = a * rho
                y0 = b * rho
                x1 = int(x0 + 1000 * (-b))
                y1 = int(y0 + 1000 * (a))
                x2 = int(x0 - 1000 * (-b))
                y2 = int(y0 - 1000 * (a))

                # Calculate the length of the line
                line_length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

                # Update the longest line if the current line is longer
                if line_length > longest_line_length:
                    longest_line_length = line_length
                    longest_line = ((x1, y1), (x2, y2))

            if longest_line:
                if self.drawing:
                    cv2.line(frame, longest_line[0], longest_line[1], (0, 0, 255), 2)
                dtime = time.time()
                
        return frame, longest_line, dtime
    
    # Stop the camera thread
    def stop(self):
        self.status = "Stop"
        self.logger.info("Ending Camera Thread")
        time.sleep(2)
        self.capture.release()
        return

    # Pause the camera
    def pause(self):
        self.logger.info("Pausing Camera")
        self.paused = True
        return
    
    # Resume the camera
    def resume(self):
        self.logger.info("Resuming Camera")
        self.paused = False
        return

#TEST CAMERA CODE 
if __name__ == '__main__':
    input("Please press enter to begin: ")
    '''
    colour = 'red'
    CAMERA = CameraInterface()
    CAMERA.start()
    #CAMERA.add_detection_task('detect_colour')
    #CAMERA.set_detection_colour(colour)
    CAMERA.drawing = True
    CAMERA.add_detection_task('detect_line')
    cv2.namedWindow('Detection Mode')
    cv2.resizeWindow('Detection Mode', 640, 480)
    time.sleep(3)
    while True:
        frame = CAMERA.get_frame()
        if frame is not None:
            cv2.imshow('Detection Mode', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    CAMERA.stop()
    cv2.destroyAllWindows()
    time.sleep(1)
    sys.exit(0)
    '''