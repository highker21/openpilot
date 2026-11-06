"""
dp - curve speed (shadow): what slowing for a bend the model can see coming would ask for.

Ported from sunnypilot's Smart Cruise Control (vision), MIT License:
  sunnyhaibin/sunnypilot @ 02ef6e4ce0a6e22f6209c17cc6a59f0684241008
  sunnypilot/selfdrive/controls/lib/smart_cruise_control/vision_controller.py
  Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

The model's yaw-rate plan times its speed plan gives the lateral acceleration we would pull
over the path ahead; over _ENTERING_PRED_LAT_ACC_TH the state machine starts easing off before
the corner (ENTERING), holds a comfortable acceleration in it (TURNING) and regains speed after
it (LEAVING). Thresholds and lookup tables are sunnypilot's, unchanged.

Shadow only: the planner runs this after its output is final and plannerd publishes it as
curveSpeedShadow (20 Hz, every 10th in the qlog), but nothing it computes reaches the plan or
the car. Changes from the original: no Params / cereal custom types (enabled is passed in,
states are a local IntEnum), inputs are plain values so it can be replayed offline, and a
straight plan (max_curve 0) gives v_target V_CRUISE_UNSET instead of dividing by zero.
"""
import time
from enum import IntEnum

import numpy as np

from openpilot.common.constants import CV

V_CRUISE_UNSET = 255            # selfdrive/car/cruise.py; not imported so this stays pure (no cereal) like turn_pause
MIN_V = 20 * CV.KPH_TO_MS         # sunnypilot smart_cruise_control/__init__.py

_ENTERING_PRED_LAT_ACC_TH = 1.3   # predicted lat acc that triggers the entering state
_ABORT_ENTERING_PRED_LAT_ACC_TH = 1.1  # abort entering if the predicted lat acc drops below this

_TURNING_LAT_ACC_TH = 1.6         # lat acc that triggers the turning state

_LEAVING_LAT_ACC_TH = 1.3         # lat acc that triggers the leaving state
_FINISH_LAT_ACC_TH = 1.1          # lat acc that ends the turn cycle

_A_LAT_REG_MAX = 2.               # maximum lateral acceleration

_NO_OVERSHOOT_TIME_HORIZON = 4.   # s, horizon for v_target from a_target when not overshooting

# minimum smooth deceleration in ENTERING, by the maximum predicted lat acc ahead
_ENTERING_SMOOTH_DECEL_V = [-0.2, -1.]
_ENTERING_SMOOTH_DECEL_BP = [1.3, 3.]

# acceleration in TURNING, by the current lat acc
_TURNING_ACC_V = [0.5, 0., -0.4]
_TURNING_ACC_BP = [1.5, 2.3, 3.]

_LEAVING_ACC = 0.5                # comfortable acceleration to regain speed leaving a turn


class VisionState(IntEnum):
  disabled = 0
  enabled = 1
  overriding = 2
  entering = 3
  turning = 4
  leaving = 5


ERROR_LOG_PERIOD = 60.           # s, at most one exception logged per period


class ShadowGuard:
  """A shadow feature must never take control down: run it, swallow any exception, log one per period."""
  def __init__(self, log_exception, period=ERROR_LOG_PERIOD, clock=time.monotonic):
    self.log_exception = log_exception
    self.period = period
    self.clock = clock
    self.last_log_t = None
    self.errors = 0

  def run(self, fn, *args):
    try:
      fn(*args)
      return True
    except Exception:
      self.errors += 1
      now = self.clock()
      if self.last_log_t is None or now - self.last_log_t >= self.period:
        self.last_log_t = now
        self.log_exception(f"dp_curve_speed shadow failed ({self.errors} so far)")
      return False


ACTIVE_STATES = (VisionState.entering, VisionState.turning, VisionState.leaving)
ENABLED_STATES = (VisionState.enabled, VisionState.overriding, *ACTIVE_STATES)


class CurveSpeed:
  def __init__(self):
    self.long_enabled = False
    self.long_override = False
    self.enabled = False
    self.is_enabled = False
    self.is_active = False
    self.v_ego = 0.
    self.a_ego = 0.

    self.state = VisionState.disabled
    self.current_lat_acc = 0.
    self.max_pred_lat_acc = 0.
    self.v_target = 0.
    self.a_target = 0.
    self.output_v_target = V_CRUISE_UNSET
    self.output_a_target = 0.

  def _update_calculations(self, rate_plan, vel_plan, curvature):
    if not self.long_enabled:
      return
    rate_plan = np.abs(np.asarray(rate_plan, dtype=float))
    vel_plan = np.asarray(vel_plan, dtype=float)
    if len(rate_plan) == 0 or len(rate_plan) != len(vel_plan):
      return

    self.current_lat_acc = self.v_ego ** 2 * abs(curvature)

    # maximum lat accel the model predicts ahead
    self.max_pred_lat_acc = float(np.percentile(rate_plan * vel_plan, 97))

    # maximum curve at the current speed, and the speed that curve allows
    v_ego = max(self.v_ego, 0.1)
    max_curve = self.max_pred_lat_acc / (v_ego ** 2)
    self.v_target = (_A_LAT_REG_MAX / max_curve) ** 0.5 if max_curve > 0. else V_CRUISE_UNSET

  def _update_state_machine(self):
    if self.state != VisionState.disabled:
      # longitudinal and feature disable always have priority in a non-disabled state
      if not self.long_enabled or not self.enabled:
        self.state = VisionState.disabled
      elif self.long_override:
        self.state = VisionState.overriding

      elif self.state == VisionState.enabled:
        # no turn cycle at low speed
        if self.v_ego <= MIN_V:
          pass
        elif self.max_pred_lat_acc >= _ENTERING_PRED_LAT_ACC_TH:
          self.state = VisionState.entering

      elif self.state == VisionState.overriding:
        if not self.long_override:
          self.state = VisionState.enabled

      elif self.state == VisionState.entering:
        if self.current_lat_acc >= _TURNING_LAT_ACC_TH:
          self.state = VisionState.turning
        elif self.max_pred_lat_acc < _ABORT_ENTERING_PRED_LAT_ACC_TH:
          self.state = VisionState.enabled

      elif self.state == VisionState.turning:
        if self.current_lat_acc <= _LEAVING_LAT_ACC_TH:
          self.state = VisionState.leaving

      elif self.state == VisionState.leaving:
        if self.current_lat_acc >= _TURNING_LAT_ACC_TH:
          self.state = VisionState.turning
        elif self.current_lat_acc < _FINISH_LAT_ACC_TH:
          self.state = VisionState.enabled

    elif self.long_enabled and self.enabled:
      self.state = VisionState.overriding if self.long_override else VisionState.enabled

    return self.state in ENABLED_STATES, self.state in ACTIVE_STATES

  def _update_solution(self):
    if self.state not in ACTIVE_STATES:
      return self.a_ego
    if self.state == VisionState.entering:
      return float(np.interp(self.max_pred_lat_acc, _ENTERING_SMOOTH_DECEL_BP, _ENTERING_SMOOTH_DECEL_V))
    if self.state == VisionState.turning:
      return float(np.interp(self.current_lat_acc, _TURNING_ACC_BP, _TURNING_ACC_V))
    return _LEAVING_ACC

  def update(self, enabled, long_enabled, long_override, v_ego, a_ego, rate_plan, vel_plan, curvature):
    """Returns True when the state changed this frame."""
    prev_state = self.state
    self.enabled = enabled
    self.long_enabled = long_enabled
    self.long_override = long_override
    self.v_ego = v_ego
    self.a_ego = a_ego

    self._update_calculations(rate_plan, vel_plan, curvature)
    self.is_enabled, self.is_active = self._update_state_machine()
    self.a_target = self._update_solution()

    if self.is_active:
      self.output_v_target = max(self.v_target, MIN_V) + self.a_target * _NO_OVERSHOOT_TIME_HORIZON
    else:
      self.output_v_target = V_CRUISE_UNSET
    self.output_a_target = self.a_target
    return self.state != prev_state
