"""
cinematic_grader.py — warm devotional colour grade for Panchangam video.

Pipeline (applied in order)
---------------------------
1. Warm tone     push R up, G up slightly, B down → amber/golden-hour feel
2. S-curve       mild contrast boost without crushing blacks
3. Saturation    boost colour richness (Luma-weighted desaturation inverse)
4. Vignette      radial darkness at edges, keeps eyes on the subject

Performance
-----------
All operations are NumPy-vectorised (O(W×H) per frame).
The vignette mask is computed once and cached per frame size.

Usage
-----
    grader = CinematicGrader()          # create once
    frame  = grader.grade(frame)        # call per frame
"""

import math
import numpy as np
from PIL import Image


class CinematicGrader:
    """
    Parameters (all 0–1 unless noted)
    ----------
    warmth     : amber push strength           (default 0.20)
    contrast   : S-curve contrast strength     (default 0.15)
    saturation : colour saturation multiplier  (default 1.10)
    vignette   : edge darkness 0=none 1=heavy  (default 0.32)
    """

    def __init__(
        self,
        warmth:     float = 0.20,
        contrast:   float = 0.15,
        saturation: float = 1.10,
        vignette:   float = 0.32,
    ):
        self._w  = warmth
        self._c  = contrast
        self._s  = saturation
        self._v  = vignette
        self._vig_cache: dict = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def grade(self, img: Image.Image) -> Image.Image:
        """Apply full grade; returns a new PIL image in the same mode."""
        mode = img.mode
        arr  = np.array(img, dtype=np.float32)

        # ── 1. Warm tone ──────────────────────────────────────────────────────
        arr[:, :, 0] = np.clip(arr[:, :, 0] + 255 * self._w * 0.10, 0, 255)  # R +
        arr[:, :, 1] = np.clip(arr[:, :, 1] + 255 * self._w * 0.04, 0, 255)  # G +tiny
        arr[:, :, 2] = np.clip(arr[:, :, 2] - 255 * self._w * 0.07, 0, 255)  # B -

        # ── 2. S-curve contrast ───────────────────────────────────────────────
        # f(x) = x + c·sin(π·x)·(1/π)  — symmetric lift with natural roll-off
        rgb = arr[:, :, :3]
        t   = rgb / 255.0
        arr[:, :, :3] = np.clip(
            (t + self._c * np.sin(math.pi * t) / math.pi) * 255, 0, 255
        )

        # ── 3. Saturation (luma-weighted) ──────────────────────────────────────
        r3, g3, b3 = arr[:, :, 0:1], arr[:, :, 1:2], arr[:, :, 2:3]
        luma = 0.299 * r3 + 0.587 * g3 + 0.114 * b3
        arr[:, :, :3] = np.clip(luma + (arr[:, :, :3] - luma) * self._s, 0, 255)

        # ── 4. Vignette ────────────────────────────────────────────────────────
        arr[:, :, :3] *= self._get_vignette(img.size)
        arr[:, :, :3]  = np.clip(arr[:, :, :3], 0, 255)

        return Image.fromarray(arr.astype(np.uint8), mode)

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_vignette(self, size: tuple) -> np.ndarray:
        """Return cached (H, W, 1) float32 mask in [0, 1]."""
        if size not in self._vig_cache:
            W, H = size
            xs = np.linspace(-1.0,  1.0, W, dtype=np.float32)[np.newaxis, :]
            ys = np.linspace(-1.0,  1.0, H, dtype=np.float32)[:, np.newaxis]
            dist = np.sqrt(xs ** 2 + ys ** 2) / math.sqrt(2.0)
            mask = np.clip(1.0 - self._v * dist ** 1.7, 0.0, 1.0)
            self._vig_cache[size] = mask[:, :, np.newaxis]
        return self._vig_cache[size]
