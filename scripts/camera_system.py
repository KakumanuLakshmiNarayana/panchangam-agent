"""
camera_system.py — smooth cinematic camera motion for Panchangam video.

Presets
-------
push_in        slow zoom toward centre, very cinematic
drift          constant gentle horizontal drift
push_in_drift  push-in + sinusoidal drift  (default)
shake          faster drift for tense / warning scenes
static         no movement

Usage
-----
    cam   = CameraMotion("push_in_drift", duration=5.0)
    frame = cam.apply(frame, t_seconds)   # same size as input
"""

import math
from PIL import Image


# ── Easing ────────────────────────────────────────────────────────────────────

def _ease_in_out(t: float) -> float:
    """Cubic ease-in-out: slow start, fast middle, slow end."""
    return 3 * t * t - 2 * t * t * t


# ── Presets: (zoom_start, zoom_end, drift_amp, drift_freq_Hz, drift_phase) ────

PRESETS: dict[str, tuple] = {
    "push_in":       (1.000, 1.060,  0,   0.00, 0.0),
    "drift":         (1.030, 1.030, 16,   0.16, 0.0),
    "push_in_drift": (1.000, 1.050, 10,   0.13, 0.9),
    "shake":         (1.020, 1.025,  8,   1.30, 0.0),
    "static":        (1.000, 1.000,  0,   0.00, 0.0),
}

# Default camera preset per scene index (0=intro, 1=bad, 2=good, 3=closing)
SCENE_CAMERA_PRESETS: list[str] = [
    "push_in_drift",   # scene 0 — intro
    "shake",           # scene 1 — Rahu Kalam warning
    "push_in",         # scene 2 — auspicious timings
    "drift",           # scene 3 — closing
]


# ── Camera class ──────────────────────────────────────────────────────────────

class CameraMotion:
    """
    Apply smooth camera zoom + horizontal drift to a PIL frame.

    Parameters
    ----------
    preset   : one of the keys in PRESETS
    duration : scene duration in seconds (used to normalise zoom progress)
    """

    def __init__(self, preset: str = "push_in_drift", duration: float = 5.0):
        zs, ze, da, df, dp = PRESETS.get(preset, PRESETS["push_in_drift"])
        self._zs  = zs           # zoom at t=0
        self._ze  = ze           # zoom at t=duration
        self._da  = da           # drift amplitude (pixels at output size)
        self._df  = df           # drift frequency (Hz)
        self._dp  = dp           # drift phase offset (radians)
        self._dur = max(duration, 0.001)

    def apply(self, img: Image.Image, t: float) -> Image.Image:
        """
        Return *img* transformed for time *t* (seconds).

        The output is always the same pixel size as the input.
        """
        W, H = img.size
        norm = min(t / self._dur, 1.0)

        zoom = self._zs + (self._ze - self._zs) * _ease_in_out(norm)
        dx   = int(self._da * math.sin(2.0 * math.pi * self._df * t + self._dp))

        # Fast-path: no transform needed
        if abs(zoom - 1.0) < 0.0008 and dx == 0:
            return img

        nW, nH = int(W * zoom), int(H * zoom)
        # BILINEAR is fast enough for per-frame offline rendering
        scaled = img.resize((nW, nH), Image.BILINEAR)

        # Centre-crop back to original size, offset by drift
        cx = max(0, min((nW - W) // 2 + dx, nW - W))
        cy = max(0, min((nH - H) // 2,       nH - H))
        return scaled.crop((cx, cy, cx + W, cy + H))
