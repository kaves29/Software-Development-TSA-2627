"""Probe the mismatch between physical head motion and AMI communication labels."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pose_directory", type=Path)
parser.add_argument("annotations", type=Path)
args = parser.parse_args()
speakers = ("ES2008a.A", "IS1008a.D")
data = {}
for speaker in speakers:
    a = json.loads((args.pose_directory / f"{speaker}.pose.json").read_text())
    with ZipFile(args.annotations) as z:
        root = ET.fromstring(z.read(f"headGesture/{speaker}.head.xml"))
    intervals = [
        (float(x.get("starttime")), float(x.get("endtime")), x.get("type"))
        for x in root
    ]
    features = []
    labels = []
    misses = 0
    prev = None
    for item in a["pose_timeline"]:
        t = item["time_s"]
        kind = next((k for l, r, k in intervals if l <= t < r), None)
        if kind in (None, "off_camera"):
            prev = None
            continue
        points = item["landmarks"]
        if points is None or min(points[i]["visibility"] for i in (0, 11, 12)) < 0.65:
            features.append(-1)
            labels.append(kind != "no_comm_head")
            prev = None
            continue
        xyz = np.array([[p["x"], p["y"]] for p in points])
        shoulder = (xyz[11] + xyz[12]) / 2
        scale = np.linalg.norm(xyz[11] - xyz[12])
        if scale < 0.05:
            features.append(-1)
            labels.append(kind != "no_comm_head")
            prev = None
            continue
        head = (xyz[0] - shoulder) / scale
        if prev is None:
            features.append(-1)
        else:
            features.append(np.linalg.norm(head - prev) * 5)
        labels.append(kind != "no_comm_head")
        prev = head
    data[speaker] = (np.array(features), np.array(labels))
for source, target in (speakers, speakers[::-1]):
    x, y = data[source]
    options = [0.02, 0.05, 0.1, 0.2, 0.4, 0.8, 1.2]
    best = max(
        options,
        key=lambda v: precision_recall_fscore_support(
            y, x >= v, average="binary", zero_division=0
        )[2],
    )
    x, y = data[target]
    print(
        source,
        "selected",
        best,
        "test",
        target,
        "frames",
        len(y),
        "unavailable",
        int((x < 0).sum()),
        "positives",
        int(y.sum()),
        "precision_recall_f1",
        precision_recall_fscore_support(
            y, x >= best, average="binary", zero_division=0
        )[:3],
    )
