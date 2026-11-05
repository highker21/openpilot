"""
dp - turn pause: hand the wheel back while the driver turns at a junction.

Signalling below the turn speed (dp_lat_lca_speed, the speed below which a
blinker means a turn rather than a lane change) pauses lateral control, so
openpilot/ALKA stops pulling the wheel back during the turn. Lateral resumes
once the blinker is off and the wheel has been straight for a moment, or once
the car is clearly past turn speed with a straight wheel (blinker left on or
not self-cancelled). Only a single-side blinker triggers it (hazards keep steering, e.g. warning
of a jam ahead on the highway); a wheel-angle trigger would fire on hairpins.

Pure logic on carState values plus a monotonic time, so controlsd (which acts
on it) and the UI (which only shows it) run the same code.
"""
from openpilot.common.constants import CV

TURN_SPEED_FALLBACK_MPH = 20.  # dp_lat_lca_speed default; used when it is 0 (LCA off)
STRAIGHT_ANGLE_DEG = 10.
RESUME_STRAIGHT_S = 0.5        # blinker off and wheel straight this long -> resume
FAST_RESUME_MARGIN_MS = 10. * CV.KPH_TO_MS
FAST_RESUME_STRAIGHT_S = 2.    # above turn speed + margin, wheel straight this long -> resume even if blinker is on
LONG_PAUSE_S = 45.             # paused while moving longer than this -> UI warns prominently (11/04 replay: max 38.8 s)
MOVING_MS = 2.                 # waiting at the junction with the blinker on does not count towards LONG_PAUSE_S


def turn_signal(left: bool, right: bool) -> bool:
  return left != right  # hazards (both) are not a turn


def turn_speed_ms(lca_speed_mph: float) -> float:
  return (lca_speed_mph if lca_speed_mph > 0 else TURN_SPEED_FALLBACK_MPH) * CV.MPH_TO_MS


class TurnPause:
  def __init__(self):
    self.paused = False
    self.paused_since = 0.
    self.moving_paused_s = 0.
    self._last_t: float | None = None
    self._straight_since: float | None = None
    self._fast_straight_since: float | None = None

  def reset(self) -> None:
    self.paused = False
    self._straight_since = None
    self._fast_straight_since = None
    self.moving_paused_s = 0.

  def long_pause(self) -> bool:
    return self.paused and self.moving_paused_s > LONG_PAUSE_S

  def update(self, enabled: bool, blinker: bool, v_ego: float, steering_angle_deg: float,
             now: float, turn_speed: float) -> bool:
    """Returns True while lateral control should be paused."""
    dt = 0. if self._last_t is None else max(now - self._last_t, 0.)
    self._last_t = now
    if not enabled:
      self.reset()
      return False

    if not self.paused:
      if blinker and v_ego < turn_speed:
        self.paused = True
        self.paused_since = now
        self._straight_since = None
        self._fast_straight_since = None
        self.moving_paused_s = 0.
      return self.paused

    if v_ego > MOVING_MS:
      self.moving_paused_s += dt
    straight = abs(steering_angle_deg) < STRAIGHT_ANGLE_DEG

    if not blinker and straight:
      if self._straight_since is None:
        self._straight_since = now
    else:
      self._straight_since = None

    if v_ego > turn_speed + FAST_RESUME_MARGIN_MS and straight:
      if self._fast_straight_since is None:
        self._fast_straight_since = now
    else:
      self._fast_straight_since = None

    if (self._straight_since is not None and now - self._straight_since >= RESUME_STRAIGHT_S) or \
       (self._fast_straight_since is not None and now - self._fast_straight_since >= FAST_RESUME_STRAIGHT_S):
      self.reset()

    return self.paused
