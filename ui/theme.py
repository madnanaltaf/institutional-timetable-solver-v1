"""
UI Theme, Color Tokens, and Visual Styling Helpers
"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Modern theme constants
APP_THEME = "cosmo"  # Clean, modern, high-contrast flat theme

# Brand Colors
NAV_BG = "#0F172A"       # Deep slate sidebar
NAV_HOVER = "#1E293B"    # Dark slate hover
NAV_ACTIVE = "#2563EB"   # Vivid blue active
CARD_BG = "#FFFFFF"
BORDER_COLOR = "#E2E8F0"
TEXT_PRIMARY = "#0F172A"
TEXT_MUTED = "#64748B"
ACCENT_BLUE = "#2563EB"
ACCENT_GREEN = "#10B981"
ACCENT_AMBER = "#F59E0B"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_RED = "#EF4444"

# Card border / padding helper
CARD_PAD = 12

def get_subject_badge_style(hex_color: str) -> str:
    """Returns suitable text color for background contrast."""
    if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7:
        return "#FFFFFF"
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.65 else "#FFFFFF"
