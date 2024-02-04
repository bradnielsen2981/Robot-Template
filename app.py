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
DATABASE = Database("databases/test.db", app.logger)
ROBOT = None

#---VIEW FUNCTIONS----------------------------------------------------
# Backdoor
@app.route('/backdoor')
def backdoor():
    if DATABASE:
        results = DATABASE.ViewQuery("SELECT * FROM users")
    return jsonify(results)

# Login as the admin user
@app.route('/', methods=["GET","POST"])
def login():
    if 'userid' in session:
        return redirect('/mission')
    app.logger.info("Login")
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        if email == 'admin@admin' and password == 'admin': 
            session['userid'] = 1
            return redirect('./mission') #takes 3 seconds for the CAMERA to start
    return render_template("login.html")
 
# Dashboard for the robot
@app.route('/mission', methods=['GET','POST'])
def mission():
    loaded = 0
    if not 'userid' in session:
        return redirect('/')
    if ROBOT:
        loaded = 1
    return render_template('mission.html', robot_loaded=loaded)

#load the robot
@app.route('/load_robot', methods=['GET','POST'])
def load_robot():
    global ROBOT
    if not ROBOT:
        app.logger.info('Loading Robot')
        ROBOT = Robot(DATABASE)
        time.sleep(3) #takes 3 seconds to load the robot
    return jsonify({'message':'robot loaded'})

# YOUR FLASK CODE------------------------------------------------------------------------

# Manual move forward until stop is pressed
@app.route('/move_forward', methods=['GET','POST'])
def move_forward():
    app.logger.info('move forward')
    if ROBOT:
        ROBOT.SOUND.say("Moving forward")
        try:
            ROBOT.move_direction_time(power=35, direction=90, timelimit=5)
        except Exception as e:
            app.logger.info(e)
            ROBOT.stop()
    return jsonify({'message':'moving forward'})

# Manual stop
@app.route('/stop_command', methods=['GET','POST'])
def stop():
    app.logger.info('stop')
    if ROBOT:
        ROBOT.stop()
        app.logger.info('Stopping')
        ROBOT.SOUND.say('Stopping')
    return jsonify({'message':'stopping'})

# Move towards the detected colour
@app.route('/move_toward_colour', methods=['GET','POST'])
def move_toward_colour_detected():
    app.logger.info('move toward colour detected')
    try:
        if request.method == "POST":
            colour = request.form['colour']
            if ROBOT:
                ROBOT.SOUND.say("Move toward colour")
                ROBOT.move_toward_colour_detected(colour=colour)
    except Exception as e:
        print(e)
        ROBOT.stop_command()
        ROBOT.SOUND.say("Stopping")
    return jsonify({'message':'move_toward_colour_detected'})

# Look down
@app.route('/look_down', methods=['GET','POST'])
def look_down():
    app.logger.info('look down')
    if ROBOT:
        ROBOT.SOUND.say("Look down")
        ROBOT.look_down()
    return jsonify({'message':'look down'})

# Look up
@app.route('/look_up', methods=['GET','POST'])
def look_up():
    app.logger.info('look up')
    if ROBOT:
        ROBOT.look_up()
    return jsonify({'message':'look up'})











# CAMERA CODE-(do not touch!!)-------------------------------------------------------
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

# Turn on detection mode
@app.route('/turn_on_detection', methods=['GET','POST'])
def turn_on_detection():
    app.logger.info('turn on detection')
    if ROBOT:
        ROBOT.CAMERA.detect_all(exclude_colours=['black'])
    return jsonify({'message':'Detection mode on!!'})

# Turn off detection mode
@app.route('/turn_off_detection', methods=['GET','POST'])
def turn_off_detection():
    app.logger.info('turn off detection')
    if ROBOT:
        ROBOT.CAMERA.end_detection()
    return jsonify({'message':'Detection mode off!!'})

# Log out
@app.route('/logout')
def logout():
    app.logger.info('logging off')
    session.clear()
    return redirect('/')

# Shut down the robot
@app.route('/shutdown_robot', methods=['GET','POST'])
def shutdown_robot():
    app.logger.info("Shut down robot")
    global ROBOT
    if ROBOT:
        ROBOT.CAMERA.stop()
        ROBOT.stop()
        time.sleep(0.5)
        ROBOT = None
    return jsonify({'message':'Shutting Down'})

# Exit the web server
@app.route('/exit', methods=['GET','POST'])
def exit():
    app.logger.info("Exiting")
    shutdown_robot()
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return jsonify({'message':'Exiting'})

#---------------------------------------------------------------------------
# main method called web server application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) #runs a local server on port 5000