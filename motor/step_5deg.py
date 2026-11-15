"""Wait 2 seconds, then keep moving the motor 10 degrees at a time, waiting 2 seconds
between moves, until 30 seconds have passed since this script started."""
import os
import signal
import time

from pytrinamic.connections import ConnectionManager
from pytrinamic.modules import TMCM3216

# if the port changes, run: ls /dev/tty.usbmodem*  (motor_run.py sets MOTOR_PORT for us)
PORT = os.environ.get("MOTOR_PORT", "/dev/tty.usbmodem1401")
AXIS = 0                        # motor plugged into port 0
START_DELAY_SECONDS = 2         # wait this long before the first move
STEP_DEGREES = 10
RUN_SECONDS = 30                # stop after this long, like the recording
PAUSE_SECONDS = 2               # wait between moves
SPEED = 5000                    # slow: about a tenth of a turn per second
ACCELERATION = 5000             # gentle start and stop (the board's default was 51160)
MOTOR_CURRENT = 128             # 0-255, about half the board's maximum
ONE_REV = 200 * 256             # 1.8° motor (200 steps) x 256 microsteps


def wait_until_reached(motor):
    while not motor.get_position_reached():
        time.sleep(0.02)


# When the recording ends, motor_run.py asks us to stop. Turn that request
# into Ctrl+C so the "finally" below still stops the motor.
def stop_now(signum, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop_now)
signal.signal(signal.SIGINT, stop_now)

script_start = time.time()      # the 30 seconds count from here


with ConnectionManager(f"--interface serial_tmcl --port {PORT}").connect() as interface:
    module = TMCM3216(interface)
    motor = module.motors[AXIS]
    print(f"Connected to {module.name}, firmware {interface.get_version_string()}")

    # Switch the driver on (it starts off if the 20V came on after USB).
    motor.set_axis_parameter(motor.AP.MaxCurrent, MOTOR_CURRENT)
    motor.set_axis_parameter(motor.AP.MaxAcceleration, ACCELERATION)
    if motor.get_axis_parameter(motor.AP.TOff) == 0:
        print("Warning: driver output is still off. Check the 20V supply.")

    start = motor.actual_position
    try:
        print(f"Waiting {START_DELAY_SECONDS} seconds before moving...")
        time.sleep(START_DELAY_SECONDS)

        i = 0
        while time.time() - script_start < RUN_SECONDS:
            i = i + 1
            # Degrees are not whole microsteps (10° is 1422.2), so aim at
            # absolute positions computed from the start; rounding errors never add up.
            target = start + round(i * STEP_DEGREES * ONE_REV / 360)
            motor.move_to(target, SPEED)
            wait_until_reached(motor)
            print(f"Move {i}: {i * STEP_DEGREES} degrees")
            time.sleep(PAUSE_SECONDS)
        print("Done (30 seconds are up).")
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        motor.stop()
