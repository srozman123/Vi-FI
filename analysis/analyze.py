# analyze.py
# Looks at one recording and checks if something changed in the middle.
# It tracks TWO things: RSSI (one number per packet) and CSI (128 numbers per packet).
#
# Run it like this:
#   .venv/bin/python analysis/analyze.py                  (newest file in data/)
#   .venv/bin/python analysis/analyze.py data/some.csv    (a specific file)

import csv
import glob
import os
import sys
import statistics as st

BEFORE_END = 12     # seconds 0 to 12 = "before" (the baseline)
AFTER_START = 18    # seconds 18 and later = "after"

# ---------- load the file ----------
if len(sys.argv) > 1:
    path = sys.argv[1]
else:
    folder = os.path.join(os.path.dirname(__file__), "..", "data")
    path = max(glob.glob(os.path.join(folder, "*.csv")), key=os.path.getmtime)

rows = list(csv.reader(open(path)))
data = rows[1:]
n = len(data)

time_us = [int(r[2]) for r in data]
rssi = [int(r[3]) for r in data]
csi = [[float(x) for x in r[4:]] for r in data]
t = [(x - time_us[0]) / 1000000 for x in time_us]    # seconds from the receiver clock

print("File:", os.path.basename(path))
print("Packets:", n, " Length:", round(t[-1], 1), "s  Rate:", round(n / t[-1], 1), "per second")

# subcarriers that are actually used (the others are always near 0)
num_sc = len(csi[0])
alive = []
for i in range(num_sc):
    if st.mean(p[i] for p in csi) > 3:
        alive.append(i)
print("Subcarriers in use:", len(alive), "of", num_sc)

# which packets are before and after
before = [k for k in range(n) if t[k] < BEFORE_END]
after = [k for k in range(n) if t[k] >= AFTER_START]

# ---------- baseline for each subcarrier ----------
base_mean = {}
base_sd = {}
for i in alive:
    values = [csi[k][i] for k in before]
    base_mean[i] = st.mean(values)
    base_sd[i] = max(st.pstdev(values), 0.5)     # floor so we never divide by ~0

# ---------- per second table ----------
print()
print("sec  pkts | RSSI mean  sd  | CSI mean-amp  CSI-shift  CSI-wobble")
print("                                (avg level)  (vs baseline) (spread)")
for sec in range(int(t[-1]) + 1):
    idx = [k for k in range(n) if sec <= t[k] < sec + 1]
    if len(idx) == 0:
        continue
    r = [rssi[k] for k in idx]

    # CSI level: average amplitude over the subcarriers in use
    level = st.mean(st.mean(csi[k][i] for i in alive) for k in idx)

    # CSI shift: how far each subcarrier's average moved from its baseline,
    # in "standard deviations", averaged over subcarriers
    shift = st.mean(abs(st.mean(csi[k][i] for k in idx) - base_mean[i]) / base_sd[i] for i in alive)

    # CSI wobble: how much each subcarrier jumps around inside this second
    wobble = st.mean(st.pstdev([csi[k][i] for k in idx]) for i in alive)

    print(f"{sec:3d}  {len(idx):4d} | {st.mean(r):7.1f}  {st.pstdev(r):4.2f} |"
          f" {level:9.2f}   {shift:9.2f}   {wobble:9.2f}")

# ---------- before vs after summary ----------
print()
print("BEFORE (0 to", BEFORE_END, "s)  vs  AFTER (", AFTER_START, "s on)")

rb = [rssi[k] for k in before]
ra = [rssi[k] for k in after]
rssi_drop = st.mean(ra) - st.mean(rb)
rssi_noise = max(st.pstdev(rb), 0.3)
print(f"RSSI : {st.mean(rb):.1f} dBm -> {st.mean(ra):.1f} dBm   change = {rssi_drop:+.1f} dB"
      f"   ({abs(rssi_drop) / rssi_noise:.1f}x the baseline noise)")
print(f"RSSI spread: {st.pstdev(rb):.2f} -> {st.pstdev(ra):.2f}")

lb = st.mean(st.mean(csi[k][i] for i in alive) for k in before)
la = st.mean(st.mean(csi[k][i] for i in alive) for k in after)
print(f"CSI average amplitude: {lb:.2f} -> {la:.2f}   change = {la - lb:+.2f} ({(la - lb) / lb * 100:+.1f}%)")

# per subcarrier change, in standard deviations
changes = []
for i in alive:
    mb = base_mean[i]
    ma = st.mean(csi[k][i] for k in after)
    z = (ma - mb) / base_sd[i]
    changes.append((abs(z), i, mb, ma))
changes.sort(reverse=True)

median_z = st.median(c[0] for c in changes)
big = sum(1 for c in changes if c[0] > 2)
print(f"CSI per-subcarrier change: median = {median_z:.2f} sd,"
      f" {big} of {len(alive)} subcarriers moved more than 2 sd")
print("Biggest movers (subcarrier: before -> after):")
for z, i, mb, ma in changes[:6]:
    print(f"   sc{i:3d}: {mb:6.1f} -> {ma:6.1f}   ({z:.1f} sd)")

# ---------- simple verdict ----------
print()
rssi_ratio = abs(rssi_drop) / rssi_noise
print("RSSI verdict:", "CLEAR change" if rssi_ratio > 3 else "small / unclear", f"({rssi_ratio:.1f}x noise)")
print("CSI  verdict:", "CLEAR change" if median_z > 2 else "small / unclear", f"(median {median_z:.1f} sd)")
