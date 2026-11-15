"""Spin the stepper on the TMCM-3216 nonstop until you press Ctrl+C."""
import time

from pytrinamic.connections import ConnectionManager
from pytrinamic.modules import TMCM3216

PORT = "/dev/tty.usbmodem1401"  # if this changes, run: ls /dev/tty.usbmodem*
AXIS = 0                        # motor plugged into port 0
SPEED = 25600                   # about half a turn per second; use a negative number to reverse
MOTOR_CURRENT = 128             # 0-255, about half the board's maximum
ONE_REV = 200 * 256             # 1.8° motor (200 steps) x 256 microsteps

with ConnectionManager(f"--interface serial_tmcl --port {PORT}").connect() as interface:
    module = TMCM3216(interface)
    motor = module.motors[AXIS]
    print(f"Connected to {module.name}, firmware {interface.get_version_string()}")

    # Switch the driver on (it starts off if the 20V came on after USB).
    motor.set_axis_parameter(motor.AP.MaxCurrent, MOTOR_CURRENT)
    if motor.get_axis_parameter(motor.AP.TOff) == 0:
        print("Warning: driver output is still off. Check the 20V supply.")

    start = motor.actual_position
    try:
        motor.rotate(SPEED)
        print("Spinning. Press Ctrl+C in the terminal to stop.")
        while True:
            time.sleep(1)
            print(f"  {(motor.actual_position - start) / ONE_REV:.1f} turns")
    except KeyboardInterrupt:
        pass
    finally:
        # The board keeps spinning on its own unless told to stop.
        motor.stop()
        print("Stopped.")
