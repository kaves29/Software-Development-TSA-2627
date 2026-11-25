"""Recording-relative acoustic measurements, not loudness judgments."""

import numpy as np


def energy_variation(waveform, sample_rate, speech):
    frame = max(1, round(sample_rate * 0.1))
    levels = []
    for start, end in speech:
        audio = waveform[max(0, int(start * sample_rate)):min(len(waveform), int(end * sample_rate))]
        for offset in range(0, len(audio) - frame + 1, frame):
            rms = float(np.sqrt(np.mean(np.square(audio[offset:offset + frame], dtype=np.float64))))
            if rms > 1e-6:
                levels.append(20 * np.log10(rms))
    if len(levels) < 5:
        return None
    return round(float(np.percentile(levels, 90) - np.percentile(levels, 10)), 4)
