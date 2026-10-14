"""Pure geometry for the band map: audio offsets to x positions. No Qt, so it is tested outside the gui package."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Axis:
    """A linear audio offset axis from `low_hz` to `high_hz`, drawn over `width_px` starting at `left_px`."""

    low_hz: int
    high_hz: int
    left_px: float
    width_px: float

    def x_of(self, hz: float) -> float:
        """Horizontal pixel position of an audio offset."""
        return self.left_px + (hz - self.low_hz) / (self.high_hz - self.low_hz) * self.width_px

    def ticks(self, step_hz: int) -> list[int]:
        """Multiples of `step_hz` inside the axis, in order."""
        first = math.ceil(self.low_hz / step_hz) * step_hz
        return list(range(first, self.high_hz + 1, step_hz))
