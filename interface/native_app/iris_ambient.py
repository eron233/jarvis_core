"""Quiet idle and hit-region policy for the Iris desktop overlay.

No screen inspection, telemetry, network, or microphone.
"""
from __future__ import annotations

import math
import time


class IdlePolicy:
    """Monotonic, easily testable decision about when Iris may rest."""

    def __init__(self, inactive_after_seconds: int = 300, now: float | None = None):
        if inactive_after_seconds < 1:
            raise ValueError("Idle timeout must be positive")
        self.inactive_after_seconds = inactive_after_seconds
        self.last_activity = time.monotonic() if now is None else float(now)

    def wake(self, now: float | None = None):
        self.last_activity = time.monotonic() if now is None else float(now)

    def should_sleep(self, *, now: float | None = None, busy: bool = False) -> bool:
        if busy:
            return False
        current = time.monotonic() if now is None else float(now)
        return current - self.last_activity >= self.inactive_after_seconds


# Broad nonrectangular silhouette. Gives the desktop its mouse back wherever
# the transparent frame has no Iris pixels. The body contours are generous
# enough to accommodate all currently supported poses.
BASE_SILHOUETTE = (
    (57, 26, 130, 150),    # head + hair
    (74, 129, 96, 107),    # torso
    (41, 151, 63, 99),     # hanging arm
    (145, 130, 84, 112),   # hand and extended arm
    (75, 206, 61, 100),    # left leg
    (118, 206, 64, 100),   # right leg
)


def silhouette_rectangles(scale: float) -> tuple[tuple[int, int, int, int], ...]:
    """Scaled ellipses for OS-level Qt window mask; no 1:1 image polling."""
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid mascot scale")
    return tuple((round(x*scale), round(y*scale), max(1, round(w*scale)),
                  max(1, round(h*scale))) for x, y, w, h in BASE_SILHOUETTE)
