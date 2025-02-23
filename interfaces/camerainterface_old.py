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

try:
    from pycoral.utils.dataset import read_label_file
    from pycoral.utils.edgetpu import make_interpreter
    from pycoral.adapters import common
    from pycoral.adapters import classify
    from pycoral.utils.edgetpu import list_edge_tpus
    tpu_devices = list_edge_tpus()
    if tpu_devices:
        print("Edge TPU devices found:", tpu_devices)
    else:
        print("No Edge TPU devices detected.")
    MODELDETECTION_ENABLED = True
except:
    print("pycoral not installed. Model detection disabled.")
    MODELDETECTION_ENABLED = False

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

# Function to format detection dictionary as a string with line breaks
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

    # Initialise timelimit and logging
    def __init__(self, timelimit=20, logger=logging.getLogger()):
        self.timelimit=20
        self.logger = logger
        self.thread = None
        self.status = None
        self.frame = None
        self.frameskip = 2
        self.detection_data = { } #detection dictionary will contain the name of the task and data that was detected
        self.detection_tasks = []
        self.detection_colours = []
        self.detection_model = None
        self.detection_model_labels = None
        self.labels = None
        self.input_details = None
        self.output_details = None
        self.colour_shift = 0 #if more than one colour, colour will shift each frame
        self.task_shift = 0 #if more than one task, the task will shift each frame
        self.linecolour = "black"
        self.min_detection_area = 800
        self.detection_data_expire_time = 1
        self.clear_temp_detection_data = False
        self.output_text = True
        self.output_message = ""
        self.paused = False
        self.drawing = True
        self.dict_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.task_lock = threading.Lock()
        self.colours_lock = threading.Lock()
        self.clear_lock = threading.Lock()
        self.logger = logging.getLogger('CameraInterface')
        setup_logger(self.logger, '../logs/camera.log')
        np.set_printoptions(suppress=True) # Disable scientific notation for clarity
        
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
    
    # Start the camera
    def start(self):
        if self.status == "Ready":
            self.thread = threading.Thread(target=self.update, args=())
            self.thread.daemon = True
            self.currenttime = time.time()
            self.thread.start()
            self.status = "Running"
            
        return
    
    # Function is run by thread...
    def update(self):
        # self.logger.info("Starting Camera Thread")
        img = None
        time.sleep(2) #doesnt work without this, dont know why

        #temp variables
        frame = None
        framecount = 0
        framerate = 0.0
        detection_data = {}
        detection_tasks = None
        active_detection_task = None
        colour = None

        #to exit the thread, set status to Stopped
        while self.status == "Running":

            if self.paused: #pause the camera update
                continue
            try:
                ret, img = self.capture.read()
                if not ret:
                    continue
                else:
                    frame = img.copy() #update the current frame
            except:
                continue
            
            # clear the temporary detection data when required
            if self.clear_temp_detection_data == True:
                with self.clear_lock:
                    detection_data.clear()
                    self.colour_shift = 0
                    self.task_shift = 0
                    self.clear_temp_detection_data = False
            
            #set detection tasks
            with self.task_lock:
                detection_tasks = self.detection_tasks

            #FRAME SKIP - only process every second frame
            framecount+=1
            if framecount>=self.frameskip:
                framecount=0
                
                #get current time
                currenttime = time.time()

                if len(detection_tasks) != 0: #there are one or more detection tasks
                                    
                    active_detection_task = detection_tasks[self.task_shift] #with more than one detection task

                    if len(detection_tasks) > 0:
                        self.task_shift = (self.task_shift + 1)%len(detection_tasks)
                
                    #check for line detection
                    if "detect_line" in detection_tasks:
                        if 'detect_line' not in detection_data:
                            detection_data['detect_line'] = {}

                        if active_detection_task == None or active_detection_task == 'detect_line': 
                            frame, data = self.detect_line(currenttime, frame, threshold=100, colour=self.linecolour)
                            if data['found']:
                                detection_data['detect_line'] = data.copy()
                            else: #data['found'] == False
                                if 'found' in detection_data['detect_line']: #expire old data
                                    if (currenttime - detection_data['detect_line']['time']) > self.detection_data_expire_time:
                                        detection_data['detect_line'] = {}  #clear old data  
            
                    #check for colour detection
                    if "detect_colour" in detection_tasks:
                        if active_detection_task == None or active_detection_task == 'detect_colour':
                            if 'detect_colour' not in detection_data:
                                detection_data['detect_colour'] = {}
                            
                            colour = None
                            if len(self.detection_colours) > 1:
                                colour = self.detection_colours[self.colour_shift]
                                self.colour_shift = (self.colour_shift+1)%len(self.detection_colours)
                                
                            elif len(self.detection_colours) == 1:
                                colour = self.detection_colours[0]
                            else:
                                self.colour_shift = 0
                                
                            if colour != None:
                                if colour in self.lab_colours.keys():
                                    minC = np.array(self.lab_colours[colour]['min']) #min colour range
                                    maxC = np.array(self.lab_colours[colour]['max']) #max colour range
                                    
                                    frame, data = self.detect_color(currenttime, frame, minC, maxC)
                                    if data['found']:
                                        detection_data['detect_colour'][colour] = data.copy()
                                    
                                    if colour in detection_data['detect_colour']:
                                        if 'found' in detection_data['detect_colour'][colour]:
                                            if (currenttime - detection_data['detect_colour'][colour]['time']) > self.detection_data_expire_time:
                                                detection_data['detect_colour'] = {}  #clear old data

                    #use neural network for detection using a tflite model                                
                    if "detect_model" in detection_tasks: #i could use keras here...
                        if active_detection_task == None or active_detection_task == 'detect_model':
                            if 'detect_model' not in detection_data:
                                detection_data['detect_model'] = {}

                            frame, data = self.detect_model(currenttime, frame)
                            if data['found']:
                                detection_data['detect_model'] = data.copy()
                            else:
                                if 'found' in detection_data['detect_model']: #expire old data
                                    if (currenttime - detection_data['detect_model']['time']) > self.detection_data_expire_time:
                                        detection_data['detect_model'] = {}  #clear old data  
                        
                else:
                    self.task_shift = 0
                
                #get current frame rate
                elapsedtime = currenttime - self.currenttime
                self.currenttime = currenttime
                if elapsedtime > 0:
                    framerate = round(self.frameskip/elapsedtime, 2) #it should be an average framerate 
                #END FRAME SKIP

            # draw detection lines and boxes
            if self.drawing:
                if 'detect_line' in detection_data:
                    if 'found' in detection_data['detect_line']:
                        if detection_data['detect_line']['found']:
                            start_point = detection_data['detect_line']['line'][0]
                            end_point = detection_data['detect_line']['line'][1]
                            cv2.line(frame, start_point, end_point, (255, 0, 0), 2)

                if 'detect_colour' in detection_data:
                    for color, data in detection_data['detect_colour'].items():
                        if data['found']:
                            box = cv2.boxPoints(data['rect'])
                            box = np.int0(box) # Convert to integer type
                            cv2.drawContours(frame, [box], 0, (0, 255, 0), 2)
            
            # Write text if output_text is on - update the test every two seconds
            if self.output_text:
                coord = (10, 10)
                cv2.putText(frame, "Frame rate: " + str(framerate), (coord[0], coord[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,0,255), 1, cv2.LINE_AA)
                coord = (300, 10)
                cv2.putText(frame, self.output_message, (coord[0], coord[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,0,255), 1, cv2.LINE_AA)
                self.output_message = "" #clear the output message
                coord = (10, 20)

                # If there is current detection - write out the detection data
                if len(detection_tasks) > 0:
                    formatted_text = format_dict_with_line_breaks(detection_data)
                    lines = formatted_text.split('\n')
                    y_offset = 0
                    for line in lines:
                        cv2.putText(frame, line, (coord[0], coord[1] + y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,0,255), 1, cv2.LINE_AA)
                        y_offset += 20  # Adjust the vertical spacing between lines
                    
            with self.frame_lock:
                self.frame = frame
                
            with self.dict_lock:
                self.detection_data = detection_data.copy()
                
        return
    
    # Detect line
    def detect_line(self, currenttime, frame, threshold=150, colour=None):

        data = {'found': False}
        frame_mask = None

        if colour is not None:
            if colour in self.lab_colours:
                minC = np.array(self.lab_colours[colour]['min'])  # Min color range
                maxC = np.array(self.lab_colours[colour]['max'])  # Max color range
                frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                frame_mask = cv2.inRange(frame_lab, minC, maxC)  # Corrected reference
            else:
                frame_mask = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame_mask = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(frame_mask, 50, 150, apertureSize=3)
        # Use probabilistic Hough Transform for efficiency
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
                data = {'found':True,'line':longest_line,'time':currenttime }

        return frame, data
    
    # Detect a contour with colour and return the rectangle of the largest colour
    def detect_color(self, currenttime, frame, minC, maxC):
        
        frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        mask = cv2.inRange(frame_lab, minC, maxC) # Create a mask to isolate the colour regions
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_contour, contour_area_max = get_max_contour(contours, self.min_detection_area) #get the largest contour of note and its area
        data = { 'found':False }
        
        if max_contour is not None: #colour range was found
            target_rect = cv2.minAreaRect(max_contour) #make an area rectangle around the contour
            data = { 'found':True, 'area':contour_area_max, 'rect':target_rect, 'time':currenttime }

        return frame, data

    # Detect an object based on a model - could use teachable machine to create a model
    def detect_model(self, currenttime, frame):
        data = {'found': None}
        
        if not MODELDETECTION_ENABLED or self.detection_model is None:
            return frame, data

        size = common.input_size(self.detection_model)  # Ensure this is (416, 416)

        # Use OpenCV's optimized preprocessing
        blob = cv2.dnn.blobFromImage(frame, scalefactor=1.0, size=size, swapRB=True, crop=False)

        # Convert from (1, 3, H, W) → (H, W, 3) for PyCoral
        input_data = np.squeeze(blob, axis=0).transpose(1, 2, 0)  # Removes batch dimension, reorders axes

        # Convert input data type to match PyCoral's expected format
        input_data = np.uint8(input_data)  # PyCoral expects uint8 tensor

        # Set input tensor for the model
        common.set_input(self.detection_model, input_data)

        # Run inference
        self.detection_model.invoke()

        # Get output predictions
        output_details = self.detection_model.get_output_details()[0]
        predictions = self.detection_model.get_tensor(output_details['index'])

        if predictions is not None and len(predictions) > 0:
            max_index = np.argmax(predictions)  # Get the class index with the highest probability
            label = self.labels[max_index] if max_index < len(self.labels) else "Unknown"
            print(f"Detected: {label}")

        return frame, data

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
            
    # Get current detection data
    def get_detection_data(self):
        with self.dict_lock:
            return self.detection_data.copy()
        
    # Clear detection data
    def clear_detection_data(self):
        with self.dict_lock:
            self.detection_data.clear()
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
        for task in tasks:
            self.add_detection_task(task)
        return
    
    # clear the detection tasks
    def clear_detection_tasks(self):
        with self.task_lock:
            self.detection_tasks.clear()
        return
    
    # Tests all detection tasks
    def detect_all(self, exclude_colours=[]):
        self.add_detection_task('detect_colour')
        self.add_detection_task('detect_line')
        #self.add_detection_task('detect_model')
        
        # DETECT ALL COLOURS WITH A COLOUR SHIFT
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
    
    #set an extra output message - can be used for other sensors e.g. voltage, sonar, temperature
    def set_output_message(self, message):
        self.output_message = message
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
    
    # Add the detection colour - the colour name should have been set using the ARM application
    def add_detection_colour(self, colour):
        with self.colours_lock:
            if colour not in self.detection_colours:
                self.detection_colours.append(colour)
        return
    
    # Set the detection colours as a list
    def set_detection_colours(self, colourlist):
        with self.colours_lock:
            self.detection_colours = colourlist
        return
    
    #set the line detection colour
    def set_line_detection_colour(self, colour):
        self.linecolour = "colour"
        return
    
    # Load the detection model
    def load_detection_model(self, model_file, classes_file):
        self.detection_model = make_interpreter(model_file)
        self.detection_model.allocate_tensors()
        
        self.input_details = self.detection_model.get_input_details()
        self.output_details = self.detection_model.get_output_details()
        
        #self.detection_model_labels = read_label_file(classes_file) 
        
        # Load COCO class labels
        with open(classes_file, "r") as f:
            self.labels = [line.strip() for line in f.readlines()]       
        return
    
    # Clear the detection model
    def clear_detection_model(self, model):
        self.detection_model = None
        self.detection_model_class_names = None
        return
    
    # Remove detection colours
    def remove_detection_colour(self, colour):
        with self.colours_lock:
            self.detection_colours.remove(colour)
        return
    
    # Clear detection colours
    def clear_detection_colours(self):
        with self.colours_lock:
            self.detection_colours.clear()
        return
    
    #creates the detection window
    def create_detection_window(self):
        cv2.namedWindow('Detection Mode')
        cv2.resizeWindow('Detection Mode', 640, 480)
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
    print("\033c")
    CAMERA.start()
    #CAMERA.load_detection_model("models/quant_coco-tiny-v3-relu_edgetpu.tflite", "models/cocov2.names")
    #CAMERA.add_detection_task('detect_model')
    #CAMERA.add_detection_task('detect_colour')
    #CAMERA.add_detection_colour('red')
    CAMERA.create_detection_window()

    prev_time = time.time()
    frame_count = 0
    while True:
        frame = CAMERA.get_frame()
        
        if frame is not None:
            cv2.imshow('Detection Mode', frame)

            # FPS Calculation
            frame_count += 1
            current_time = time.time()
            elapsed_time = current_time - prev_time

            if elapsed_time >= 1.0:  # Update every second
                fps = frame_count / elapsed_time
                print(f"FPS: {fps:.2f}")
                prev_time = current_time
                frame_count = 0

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    CAMERA.end_detection()
    CAMERA.stop()
    cv2.destroyAllWindows()
    time.sleep(1)
    sys.exit(0)