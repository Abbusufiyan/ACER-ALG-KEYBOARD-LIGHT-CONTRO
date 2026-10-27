"""
Color definitions, conversions, and nearest-preset matching for Acer ALG RGB.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import math

@dataclass(frozen=True)
class AlgColor:
    name: str
    r: int
    g: int
    b: int
    label: str
    hex_code: str

    @property
    def rgb_tuple(self) -> Tuple[int, int, int]:
        return (self.r, self.g, self.b)


# Calibrated firmware colors matching kernel/alg_rgb.c
SUPPORTED_COLORS: List[AlgColor] = [
    AlgColor("red",          0xFF, 0x00, 0x00, "Red",          "#FF0000"),
    AlgColor("orange",       0xFF, 0x7F, 0x00, "Orange",       "#FF7F00"),
    AlgColor("yellow",       0xFF, 0xFF, 0x00, "Yellow",       "#FFFF00"),
    AlgColor("lime",         0x7F, 0xFF, 0x00, "Lime",         "#7FFF00"),
    AlgColor("light-green",  0x3F, 0xFF, 0x00, "Light Green",  "#3FFF00"),
    AlgColor("green",        0x00, 0xFF, 0x00, "Green",        "#00FF00"),
    AlgColor("green-cyan",   0x00, 0xFF, 0x46, "Green Cyan",   "#00FF46"),
    AlgColor("cyan",         0x00, 0xFF, 0xC8, "Cyan",         "#00FFC8"),
    AlgColor("light-blue",   0x00, 0x7F, 0xC8, "Light Blue",   "#007FC8"),
    AlgColor("blue",         0x00, 0x00, 0xC8, "Blue",         "#0000C8"),
    AlgColor("violet",       0x7F, 0x00, 0xC8, "Violet",       "#7F00C8"),
    AlgColor("magenta",      0xFF, 0x00, 0xC8, "Magenta",      "#FF00C8"),
    AlgColor("pink",         0xFF, 0x00, 0x7F, "Pink",         "#FF007F"),
    AlgColor("flesh",        0xFF, 0x7F, 0x3F, "Flesh",        "#FF7F3F"),
    AlgColor("bluish-white", 0x3F, 0x7F, 0x7F, "Bluish White", "#3F7F7F"),
    AlgColor("white",        0xFF, 0xFF, 0xFF, "White",        "#FFFFFF"),
]

COLOR_OFF = AlgColor("off", 0x00, 0x00, 0x00, "Off", "#000000")

COLOR_BY_NAME = {c.name: c for c in SUPPORTED_COLORS}
COLOR_BY_NAME["off"] = COLOR_OFF


def get_color(name: str) -> Optional[AlgColor]:
    """Retrieve AlgColor by command name (case-insensitive)."""
    return COLOR_BY_NAME.get(name.strip().lower())


def hex_to_rgb(hex_str: str) -> Optional[Tuple[int, int, int]]:
    """Parse a hex color string like #RRGGBB or RRGGBB into (r, g, b)."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join([c * 2 for c in s])
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (r, g, b)
    except ValueError:
        return None


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Format RGB components to uppercase hex string #RRGGBB."""
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def find_nearest_preset(r: int, g: int, b: int) -> AlgColor:
    """
    Find the closest supported firmware color preset using weighted Euclidean distance
    accounting for human eye luminance perception.
    """
    best_color = SUPPORTED_COLORS[0]
    best_dist = float("inf")

    # Weighted Euclidean distance: 30% R, 59% G, 11% B
    for c in SUPPORTED_COLORS:
        dr = r - c.r
        dg = g - c.g
        db = b - c.b
        # Redmean color approximation for perceptual accuracy
        r_mean = (r + c.r) / 2
        dist_sq = (2 + r_mean / 256) * (dr ** 2) + 4.0 * (dg ** 2) + (2 + (255 - r_mean) / 256) * (db ** 2)
        if dist_sq < best_dist:
            best_dist = dist_sq
            best_color = c

    return best_color
