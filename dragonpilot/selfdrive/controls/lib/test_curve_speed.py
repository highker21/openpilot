import numpy as np

from dragonpilot.selfdrive.controls.lib.curve_speed import CurveSpeed, ShadowGuard, VisionState, MIN_V, V_CRUISE_UNSET, _ENTERING_PRED_LAT_ACC_TH

N = 33  # ModelConstants.IDX_N
V = MIN_V + 5.


def flat(pred_lat_acc):
  """rate * vel == pred_lat_acc at every point of the plan"""
  return [float(pred_lat_acc)] * N, [1.] * N


def step(cs, pred=0., curvature=0., v=V, enabled=True, long_enabled=True, override=False):
  rate, vel = flat(pred)
  return cs.update(enabled, long_enabled, override, v, 0., rate, vel, curvature)


def test_initial_state():
  cs = CurveSpeed()
  assert cs.state == VisionState.disabled
  assert not cs.is_active
  assert cs.output_v_target == V_CRUISE_UNSET
  assert cs.output_a_target == 0.


def test_feature_off_stays_disabled():
  cs = CurveSpeed()
  for _ in range(10):
    step(cs, pred=3., enabled=False)
  assert cs.state == VisionState.disabled


def test_not_engaged_stays_disabled():
  cs = CurveSpeed()
  for _ in range(10):
    step(cs, pred=3., long_enabled=False)
  assert cs.state == VisionState.disabled


def test_enters_above_threshold():
  cs = CurveSpeed()
  step(cs)                                   # disabled -> enabled
  assert step(cs, pred=_ENTERING_PRED_LAT_ACC_TH + 0.01)
  assert cs.state == VisionState.entering
  assert cs.is_active
  assert cs.a_target < 0.                    # eases off before the corner
  assert cs.output_v_target < V_CRUISE_UNSET


def test_single_spike_filtered_by_p97():
  cs = CurveSpeed()
  step(cs)
  rate = [1.] * N
  rate[-1] = 2.                              # max over threshold, p97 under it
  cs.update(True, True, False, V, 0., rate, [1.] * N, 0.)
  assert cs.max_pred_lat_acc < _ENTERING_PRED_LAT_ACC_TH
  assert cs.state == VisionState.enabled


def test_no_turn_cycle_at_low_speed():
  cs = CurveSpeed()
  step(cs, v=MIN_V)
  step(cs, pred=3., v=MIN_V)
  assert cs.state == VisionState.enabled


def test_full_turn_cycle():
  cs = CurveSpeed()
  step(cs)
  step(cs, pred=2.)
  assert cs.state == VisionState.entering
  step(cs, pred=2., curvature=1.7 / V ** 2)  # lat acc 1.7 -> turning
  assert cs.state == VisionState.turning
  step(cs, pred=2., curvature=1.2 / V ** 2)  # 1.2 -> leaving
  assert cs.state == VisionState.leaving
  assert cs.a_target == 0.5
  step(cs, pred=0., curvature=1.0 / V ** 2)  # 1.0 -> done
  assert cs.state == VisionState.enabled
  assert cs.output_v_target == V_CRUISE_UNSET


def test_abort_entering_when_prediction_drops():
  cs = CurveSpeed()
  step(cs)
  step(cs, pred=2.)
  step(cs, pred=1.0)
  assert cs.state == VisionState.enabled


def test_override_then_back():
  cs = CurveSpeed()
  step(cs)
  step(cs, pred=2., override=True)
  assert cs.state == VisionState.overriding
  assert not cs.is_active
  step(cs, override=False)
  assert cs.state == VisionState.enabled


def test_straight_road_no_division_by_zero():
  cs = CurveSpeed()
  step(cs)
  step(cs, pred=0.)
  assert cs.v_target == V_CRUISE_UNSET
  assert np.isfinite(cs.output_a_target)


def test_bad_plan_length_keeps_last_values():
  cs = CurveSpeed()
  step(cs)
  step(cs, pred=2.)
  cs.update(True, True, False, V, 0., [], [], 0.)
  assert cs.max_pred_lat_acc == 2.


def boom():
  raise ValueError("forced")


def test_guard_swallows_and_rate_limits():
  logged, t = [], [0.]
  g = ShadowGuard(logged.append, period=60., clock=lambda: t[0])
  assert not g.run(boom)
  t[0] = 30.
  assert not g.run(boom)                     # within the period: counted, not logged again
  t[0] = 61.
  assert not g.run(boom)
  assert g.errors == 3
  assert len(logged) == 2


def test_guard_passes_through():
  out = []
  g = ShadowGuard(lambda msg: None)
  assert g.run(out.append, 1)
  assert out == [1] and g.errors == 0


def test_guard_shields_a_failing_update():
  cs = CurveSpeed()
  cs.update = lambda *a: boom()              # forced failure inside the shadow
  g = ShadowGuard(lambda msg: None)
  assert not g.run(cs.update, True, True, False, V, 0., [], [], 0.)
