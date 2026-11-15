"""Turn a stepper on the TMCM-3216 one revolution forward, then back."""
import time

from pytrinamic.connections import ConnectionManager
from pytrinamic.modules import TMCM3216

PORT = "/dev/tty.usbmodem1401"  # if this changes, run: ls /dev/tty.usbmodem*
AXIS = 0                        # TMCM-3216 has three axes: 0, 1, 2
ONE_REV = 200 * 256             # 1.8° motor (200 steps) x 256 microsteps
SPEED = 25600                   # microsteps/s, about half a turn per second
MOTOR_CURRENT = 128             # 0-255, about half the board's maximum


def wait_until_reached(motor):
    while not motor.get_position_reached():
        time.sleep(0.05)


with ConnectionManager(f"--interface serial_tmcl --port {PORT}").connect() as interface:
    module = TMCM3216(interface)
    motor = module.motors[AXIS]
    print(f"Connected to {module.name}, firmware {interface.get_version_string()}")

    # The driver chips start with output off and zero current when the 20V
    # supply comes on after USB. Setting the current re-enables the driver.
    motor.set_axis_parameter(motor.AP.MaxCurrent, MOTOR_CURRENT)
    if motor.get_axis_parameter(motor.AP.TOff) == 0:
        print("Warning: driver output is still off. Check the 20V supply.")

    try:
        print("Forward one revolution...")
        motor.move_by(ONE_REV, SPEED)
        wait_until_reached(motor)

        print("Back one revolution...")
        motor.move_by(-ONE_REV, SPEED)
        wait_until_reached(motor)

        print(f"Done. Position: {motor.actual_position}")
    finally:
        # Stop the motor even on Ctrl+C or an error; the module keeps running
        # a move on its own after the script exits otherwise.
        motor.stop()
