"""
presenter_animator.py

Brings the static pandit_character.png to life with:
  - Natural body bob + breathing + gentle sway
  - Simulated talking (body lean + sound-wave rings + hand glow pulse)
  - Scene-aware tint (calm / warning-red / auspicious-gold / closing)
  - Temple arch background generator
  - Marigold petal particle system
  - Subtitle text renderer
  - Blink simulation (irregular natural blink cadence)
  - Rim light (cinematic side fill on character)

Usage:
    from presenter_animator import PresenterAnimator, make_temple_bg, draw_subtitle

    anim = PresenterAnimator(char_path)
    bg   = make_temple_bg(W, H)
    frame = bg.copy()
    frame = anim.composite(frame, t=t, talking=True, scene=0)
    frame = draw_subtitle(frame, "నమస్కారం!", t)
"""

import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops


# ── Blink schedule (module-level, shared across all instances) ────────────────

def _make_blink_times(seed: int = 17, span: float = 120.0) -> list[float]:
    """Pre-compute irregular blink timestamps over *span* seconds (loops)."""
    rng, ts, t = random.Random(seed), [], 0.8
    while t < span:
        t += rng.uniform(2.6, 5.4)
        ts.append(t)
    return ts

_BLINK_TIMES: list[float] = _make_blink_times()


def _blink_alpha(t: float, blink_dur: float = 0.10) -> float:
    """
    Return blink intensity in [0, 1] at time *t*.
    0 = eyes fully open, 1 = eyes fully closed.
    Uses a triangle envelope over *blink_dur* seconds.
    """
    t_mod = t % 120.0
    for bt in _BLINK_TIMES:
        dt = t_mod - bt
        if 0.0 <= dt < blink_dur:
            return 1.0 - abs(2.0 * dt / blink_dur - 1.0)
    return 0.0

# ── Colour palette ────────────────────────────────────────────────────────────
GOLD        = (255, 215,   0)
SAFFRON     = (255, 120,   0)
WARN_RED    = (220,  40,  40)
CREAM       = (255, 228, 181)
WHITE       = (255, 248, 240)
DARK_STONE  = ( 90,  70,  50)
WARM_LIGHT  = (255, 200, 120)
MARIGOLD    = (255, 140,   0)

# ── Scene tints applied to the character ─────────────────────────────────────
SCENE_TINTS = {
    0: None,                           # intro  — natural
    1: (230, 30,  30),                 # bad    — red
    2: (255, 200,  60),                # good   — gold
    3: None,                           # close  — natural
}

FPS = 24

# ─────────────────────────────────────────────────────────────────────────────
# Background: warm temple arch scene
# ─────────────────────────────────────────────────────────────────────────────

def make_temple_bg(W: int, H: int) -> Image.Image:
    """Generate a warm Hindu-temple-style background (no external images needed)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # ── Sky gradient (warm golden hour) ──────────────────────────────────────
    sky_h = int(H * 0.52)
    for y in range(sky_h):
        t = y / sky_h
        r = int(255 - 30 * t)
        g = int(230 - 80 * t)
        b = int(170 - 120 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Ground / floor (stone) ────────────────────────────────────────────────
    for y in range(sky_h, H):
        t = (y - sky_h) / (H - sky_h)
        r = int(140 + 30 * t)
        g = int(115 + 20 * t)
        b = int(85 + 15 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Stone floor lines ─────────────────────────────────────────────────────
    for row in range(6):
        fy = sky_h + int((H - sky_h) * (row / 6))
        draw.line([(0, fy), (W, fy)], fill=(110, 88, 65, 90), width=2)
    for col in range(8):
        cx = int(W * col / 7)
        draw.line([(cx, sky_h), (cx, H)], fill=(110, 88, 65, 60), width=1)

    # ── Back-wall arch ────────────────────────────────────────────────────────
    arch_cx    = W // 2
    arch_base  = int(H * 0.54)
    arch_w     = int(W * 0.52)
    arch_top   = int(H * 0.04)
    arch_h     = arch_base - arch_top

    # Fill arch interior with bright sky glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([arch_cx - arch_w // 2, arch_top,
                arch_cx + arch_w // 2, arch_top + arch_h * 2],
               fill=(255, 245, 210, 220))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img  = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Arch border (stone)
    for i in range(3):
        aw = arch_w - i * 12
        draw.arc([arch_cx - aw // 2, arch_top + i * 8,
                  arch_cx + aw // 2, arch_top + arch_h * 2 + i * 8],
                 start=180, end=360,
                 fill=(160, 130, 95, 200 - i * 40), width=14 - i * 4)

    # ── Side columns ─────────────────────────────────────────────────────────
    col_w = int(W * 0.09)
    col_positions = [
        int(W * 0.08), int(W * 0.20),     # left two
        int(W * 0.72), int(W * 0.84),     # right two
    ]
    col_top    = int(H * 0.05)
    col_bottom = int(H * 0.60)
    for cx2 in col_positions:
        # Column shaft
        cw2 = col_w if cx2 < W // 2 else int(col_w * 0.75)   # perspective
        for shade_y in range(col_top, col_bottom):
            t2 = (shade_y - col_top) / (col_bottom - col_top)
            r2 = int(175 - 25 * t2)
            g2 = int(148 - 22 * t2)
            b2 = int(112 - 18 * t2)
            draw.line([(cx2 - cw2 // 2, shade_y), (cx2 + cw2 // 2, shade_y)],
                      fill=(r2, g2, b2, 220))
        # Capital
        draw.rectangle([cx2 - cw2 // 2 - 6, col_top,
                        cx2 + cw2 // 2 + 6, col_top + 20],
                       fill=(190, 160, 120, 230))
        # Carved rings on column
        for ring_y in range(col_top + 30, col_bottom, 80):
            draw.ellipse([cx2 - cw2 // 2 - 3, ring_y - 5,
                          cx2 + cw2 // 2 + 3, ring_y + 5],
                         outline=(140, 112, 82, 160), width=2)

    # ── Marigold garlands ─────────────────────────────────────────────────────
    _draw_garland(draw, W, H,
                  start=(int(W * 0.05), int(H * 0.25)),
                  end=(int(W * 0.48), int(H * 0.50)),
                  sag=0.22)
    _draw_garland(draw, W, H,
                  start=(int(W * 0.52), int(H * 0.50)),
                  end=(int(W * 0.95), int(H * 0.25)),
                  sag=0.22)

    # ── Fallen petals on ground ───────────────────────────────────────────────
    rng = random.Random(42)
    for _ in range(120):
        px = rng.randint(0, W)
        py = rng.randint(sky_h + 10, H - 30)
        r2 = rng.randint(3, 8)
        a  = rng.randint(100, 200)
        draw.ellipse([px - r2, py - r2 // 2, px + r2, py + r2 // 2],
                     fill=(MARIGOLD[0], MARIGOLD[1], MARIGOLD[2], a))

    # ── Sun / bright halo behind arch ────────────────────────────────────────
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd   = ImageDraw.Draw(halo)
    for rad in range(180, 0, -12):
        a2 = int(38 * (1 - rad / 180) ** 1.8)
        hd.ellipse([arch_cx - rad, arch_top + 40 - rad,
                    arch_cx + rad, arch_top + 40 + rad],
                   fill=(255, 230, 140, a2))
    halo = halo.filter(ImageFilter.GaussianBlur(28))
    img  = Image.alpha_composite(img, halo)

    return img


def _draw_garland(draw, W, H, start, end, sag=0.20, segments=60):
    """Draw a catenary-ish marigold garland."""
    sx, sy = start
    ex, ey = end
    mid_y  = max(sy, ey) + int(abs(ex - sx) * sag)
    pts    = []
    for i in range(segments + 1):
        u  = i / segments
        x  = int(sx + (ex - sx) * u)
        # quadratic bezier y
        bm = (sx + ex) // 2, mid_y
        y  = int((1 - u) ** 2 * sy + 2 * (1 - u) * u * bm[1] + u ** 2 * ey)
        pts.append((x, y))
    # Draw thick green stem
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=(60, 120, 40, 200), width=5)
    # Draw marigold blossoms along garland
    for i in range(0, len(pts), 4):
        cx2, cy2 = pts[i]
        for petal in range(8):
            ang  = petal * math.pi / 4
            dx   = int(9 * math.cos(ang))
            dy   = int(9 * math.sin(ang))
            draw.ellipse([cx2 + dx - 5, cy2 + dy - 5,
                          cx2 + dx + 5, cy2 + dy + 5],
                         fill=(MARIGOLD[0], MARIGOLD[1], MARIGOLD[2], 220))
        draw.ellipse([cx2 - 5, cy2 - 5, cx2 + 5, cy2 + 5],
                     fill=(255, 200, 0, 240))


# ─────────────────────────────────────────────────────────────────────────────
# Particle system: drifting marigold petals
# ─────────────────────────────────────────────────────────────────────────────

class PetalParticles:
    def __init__(self, W: int, H: int, count: int = 18, seed: int = 7):
        rng    = random.Random(seed)
        self.W = W
        self.H = H
        self.petals = [
            {
                "x":     rng.uniform(0, W),
                "y":     rng.uniform(-H * 0.3, H * 0.8),
                "vx":    rng.uniform(-18, 18),
                "vy":    rng.uniform(20, 50),
                "r":     rng.randint(5, 13),
                "phase": rng.uniform(0, 2 * math.pi),
                "alpha": rng.randint(130, 210),
            }
            for _ in range(count)
        ]

    def draw(self, img: Image.Image, t: float) -> Image.Image:
        ov   = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(ov)
        for p in self.petals:
            wobble = 28 * math.sin(p["phase"] + t * 1.8)
            x = (p["x"] + p["vx"] * t + wobble) % self.W
            y = (p["y"] + p["vy"] * t) % (self.H * 1.1)
            r = p["r"]
            draw.ellipse([x - r, y - r // 2, x + r, y + r // 2],
                         fill=(MARIGOLD[0], MARIGOLD[1], MARIGOLD[2], p["alpha"]))
        return Image.alpha_composite(img, ov)


# ─────────────────────────────────────────────────────────────────────────────
# Character background-removal (same logic as original video_creator.py)
# ─────────────────────────────────────────────────────────────────────────────

_char_cache: Image.Image | None = None


def load_character(path: str) -> Image.Image | None:
    global _char_cache
    if _char_cache is not None:
        return _char_cache
    if not os.path.exists(path):
        return None
    try:
        from scipy import ndimage
    except ImportError:
        img = Image.open(path).convert("RGBA")
        _char_cache = img
        return _char_cache

    orig = Image.open(path).convert("RGBA")
    arr  = np.array(orig)
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    sat    = np.max([r, g, b], axis=0) - np.min([r, g, b], axis=0)
    bright = (r + g + b) // 3
    is_bg  = ((r < 30) & (g < 30) & (b < 30)) | ((sat < 30) & (bright > 200))
    labeled, _ = ndimage.label(is_bg)
    bl = set()
    for la in [labeled[0, :], labeled[-1, :], labeled[:, 0], labeled[:, -1]]:
        bl.update(la[la > 0])
    mask   = np.zeros(is_bg.shape, dtype=bool)
    for lbl in bl:
        mask |= (labeled == lbl)
    result = arr.copy()
    result[mask, 3] = 0
    _char_cache = Image.fromarray(result, "RGBA")
    return _char_cache


# ─────────────────────────────────────────────────────────────────────────────
# Sound-wave rings (talking indicator)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_sound_waves(img: Image.Image, mouth_x: int, mouth_y: int, t: float,
                      n_rings: int = 3, base_alpha: int = 180) -> Image.Image:
    ov   = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    for i in range(n_rings):
        phase  = (t * 2.5 + i * 0.38) % 1.0
        radius = int(18 + phase * 55)
        alpha  = int(base_alpha * (1.0 - phase) ** 1.6)
        col    = (255, 215, 80, alpha)
        draw.arc(
            [mouth_x - radius, mouth_y - radius,
             mouth_x + radius, mouth_y + radius],
            start=-70, end=70,
            fill=col, width=max(2, int(4 * (1 - phase)))
        )
    ov = ov.filter(ImageFilter.GaussianBlur(2))
    return Image.alpha_composite(img, ov)


# ─────────────────────────────────────────────────────────────────────────────
# Hand glow pulse
# ─────────────────────────────────────────────────────────────────────────────

def _draw_hand_glow(img: Image.Image, char_bbox: tuple, t: float,
                    scene: int) -> Image.Image:
    cx  = (char_bbox[0] + char_bbox[2]) // 2
    ch  = char_bbox[3] - char_bbox[1]
    # Hands are roughly at 55–70 % of character height
    hy  = char_bbox[1] + int(ch * 0.62)
    hw  = int(ch * 0.25)         # half-width of hand span

    color = GOLD if scene != 1 else (255, 80, 80)
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 1.8 * t)
    alpha = int(55 * pulse)

    ov   = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    for side, xc in [(-1, cx - hw), (1, cx + hw)]:
        r = int(28 + 12 * pulse)
        draw.ellipse([xc - r, hy - r, xc + r, hy + r],
                     fill=(color[0], color[1], color[2], alpha))
    ov = ov.filter(ImageFilter.GaussianBlur(14))
    return Image.alpha_composite(img, ov)


# ─────────────────────────────────────────────────────────────────────────────
# Shadow / ground contact
# ─────────────────────────────────────────────────────────────────────────────

def _draw_ground_shadow(img: Image.Image, cx: int, bottom_y: int,
                        char_w: int) -> Image.Image:
    ov   = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    sw   = int(char_w * 0.62)
    sh   = int(sw * 0.22)
    # Two-layer shadow: broad soft base + sharper inner
    draw.ellipse([cx - sw, bottom_y - sh, cx + sw, bottom_y + sh],
                 fill=(30, 14, 0, 55))
    draw.ellipse([cx - sw//2, bottom_y - sh//2, cx + sw//2, bottom_y + sh//2],
                 fill=(20, 8, 0, 80))
    ov = ov.filter(ImageFilter.GaussianBlur(28))
    return Image.alpha_composite(img, ov)


def _draw_rim_light(img: Image.Image, px: int, py: int,
                    nw: int, nh: int, scene: int) -> Image.Image:
    """
    Add a soft cinematic rim light on the left edge of the character.
    Colour shifts to red in scene 1 (warning).
    """
    color = (255, 200, 90) if scene != 1 else (255, 110, 60)
    ov    = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw  = ImageDraw.Draw(ov)
    rim_w = int(nw * 0.12)
    draw.ellipse(
        [px - rim_w // 2,
         py + nh // 10,
         px + rim_w,
         py + nh * 9 // 10],
        fill=(*color, 38),
    )
    ov = ov.filter(ImageFilter.GaussianBlur(24))
    return Image.alpha_composite(img, ov)


def _draw_blink(img: Image.Image, cx: int, py: int,
                nw: int, nh: int, alpha: float) -> Image.Image:
    """
    Overlay a dark ellipse over the estimated eye region to simulate a blink.
    Works with a single character PNG — no separate face layers required.
    Eye region is approximated at ~11 % from the top of the character.
    """
    if alpha < 0.02:
        return img
    ey  = py + int(nh * 0.115)       # eye row y
    ew  = int(nw * 0.38)              # horizontal span of both eyes
    eh  = max(5, int(nh * 0.042))     # half-height of eyelid strip
    ov  = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    draw.ellipse(
        [cx - ew // 2, ey - eh,
         cx + ew // 2, ey + eh],
        fill=(10, 5, 0, int(235 * alpha)),
    )
    ov = ov.filter(ImageFilter.GaussianBlur(4))
    return Image.alpha_composite(img, ov)


# ─────────────────────────────────────────────────────────────────────────────
# Main animator class
# ─────────────────────────────────────────────────────────────────────────────

class PresenterAnimator:
    """
    Manages the animated character overlay for the presenter-style video.

    Parameters
    ----------
    char_path : str  — path to pandit_character.png
    W, H      : int  — frame dimensions
    scale     : float — character height relative to H (default 0.72)
    cx        : int  — horizontal center of character (default W//2)
    bottom_y  : int  — bottom edge of character on screen (default H - 8)
    """

    def __init__(self, char_path: str, W: int, H: int,
                 scale: float = 0.72,
                 cx: int | None = None,
                 bottom_y: int | None = None):
        self.W       = W
        self.H       = H
        self.scale   = scale
        self.cx      = cx if cx is not None else W // 2
        self.bottom  = bottom_y if bottom_y is not None else H - 8
        self._path   = char_path
        self._char   = load_character(char_path)
        self.petals  = PetalParticles(W, H)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_base_char(self, scene: int) -> Image.Image:
        """Return character with optional scene tint, at display size."""
        char = self._char
        if char is None:
            return None

        # Target display height
        tgt_h = int(self.H * self.scale)
        tgt_w = int(char.size[0] * (tgt_h / char.size[1]))
        resized = char.resize((tgt_w, tgt_h), Image.LANCZOS)

        tint = SCENE_TINTS.get(scene)
        if tint:
            arr  = np.array(resized).astype(np.float32)
            amask = arr[:, :, 3] > 10
            t2   = 0.45
            arr[amask, 0] = np.clip(arr[amask, 0] * (1 - t2) + tint[0] * t2, 0, 255)
            arr[amask, 1] = np.clip(arr[amask, 1] * (1 - t2) + tint[1] * t2, 0, 255)
            arr[amask, 2] = np.clip(arr[amask, 2] * (1 - t2) + tint[2] * t2, 0, 255)
            resized = Image.fromarray(arr.astype(np.uint8), "RGBA")

        return resized

    def _animate(self, char_img: Image.Image, t: float,
                 talking: bool, scene: int) -> tuple:
        """
        Apply motion transforms to the character image.

        Returns (animated_image, (paste_x, paste_y), (char_cx, char_mouth_y), (nw, nh))
        """
        W, H = self.W, self.H

        # ── Breathing — two harmonics for more organic feel ───────────────────
        breath = (1.0
                  + 0.0055 * math.sin(2 * math.pi * 0.42 * t)
                  + 0.0020 * math.sin(2 * math.pi * 0.87 * t + 1.1))

        # ── Talking: subtle chest swell on syllable beats ─────────────────────
        if talking:
            breath *= 1.0 + 0.0035 * abs(math.sin(2 * math.pi * 3.8 * t))

        nw = int(char_img.size[0] * breath)
        nh = int(char_img.size[1] * breath)
        char_img = char_img.resize((nw, nh), Image.LANCZOS)

        # ── Gentle sway rotation (around bottom-centre) ───────────────────────
        sway_deg = (0.55 * math.sin(2 * math.pi * 0.21 * t + 0.4)
                  + 0.18 * math.sin(2 * math.pi * 0.49 * t + 2.1))
        if abs(sway_deg) > 0.04:
            char_img = char_img.rotate(
                sway_deg, resample=Image.BICUBIC,
                expand=False,
                center=(nw // 2, nh),
            )

        # ── Vertical bob ──────────────────────────────────────────────────────
        bob_y = int(3.5 * math.sin(2 * math.pi * 0.65 * t)
                  + 1.2 * math.sin(2 * math.pi * 1.30 * t + 0.7))

        # ── Horizontal micro-drift ────────────────────────────────────────────
        drift_x = int(2.2 * math.sin(2 * math.pi * 1.10 * t + 1.2))

        # ── Scene-1 shake (Rahu Kalam warning energy) ─────────────────────────
        shake_x = int(5.5 * math.sin(2 * math.pi * 6.8 * t)) if scene == 1 else 0

        px = self.cx - nw // 2 + drift_x + shake_x
        py = self.bottom - nh + bob_y

        # Screen-edge clamp
        px = max(0, min(px, W - nw))
        py = max(-nh // 4, py)

        # Estimate mouth/face positions (≈17 % from top of char bbox)
        mouth_y = py + int(nh * 0.175)
        mouth_x = self.cx + drift_x + shake_x

        return char_img, (px, py), (mouth_x, mouth_y), (nw, nh)

    # ── Public API ────────────────────────────────────────────────────────────

    def composite(
        self,
        base_img: Image.Image,
        t: float,
        talking: bool = True,
        scene: int = 0,
        petals: bool = True,
    ) -> Image.Image:
        """
        Overlay the animated presenter character onto base_img.

        Parameters
        ----------
        base_img : RGBA background image
        t        : time in seconds (monotonically increasing)
        talking  : whether the character should appear to be speaking
        scene    : 0=intro, 1=bad, 2=good, 3=closing
        petals   : whether to show drifting marigold petals
        """
        char_base = self._get_base_char(scene)
        if char_base is None:
            return base_img

        char_anim, (px, py), (mx, my), (nw, nh) = self._animate(
            char_base, t, talking, scene
        )

        result = base_img.copy()

        # ── Ground shadow (two-layer, more depth) ─────────────────────────────
        result = _draw_ground_shadow(result, self.cx, self.bottom, nw)

        # ── Rim light (cinematic left-side fill) ──────────────────────────────
        result = _draw_rim_light(result, px, py, nw, nh, scene)

        # ── Hand glow (gesture indicator) ─────────────────────────────────────
        char_bbox = (px, py, px + nw, py + nh)
        result = _draw_hand_glow(result, char_bbox, t, scene)

        # ── Paste character ───────────────────────────────────────────────────
        result.paste(char_anim, (px, py), char_anim)

        # ── Blink overlay ─────────────────────────────────────────────────────
        ba = _blink_alpha(t)
        if ba > 0.02:
            result = _draw_blink(result, self.cx, py, nw, nh, ba)

        # ── Sound-wave rings when talking ────────────────────────────────────
        if talking:
            result = _draw_sound_waves(result, mx, my, t)

        # ── Drifting petals (foreground) ──────────────────────────────────────
        if petals:
            result = self.petals.draw(result, t)

        return result


# ─────────────────────────────────────────────────────────────────────────────
# Subtitle renderer
# ─────────────────────────────────────────────────────────────────────────────

def draw_subtitle(
    img: Image.Image,
    text: str,
    t: float,
    W: int,
    H: int,
    font_fn,          # callable(size, bold) -> ImageFont
    y_ratio: float = 0.885,
    fade_in: float = 0.4,
    fade_out: float = 0.4,
    duration: float = 3.0,
    start_t: float = 0.0,
) -> Image.Image:
    """
    Render a subtitle line with fade-in / fade-out.

    font_fn : a function (size, bold=False) -> PIL ImageFont
    """
    if not text:
        return img

    elapsed = t - start_t
    if elapsed < 0 or elapsed > duration:
        return img

    # Compute alpha
    if elapsed < fade_in:
        alpha = int(255 * elapsed / fade_in)
    elif elapsed > duration - fade_out:
        alpha = int(255 * (duration - elapsed) / fade_out)
    else:
        alpha = 255

    ov   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)

    # Semi-transparent pill background
    y_c    = int(H * y_ratio)
    pad_x  = 40
    pad_y  = 14
    font   = font_fn(34, bold=False)

    # Measure text width roughly (fallback to W * 0.7 if font has no getbbox)
    try:
        bbox = font.getbbox(text)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]
    except Exception:
        tw, th = int(W * 0.7), 38

    bx1 = W // 2 - tw // 2 - pad_x
    bx2 = W // 2 + tw // 2 + pad_x
    by1 = y_c - th // 2 - pad_y
    by2 = y_c + th // 2 + pad_y

    bg_alpha = int(180 * alpha / 255)
    draw.rounded_rectangle([bx1, by1, bx2, by2],
                           radius=16,
                           fill=(20, 8, 0, bg_alpha))

    draw.text((W // 2, y_c), text, font=font,
              fill=(255, 228, 150, alpha), anchor="mm")

    return Image.alpha_composite(img, ov)
