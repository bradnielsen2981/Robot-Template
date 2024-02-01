from flask import *
from interfaces.databaseinterface import Database
from interfaces.hashing import *
from robot import Robot
import logging, time, sys

#---CONFIGURE APP---------------------------------------------------
app = Flask(__name__)
logging.basicConfig(filename='logs/flask.log', level=logging.INFO)
sys.tracebacklimit = 10
app.config['SECRET_KEY'] = "Type in a secret line of text"

#---EMBED OBJECTS---------------------------------------------------
DATABASE = Database("database/test.db", app.logger)
ROBOT = Robot(DATABASE)

#---VIEW FUNCTIONS----------------------------------------------------
# Login as the admin user
@app.route('/', methods=["GET","POST"])
def login():
    app.logger.info("Login")
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        if email == 'admin@admin' and password == 'admin': 
            session['userid'] = 1
            time.sleep(3)
            return redirect('./mission') #takes 3 seconds for the CAMERA to start
    return render_template("login.html")

# Dashboard for the robot
@app.route('/mission', methods=['GET','POST'])
def mission():
    frame = ROBOT.CAMERA.get_jpeg_frame()
    if not 'userid' in session:
        return redirect('/')
    return render_template('mission.html')

# YOUR FLASK CODE------------------------------------------------------------------------

# Manual move forward until stop is pressed
@app.route('/move_forward', methods=['GET','POST'])
def move_forward():
    if ROBOT:
        ROBOT.SOUND.say("Moving forward")
        ROBOT.move_direction_time(power=35, direction=90, timelimit=5)
    return jsonify({'message':'moving forward'})

# Manual stop
@app.route('/stop', methods=['GET','POST'])
def stop():
    if ROBOT:
        ROBOT.stop()
        ROBOT.SOUND.say("Stopping")
    return jsonify({'message':'stopping'})

# Move towards the detected colour
@app.route('/move_toward_colour', methods=['GET','POST'])
def move_toward_colour_detected():
    if request.method == "POST":
        colour = request.form.get('colour')
        if ROBOT:
            try:
                ROBOT.move_toward_colour_detected(colour=colour)
            except Exception as e:
                print(e)
                ROBOT.stop_command()
                ROBOT.SOUND.say("Stopping")
    return jsonify({'message':'move_toward_colour_detected'})



















# CAMERA CODE-----------------------------------------------------------------------
# Continually gets the frame from the pi camera
def videostream():
    """Video streaming generator function."""
    while True:
        if ROBOT:
            frame = ROBOT.CAMERA.get_jpeg_frame() #can change quality to test efficiency
            if frame:
                yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                return '', 204
        else:
            return '', 204 

# Embeds the videofeed by returning a continual stream as above
@app.route('/videofeed')
def videofeed():
    if ROBOT:
        """Video streaming route. Put this in the src attribute of an img tag."""
        return Response(videostream(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return '', 204

# Shut down the web server if necessary
@app.route('/turn_on_detection', methods=['GET','POST'])
def turn_on_detection():
    if ROBOT:
        ROBOT.CAMERA.detect_all(exclude_colours=['black'])
    return jsonify({'message':'Detection mode on!!'})

# Shut down the web server if necessary
@app.route('/turn_off_detection', methods=['GET','POST'])
def turn_off_detection():
    if ROBOT:
        ROBOT.CAMERA.end_detection()
    return jsonify({'message':'Detection mode off!!'})

# Log out
@app.route('/logout')
def logout():
    app.logger.info('logging off')
    session.clear()
    return redirect('/')

# Shut down the web server if necessary
@app.route('/shutdown', methods=['GET','POST'])
def shutdown():
    print("Shutting Down")
    ROBOT = None
    DATABASE = None
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return jsonify({'message':'Shutting Down'})

#---------------------------------------------------------------------------
# main method called web server application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) #runs a local server on port 5000