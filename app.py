from flask import *
from interfaces.databaseinterface import Database
from interfaces.hashing import *
from robot import Robot
import logging, time, sys

DATABASE = Database("database/test.db", app.logger)
ROBOT = Robot(DATABASE)

#---CONFIGURE APP---------------------------------------------------
app = Flask(__name__)
logging.basicConfig(filename='logs/flask.log', level=logging.INFO)
sys.tracebacklimit = 10
app.config['SECRET_KEY'] = "Type in a secret line of text"

#---VIEW FUNCTIONS----------------------------------------------------
# Login as the admin user
@app.route('/', methods=["GET","POST"])
def login():
    app.logger.info("Login")
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        if email == 'admin@admin' and password == 'password': 
            print("GOT HERE")
            session['userid'] = 1
            if time.time() + 3 > ROBOT.starttime:
                return redirect('./dashboard') #takes 3 seconds for the CAMERA to start
            else: #wait for camera to start
                time.sleep(3)
                return redirect('./dashboard')
    return render_template("login.html")

# Dashboard for the robot
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    frame = ROBOT.CAMERA.get_jpeg_frame()
    if not 'userid' in session:
        return redirect('/')
    return render_template('dashboard.html')

# YOUR FLASK CODE------------------------------------------------------------------------








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

#embeds the videofeed by returning a continual stream as above
@app.route('/videofeed')
def videofeed():
    if ROBOT:
        """Video streaming route. Put this in the src attribute of an img tag."""
        return Response(videostream(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return '', 204

#Shut down the web server if necessary
@app.route('/camera_test', methods=['GET','POST'])
def camera_test():
    ROBOT.CAMERA.detect_all()
    return jsonify({'message':'Testing Camera'})

@app.route('/logout')
def logout():
    app.logger.info('logging off')
    session.clear()
    return redirect('/')

#Shut down the web server if necessary
@app.route('/shutdown', methods=['GET','POST'])
def shutdown():
    print("Shutting Down")
    ROBOT = None
    DATABASE = None
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return jsonify({'message':'Shutting Down'})

#---------------------------------------------------------------------------
#main method called web server application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) #runs a local server on port 5000