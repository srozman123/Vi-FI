# Wi-Fi Breathing Monitor: Hackathon Plan

## Goal
Two ESP32s measure **one seated person's breathing rate** using Wi-Fi signals (CSI), and we compare it to a **manually counted** breathing rate.

This is the proof of concept for the bigger vision: contactless vital-sign monitoring for patients waiting in ER triage.

---

## Hardware
- 2× ESP32 dev boards (original ESP32, CP2102 USB chip, built-in PCB antenna)
- 2× **data** USB-C cables (some cables only charge)
- Tape (to fix the boards in place and label them)
- Optional: aluminum foil and cardboard for simple reflectors
- Optional: a power bank or phone charger for the sender

Label the boards with tape: **SENDER** and **RECEIVER**.

## Software (Mac)
- Arduino IDE, with "esp32 by Espressif Systems" installed from the Boards Manager
  - If it isn't listed, add this to Settings → Additional boards manager URLs: `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
- Board setting: **Tools → Board → esp32 → ESP32 Dev Module**
- Port: `/dev/cu.usbserial-…` or `/dev/cu.SLAB_USBtoUART` (if missing, try another cable, then install the Silicon Labs CP210x driver)
- Optional: `brew install arduino-cli` so Claude Code can compile and upload from the terminal
- Python 3 with: `numpy scipy matplotlib pyserial`

## Folder structure
```
wifi-breathing/
  PLAN.md
  sender/      sender.ino      (ESP32 that transmits packets)
  receiver/    receiver.ino    (ESP32 that captures CSI and sends it over USB)
  analysis/    Python for breathing rate and the dashboard
  data/        recorded sessions (CSV) and the results table
```
In Arduino, every sketch is a folder that contains a `.ino` file with the same name.

---

## How it works (one-paragraph version)
The sender broadcasts about 100 small packets per second on a fixed Wi-Fi channel. Each packet starts with a known pattern (the preamble), so the receiver can measure how the room distorted it. That measurement is the **Channel State Information (CSI)**: amplitude and phase across about 64 subcarriers. When a person sits between the boards, their chest rising and falling slightly changes the CSI in a slow rhythm. We keep only slow changes (0.1–0.5 Hz, roughly 6–30 breaths/min), find the strongest rhythm, and multiply its frequency by 60 to get **breaths per minute**.

---

## Phase 0: Tests with only one ESP32
Do these while waiting for the second board. Each one teaches a piece you'll need later. Tests 1–3 use only built-in tools; Test 4 is a short custom sketch.

**Trick:** a **phone hotspot or your router can stand in for the sender board.** The ESP32 connects to it and measures the signal coming from it. On an iPhone, turn on **Personal Hotspot → Maximize Compatibility** so it uses 2.4 GHz.

### Test 1: Channel scan (5 min)
- Upload **Examples → WiFi → WiFiScan**, and open Serial Monitor at 115200.
- Record which channels nearby networks use, and their signal strength (RSSI, in dBm; closer to 0 is stronger).
- **Learn:** how crowded each channel is → choose your channel.

### Test 2: Signal strength (RSSI) vs. distance (20 min)
- Connect the ESP32 to your hotspot or router, and print its signal strength several times per second.
- Open **Tools → Serial Plotter** to watch it as a live graph.
- Move the phone/router away in steps (0.5 m, 1 m, 2 m, 4 m), and note the RSSI at each distance.
- **Learn:** signal strength drops with distance, and the reading is noisy even when nothing moves.

### Test 3: Does the body affect the signal? (20 min)
Same setup as Test 2, with the phone about 1–2 m from the ESP32.
- [ ] Nothing between them for 30 s (baseline)
- [ ] Hand over the ESP32's antenna (the zigzag at the top)
- [ ] A person standing between them
- [ ] A person walking back and forth between them
- [ ] A person sitting still between them, breathing deeply
- **Learn:** blocking and movement show clearly in RSSI. Breathing barely shows, which is why we need **CSI**, not RSSI.

### Test 4: First CSI from a single board (1–2 hrs, the important one)
- The ESP32 connects to the hotspot/router and sends it many small pings per second (about 50–100). Each reply carries CSI that the ESP32 can capture.
- Print the CSI amplitudes over USB, and watch them in Serial Plotter or save them for Python.
- Repeat the Test 3 conditions, and compare CSI with RSSI.
- **Learn:** CSI captures much more detail than RSSI. Deep, slow breathing may already show up as a slow wave.
- Note: this is how Espressif's `csi_recv_router` example works (router as the sender). With two boards, the second ESP32 replaces the phone/router, which gives you more control over channel and packet rate.

### Test 5: Movement detector (optional, 30 min)
- Using RSSI (Test 2) or CSI (Test 4), measure how much the signal varies over the last 2 seconds.
- Low variation = "still/empty," high = "movement." Set a threshold and print the result.
- **Learn:** this is the "moving, hold still" state you'll need on the dashboard, and an easy early demo.

**Phase 0 checkpoint:** you've seen the body change the signal in real numbers, and you know why RSSI isn't enough for breathing.

---

## Timeline (24 hours)

### Hours 0–2: Setup
- [ ] Install the ESP32 board package in Arduino IDE
- [ ] Upload **File → Examples → WiFi → WiFiScan** to each board (hold **IO0** if the upload stalls on "Connecting…")
- [ ] Serial Monitor at **115200** shows nearby networks and their channels
- [ ] Choose the quietest of channels **1, 6, or 11**: ________
- [ ] Python packages installed

**Checkpoint:** both boards upload successfully, and a channel is chosen.

### Hours 2–6: Get CSI flowing
- [ ] Sender: broadcasts about 100 packets/s on the chosen channel, at an 802.11n rate (the default 1 Mbps rate produces no CSI)
- [ ] Receiver: captures CSI only from the sender (filter by the sender's MAC address) and prints it over USB
- [ ] Both boards use the **same channel**

**Checkpoint:** a steady stream of CSI lines, about 100 per second. Do not move on until this works.

### Hours 6–10: First breathing signal
- [ ] Boards about **1–1.5 m apart**, at chest height, taped down, with antennas facing each other
- [ ] Person sits still between them, without talking
- [ ] Python: read CSI → resample → filter 0.1–0.5 Hz → combine subcarriers → FFT → breaths/min
- [ ] Live plot of the breathing wave

**Checkpoint:** the wave rises and falls with breathing and goes flat when the person holds their breath.

### Hours 10–14: Prove it (validation)
- [ ] 4–5 people, 2-minute sessions each
- [ ] Three conditions per person: **normal**, **fast**, and **slow** breathing
- [ ] A teammate counts the real breaths for 60 seconds
- [ ] Save each session as a CSV in `data/`
- [ ] Fill in the results table (below)

**Checkpoint:** the results table is filled in. This is the strongest slide.

### Hours 14–16: Sleep

### Hours 16–20: Dashboard and story
- [ ] Patient card showing breathing rate, a live wave, and a status color
  - Green: 12–20 breaths/min
  - Yellow: 10–12 or 20–24
  - Red: under 10 or over 24
- [ ] "Moving, hold still" state (movement ruins the reading)
- [ ] Mock triage list that ranks patients by how abnormal their readings are

### Hours 20–24: Pitch and backup
- [ ] **Record a demo video** in case the live demo fails (venue Wi-Fi and crowds can break it)
- [ ] Slides: problem → how it works → live demo → results table → roadmap
- [ ] Rehearse at least twice

---

## Results table
| Person | Condition | Counted (breaths/min) | Wi-Fi (breaths/min) | Error |
|---|---|---|---|---|
| 1 | Normal | | | |
| 1 | Fast | | | |
| 1 | Slow | | | |
| 2 | Normal | | | |
| … | | | | |

**Summary:** average error = ____ breaths/min

---

## Tips that save hours
- **Same channel on both boards**, chosen from 1, 6, or 11, whichever is least crowded.
- **Don't touch or move the boards** after setup. Tape them down.
- **Control the space:** demo in a corner, and use teammates as a buffer so nobody walks by.
- **Lower the sender's transmit power** and keep the boards close, so distant movement matters less.
- **Foil reflector** behind each board (a few cm back, slightly curved) sends more signal toward the person.
- **Use 20 MHz channel width**, not 40 MHz.
- **The subject stays quiet and still.** Talking moves the chest.
- **Avoid microwaves and many Bluetooth devices** (both use 2.4 GHz).
- Sound does **not** interfere with Wi-Fi, but vibration from loud speakers can shake the boards.
- The sender only needs power. A phone charger or power bank works.

## Known limits (be honest in the pitch)
- Works for **one still, seated person** in a controlled spot.
- **Heart rate** over Wi-Fi with these boards is unreliable, so present it as future work.
- Movement and nearby people disrupt the reading.
- Respiratory rate is still a strong place to start: it's one of the most important early warning signs in triage.

## Pitch roadmap
1. **Today:** one chair, with two ESP32s reading breathing over Wi-Fi.
2. **Next:** a sensor pair on every waiting-room chair, feeding one triage dashboard.
3. **Then:** add mmWave radar for heart rate and crowded rooms.
4. **Vision:** whole-room, contactless monitoring that flags who needs care first.
