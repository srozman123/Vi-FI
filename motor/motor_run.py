# motor_run.py
# Moves the motor while a recording is running, by running step_5deg.py.
# All the movement settings (2 second wait, 10 degrees per move, speed, ...)
# are at the top of step_5deg.py, so change them there.
#
# How record.py and the web app use it:
#   motor = MotorRunner()
#   motor.connect()     # before the recording: checks the motor board is plugged in
#   motor.start()       # when the receiver says START (starts step_5deg.py)
#   motor.stop()        # when the recording is over (stops step_5deg.py)
#
# If the motor board is not plugged in, connect() says so and the recording
# just goes ahead without moving anything.

import atexit
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "step_5deg.py")
DEFAULT_PORT = "/dev/tty.usbmodem1401"   # if this changes, run: ls /dev/tty.usbmodem*


class MotorRunner:

    def __init__(self):
        self.port = None
        self.process = None

    def connect(self, log=print):
        # find the motor board's port (we only look, step_5deg.py opens it later)
        if os.path.exists(DEFAULT_PORT):
            self.port = DEFAULT_PORT
        else:
            ports = sorted(glob.glob("/dev/tty.usbmodem*"))
            if len(ports) == 0:
                log("Motor board not found, recording without the motor.")
                return False
            self.port = ports[0]

        log("Motor board found on " + self.port)
        atexit.register(self.stop)      # always stop the motor, even if the script crashes
        return True

    def start(self):
        if self.port is None:
            return
        env = dict(os.environ)
        env["MOTOR_PORT"] = self.port
        self.process = subprocess.Popen([sys.executable, SCRIPT], env=env)

    def stop(self):
        if self.process is None:
            return
        process = self.process
        self.process = None

        if process.poll() is None:
            # ask step_5deg.py to stop (it stops the motor before it exits)
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                print("Motor script had to be killed. Check that the motor stopped.")
