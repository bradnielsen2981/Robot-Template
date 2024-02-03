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

# Function to format a dictionary as a string with line breaks
def format_dict_with_line_breaks(d, indent=0):
    lines = []
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{' ' * indent}{key}:")
            lines.append(format_dict_with_line_breaks(value, indent + 4))
        else:
            lines.append(f"{' ' * indent}{key}: {value}")
    return "\n".join(lines)

#-------------------------------------------
# The Camera Object
class CameraInterface():

    #Initialise timelimit and logging
    def __init__(self, timelimit=20, logger=logging.getLogger()):
        self.timelimit=20
        self.logger = logger
        self.thread = None
        self.status = None
        self.frame = None
        self.detection_data = {'detect_line':{},'detect_colour':{},'detect_letter':{},'detect_model':{}} #detection dictionary will contain the name of the task and data that was detected
        self.detection_tasks = []
        self.detection_colours = []
        self.colour_shift = 0 #if more than one colour, colour will shift each frame
        self.task_shift = 0 #if more than one task, the task will shift each frame
        self.min_detection_area = 300
        self.detection_data_expire_time = 1
        self.clear_temp_detection_data = False
        self.output_text = False
        self.paused = False
        self.drawing = True
        self.dict_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.task_lock = threading.Lock()
        self.colours_lock = threading.Lock()
        self.clear_lock = threading.Lock()
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
        # self.logger.info("Starting Camera Thread")
        img = None
        time.sleep(2) #doesnt work without this, dont know why
        frame = None
        detection_data = {'detect_line':{},'detect_colour':{},'detect_letter':{},'detect_model':{}}
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
            
            currenttime = time.time()
            active_detection_task = None
            colour = None
            detection_tasks = None
            
            # clear the temporary detection data when required
            with self.clear_lock:
                if self.clear_temp_detection_data == True:
                    detection_data = {'detect_line':{},'detect_colour':{},'detect_letter':{},'detect_model':{}}
                    self.colour_shift = 0
                    self.task_shift = 0
                    self.clear_temp_detection_data = False
            
            with self.task_lock:
                detection_tasks = self.detection_tasks
                
            if len(detection_tasks) > 0:
                                
                active_detection_task = detection_tasks[self.task_shift]
                self.task_shift = (self.task_shift + 1)%len(detection_tasks)
            
                if "detect_line" in detection_tasks:
                    if active_detection_task == None or active_detection_task == 'detect_line': 
                        frame, line, found = self.detect_line(frame, threshold=100)
                        if found:
                            detection_data['detect_line'] = {}
                            detection_data['detect_line']['found'] = True
                            detection_data['detect_line']['line'] = line
                            detection_data['detect_line']['time'] = currenttime
                        else:
                            if 'found' in detection_data['detect_line']: #expire old data
                                if (currenttime - detection_data['detect_line']['time']) > self.detection_data_expire_time:
                                    detection_data['detect_line'] = {}    
        
                if "detect_colour" in detection_tasks:
                    
                    if active_detection_task == None or active_detection_task == 'detect_colour':
                        
                        if len(self.detection_colours) > 1:
                            colour = self.detection_colours[self.colour_shift]
                            self.colour_shift = (self.colour_shift+1)%len(self.detection_colours)
                            
                        elif len(self.detection_colours) == 1:
                            colour = self.detection_colours[0]
                        else:
                            self.colour_shift = 0
                            continue #there are no colours
                        
                        if colour in self.lab_colours.keys():
                            minC = np.array(self.lab_colours[colour]['min']) #min colour range
                            maxC = np.array(self.lab_colours[colour]['max']) #max colour range
                            
                            frame, rect, area, found = self.detect_color(frame, minC, maxC)
                            if found:
                                detection_data['detect_colour'][colour] = {}
                                detection_data['detect_colour'][colour]['found'] = True
                                detection_data['detect_colour'][colour]['area'] = area
                                detection_data['detect_colour'][colour]['rect'] = rect #detection data will only exist if colour detected
                                detection_data['detect_colour'][colour]['time'] = currenttime
                            else:
                                if colour in detection_data['detect_colour']:
                                    if 'found' in detection_data['detect_colour'][colour]:
                                        if (currenttime - detection_data['detect_colour'][colour]['time']) > self.detection_data_expire_time:
                                            #print(colour, "data has expired!")
                                            detection_data['detect_colour'] = {}  

                if "detect_letter" in detection_tasks:
                    if active_detection_task == None or active_detection_task == 'detect_letter':
                        pass
                            
                if "detect_model" in detection_tasks: #i could use keras here...
                    if active_detection_task == None or active_detection_task == 'detect_model':
                        pass
                    
                #write text if output_text is on - update the test every two seconds
                if self.output_text:
                    data = None
                    coord = (10, 10)  # Coordinates of the text
                    formatted_text = format_dict_with_line_breaks(detection_data)
                    lines = formatted_text.split('\n')
                    y_offset = 0
                    for line in lines:
                        cv2.putText(frame, line, (coord[0], coord[1] + y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,255,255), 1, cv2.LINE_AA)
                        y_offset += 20  # Adjust the vertical spacing between lines
            else:
                self.task_shift = 0
                
            with self.frame_lock:
                self.frame = frame
                
            with self.dict_lock:
                self.detection_data = detection_data.copy()
                
        return
    
    # Detect a contour with colour and return the rectangle of the largest colour
    def detect_color(self, frame, minC, maxC):
        frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        found = False
        mask = cv2.inRange(frame_lab, minC, maxC) # Create a mask to isolate the colour regions
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_contour, contour_area_max = get_max_contour(contours, self.min_detection_area) #get the largest contour of note and its area
        target_rect = None; dtime = 0
        
        if max_contour is not None: #colour range was found
            target_rect = cv2.minAreaRect(max_contour) #make an area rectangle around the contour
            found = True
            box = cv2.boxPoints(target_rect) # Get the four corner points
            
            if self.drawing: # drawing the target on the frame may slow things down
                box = np.int0(box) # Convert to integer type
                cv2.drawContours(frame, [box], 0, (0, 255, 0), 3) 

        return frame, target_rect, contour_area_max, found

    # TODO: Detect an object based on a model - could use teachable machine to create a model
    def detect_model(self, frame, model):
        
        rect = [0,0,0,0]
        found = False
        conclusion = None

        return frame, rect, conclusion, found

    # TODO: Detect a Letter 
    def detect_letter(self, frame):
        
        rect = [0,0,0,0]
        found = False
        conclusion = None

        return frame, rect, conclusion, found

    # Detect if a black or white line is in range
    def detect_line(self, frame, threshold=150):
        longest_line = ((0,0),(0,0)); dtime = 0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found = False
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
                    cv2.line(frame, longest_line[0], longest_line[1], (255, 0, 0), 2)
                found = True
                
        return frame, longest_line, found
    
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
            return self.detection_data.copy()
        
    # Clear detection data
    def clear_detection_data(self):
        with self.dict_lock:
            self.detection_data = {'detect_line':{},'detect_colour':{},'detect_letter':{},'detect_model':{}}
        with self.clear_lock:
            self.clear_temp_detection_data = True #clear temporary detection data
        return
    
    # add the detection task to be either 'detect_line', 'detect_colour', 'detect_letter', 'detect_model' - model not implemented yet
    def add_detection_task(self, task):
        with self.task_lock:
            if task not in self.detection_tasks:
                self.detection_tasks.append(task)
        return
    
    # set the detection tasks to be a list
    def set_detection_tasks(self, tasks=[]):
        with self.task_lock:
            self.detection_tasks = tasks
        return
    
    def clear_detection_tasks(self):
        with self.task_lock:
            self.detection_tasks.clear()    
    
    # Tests all detection tasks
    def detect_all(self, exclude_colours=[]):
        for key in self.detection_data.keys():
            self.add_detection_task(key)
        with self.colours_lock:
            self.detection_colours = list(self.lab_colours.keys())
            for colour in exclude_colours:
                self.detection_colours.remove(colour)
        return
    
    # turn on output text
    def turn_on_output_text(self):
        self.output_text = True
        return
    
    # turn off output text
    def turn_off_output_text(self):
        self.output_text = False
        return
    
    # remove a specific detection task
    def remove_detection_task(self, task):
        with self.task_lock:
            self.detection_tasks.remove(task)
        return
    
    # Stop the detection task
    def end_detection(self):
        self.clear_detection_tasks()
        self.clear_detection_data()
        self.clear_detection_colours()
        return
    
    # Show drawing
    def turn_on_drawing(self):
        self.drawing = True
        return
    
    # Hide drawing - will increase speed
    def turn_off_drawing(self):
        self.drawing = False
        return
    
    # Set the detection colour - the colour name should have been set using the ARM application
    def add_detection_colour(self, colour):
        with self.colours_lock:
            if colour not in self.detection_colours:
                self.detection_colours.append(colour)
        return
    
    def set_detection_colours(self, colourlist):
        with self.colours_lock:
            self.detection_colours = colourlist
        return
    
    # remove detection colours
    def remove_detection_colour(self, colour):
        with self.colours_lock:
            self.detection_colours.remove(colour)
        return
    
    # Clear detection colours
    def clear_detection_colours(self):
        with self.colours_lock:
            self.detection_colours.clear()
        return
    
    # Stop the camera thread
    def stop(self):
        self.status = "Stop"
        #self.logger.info("Ending Camera Thread")
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
    CAMERA = CameraInterface()
    CAMERA.start()
    CAMERA.detect_all()
    CAMERA.turn_on_output_text()
    CAMERA.turn_on_drawing()
    cv2.namedWindow('Detection Mode')
    cv2.resizeWindow('Detection Mode', 640, 480)
    time.sleep(3)
    while True:
        frame = CAMERA.get_frame()
        time.sleep(0.01)
        if frame is not None:
            cv2.imshow('Detection Mode', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    CAMERA.end_detection()
    CAMERA.stop()
    cv2.destroyAllWindows()
    time.sleep(1)
    sys.exit(0)