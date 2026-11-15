# record.py
# One command that runs the whole test:
#   1. finds the sender and the receiver (asks each USB board for its role)
#   2. starts the sender, then the receiver
#   3. saves 30 seconds of CSI to a CSV in the data folder
# At 15 seconds it tells you to put the object between the boards.
#
# Both boards must be plugged into this computer first.
# Run it with:   ./record.sh
#
# Needs pyserial:  pip install pyserial

import serial
import glob
import sys
import time
import csv
import os
from datetime import datetime

# the motor code lives in the motor folder
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
from motor_run import MotorRunner

BAUD = 921600
RUN_SECONDS = 30
CHANGE_AT = 15      # seconds when you add the object

# ---------- find the sender and the receiver ----------
sender = None
receiver = None
others = []

for port in sorted(glob.glob("/dev/cu.usbserial*")):
    try:
        ser = serial.Serial(port, BAUD, timeout=0.2)
    except Exception as e:
        print("Could not open", port, "-", e)
        continue

    # restart the board with the reset line so it is in a clean state,
    # then wait for it to finish booting
    ser.dtr = False
    ser.rts = True
    time.sleep(0.2)
    ser.rts = False
    time.sleep(2.5)

    ser.reset_input_buffer()
    ser.write(b"?")
    time.sleep(0.5)
    reply = ser.read(500).decode("utf-8", errors="ignore")

    if "ROLE:SENDER" in reply:
        sender = ser
        print("Sender is on", port)
    elif "ROLE:RECEIVER" in reply:
        receiver = ser
        print("Receiver is on", port)
    else:
        print("No answer from", port)
        others.append(ser)

if sender is None or receiver is None:
    print("")
    print("Could not find both boards. Check that both are plugged in")
    print("and flashed with the latest sender and receiver code.")
    raise SystemExit(1)

# ---------- file name ----------
data_folder = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(data_folder, exist_ok=True)
name = datetime.now().strftime("session_%Y%m%d_%H%M%S.csv")
path = os.path.abspath(os.path.join(data_folder, name))

# ---------- connect the motor (it moves the receiver during the recording) ----------
motor = MotorRunner()
motor.connect()

# ---------- start both boards ----------
print("Starting in 3 seconds. Keep the middle clear.")
time.sleep(3)
receiver.reset_input_buffer()
sender.write(b"g")       # sender first
time.sleep(0.3)
receiver.write(b"g")     # then the receiver

rows = []
started = False
told_change = False
header_length = None
start = time.time()

while True:
    line = receiver.readline().decode("utf-8", errors="ignore").strip()

    # the receiver prints START when it begins recording
    if "START" in line:
        started = True
        start = time.time()
        motor.start()
        print("Recording... keep the middle clear for 15 seconds")
        continue

    # wait for START before doing anything else
    if not started:
        if time.time() - start > 10:
            print("Never saw START from the receiver.")
            break
        continue

    now = time.time() - start

    if now >= CHANGE_AT and not told_change:
        print("\n>>> PUT THE OBJECT IN THE MIDDLE NOW <<<\n")
        told_change = True

    if line.startswith("END"):
        print("Receiver says:", line)
        break

    if line.startswith("D,"):
        parts = line.split(",")
        # skip broken lines (they can be cut off)
        if header_length is None:
            header_length = len(parts)
        if len(parts) != header_length:
            continue
        phase = 0
        if now >= CHANGE_AT:
            phase = 1
        # host_s = seconds on the computer, phase = 0 before the object, 1 after
        rows.append([round(now, 3), phase] + parts[1:])

    # safety: stop if the receiver never says END
    if now > RUN_SECONDS + 10:
        print("Timed out waiting for END")
        break

# ---------- stop the motor ----------
motor.stop()

# ---------- save the csv ----------
if len(rows) == 0:
    print("No data received! Check the boards.")
else:
    num_subcarriers = header_length - 3
    header = ["host_s", "phase", "time_us", "rssi"]
    for i in range(num_subcarriers):
        header.append("a" + str(i))

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print("Saved", len(rows), "packets to", path)

sender.close()
receiver.close()
for ser in others:
    ser.close()
