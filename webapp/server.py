# server.py
# A small web server for the live demo.
#   - serves the page (index.html)
#   - the Start button calls /start, which runs the test on the boards
#   - /events streams the live numbers to the page
#
# Run it from the wifi-breathing folder with:
#   .venv/bin/python webapp/server.py
# Then open http://localhost:8000
#
# Nothing in the other folders is changed. Recordings are saved in webapp/data/

import glob
import json
import os
import statistics as st
import threading
import time
import csv
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial

PORT = 8000
BAUD = 921600
RUN_SECONDS = 30
CHANGE_AT = 15          # seconds when the page tells you to add the object
BIN_SECONDS = 0.2       # we average the packets into 0.2 second chunks for the graph

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(HERE, "data")

# ---------- shared state (the web server and the test thread both use these) ----------
events = []                     # everything sent to the page during the current run
lock = threading.Lock()
running = False


def add_event(event):
    with lock:
        events.append(event)


def status(message):
    print(message)
    add_event({"type": "status", "msg": message})


# ---------- the test (runs in its own thread) ----------
def find_boards():
    sender = None
    receiver = None
    others = []

    for port in sorted(glob.glob("/dev/cu.usbserial*")):
        try:
            ser = serial.Serial(port, BAUD, timeout=0.2)
        except Exception as e:
            status("Could not open " + port + ": " + str(e))
            continue

        # restart the board so it is in a clean state, then wait for it to boot
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
            status("Sender is on " + port)
        elif "ROLE:RECEIVER" in reply:
            receiver = ser
            status("Receiver is on " + port)
        else:
            status("No answer from " + port)
            others.append(ser)

    return sender, receiver, others


def run_test():
    global running

    sender = None
    receiver = None
    others = []

    try:
        status("Looking for the boards (takes a few seconds)...")
        sender, receiver, others = find_boards()

        if sender is None or receiver is None:
            status("Could not find both boards. Are both plugged in and flashed?")
            add_event({"type": "error"})
            return

        status("Starting in 3 seconds. Keep the middle clear.")
        time.sleep(3)
        receiver.reset_input_buffer()
        sender.write(b"g")          # sender first
        time.sleep(0.3)
        receiver.write(b"g")        # then the receiver

        rows = []                   # every packet, for the CSV
        alive = None                # which subcarriers are in use
        warmup = []                 # first packets, used to find the alive subcarriers
        bin_packets = []            # packets in the current 0.2 second chunk
        bin_number = 0
        started = False
        told_change = False
        header_length = None
        start = time.time()

        while True:
            line = receiver.readline().decode("utf-8", errors="ignore").strip()

            if "START" in line:
                started = True
                start = time.time()
                add_event({"type": "started", "run_seconds": RUN_SECONDS, "change_at": CHANGE_AT})
                status("Recording... keep the middle clear")
                continue

            if not started:
                if time.time() - start > 10:
                    status("Never saw START from the receiver.")
                    add_event({"type": "error"})
                    return
                continue

            now = time.time() - start

            if now >= CHANGE_AT and not told_change:
                told_change = True
                add_event({"type": "prompt"})

            if line.startswith("END"):
                status("Receiver says: " + line)
                break

            if now > RUN_SECONDS + 10:
                status("Timed out waiting for END")
                break

            if line.startswith("D,"):
                parts = line.split(",")

                # skip broken lines (they can be cut off)
                if header_length is None:
                    header_length = len(parts)
                if len(parts) != header_length:
                    continue

                try:
                    rssi = int(parts[2])
                    amps = [float(x) for x in parts[3:]]
                except ValueError:
                    continue

                phase = 0
                if now >= CHANGE_AT:
                    phase = 1
                rows.append([round(now, 3), phase] + parts[1:])

                # find which subcarriers are in use from the first 30 packets
                if alive is None:
                    warmup.append(amps)
                    if len(warmup) >= 30:
                        alive = []
                        for i in range(len(amps)):
                            if st.mean(p[i] for p in warmup) > 3:
                                alive.append(i)
                    continue

                # which 0.2 second chunk is this packet in?
                this_bin = int(now / BIN_SECONDS)
                if this_bin != bin_number and len(bin_packets) > 0:
                    send_point(bin_number, bin_packets, alive)
                    bin_packets = []
                bin_number = this_bin
                bin_packets.append((rssi, amps))

        # send the last chunk
        if alive is not None and len(bin_packets) > 0:
            send_point(bin_number, bin_packets, alive)

        # save the csv
        saved = None
        if len(rows) > 0:
            os.makedirs(DATA_FOLDER, exist_ok=True)
            name = datetime.now().strftime("session_%Y%m%d_%H%M%S.csv")
            path = os.path.join(DATA_FOLDER, name)
            header = ["host_s", "phase", "time_us", "rssi"]
            for i in range(header_length - 3):
                header.append("a" + str(i))
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            saved = path
            status("Saved " + str(len(rows)) + " packets to " + path)
        else:
            status("No data received. Check the boards.")

        add_event({"type": "done", "saved": saved})

    except Exception as e:
        status("Error: " + str(e))
        add_event({"type": "error"})

    finally:
        for ser in [sender, receiver] + others:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
        running = False


def send_point(bin_number, packets, alive):
    # average RSSI, average CSI amplitude, and CSI "wobble" for this chunk
    rssi_mean = st.mean(p[0] for p in packets)
    amp_mean = st.mean(st.mean(p[1][i] for i in alive) for p in packets)
    wobble = 0
    if len(packets) > 1:
        wobble = st.mean(st.pstdev([p[1][i] for p in packets]) for i in alive)
    add_event({
        "type": "point",
        "t": round(bin_number * BIN_SECONDS, 2),
        "rssi": round(rssi_mean, 2),
        "amp": round(amp_mean, 2),
        "wobble": round(wobble, 2),
    })


# ---------- the web server ----------
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass    # keep the terminal quiet

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            page = open(os.path.join(HERE, "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.stream_events()

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global running

        if self.path == "/start":
            with lock:
                if running:
                    reply = {"ok": False, "msg": "A run is already going."}
                else:
                    running = True
                    events.clear()
                    reply = {"ok": True}
            if reply["ok"]:
                threading.Thread(target=run_test, daemon=True).start()

            body = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def stream_events(self):
        # send every event to the page as it appears
        sent = 0
        try:
            while True:
                with lock:
                    new = events[sent:]
                    # if a new run cleared the list, start over
                    if len(events) < sent:
                        sent = 0
                        new = list(events)
                for event in new:
                    self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
                sent += len(new)
                self.wfile.flush()
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("Open http://localhost:" + str(PORT) + " in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
