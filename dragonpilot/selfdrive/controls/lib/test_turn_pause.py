from openpilot.common.constants import CV
from dragonpilot.selfdrive.controls.lib.turn_pause import TurnPause, turn_speed_ms, turn_signal, LONG_PAUSE_S

KPH = CV.KPH_TO_MS
TURN = turn_speed_ms(20)  # ~32 km/h


def run(tp, steps, enabled=True, turn=TURN):
  """steps: list of (t, blinker, v_kph, angle_deg); returns paused state after each step."""
  return [tp.update(enabled, b, v * KPH, a, t, turn) for t, b, v, a in steps]


def test_blinker_below_turn_speed_pauses():
  assert run(TurnPause(), [(0., True, 20, 0)]) == [True]

def test_blinker_above_turn_speed_does_not_pause():
  assert run(TurnPause(), [(0., True, 60, 0)]) == [False]

def test_no_blinker_never_pauses_even_at_full_lock():
  assert run(TurnPause(), [(0., False, 15, 300), (1., False, 15, 450)]) == [False, False]

def test_disabled_never_pauses():
  assert run(TurnPause(), [(0., True, 10, 90)], enabled=False) == [False]

def test_blinker_off_but_wheel_still_turned_stays_paused():
  steps = [(0., True, 15, 0), (1., True, 15, 200), (2., False, 15, 30), (3., False, 15, 30)]
  assert run(TurnPause(), steps) == [True, True, True, True]

def test_resumes_after_straight_for_half_second():
  steps = [(0., True, 15, 200), (1., False, 18, 5), (1.3, False, 20, 5), (1.5, False, 22, 5)]
  assert run(TurnPause(), steps) == [True, True, True, False]

def test_straight_timer_restarts_if_wheel_moves():
  steps = [(0., True, 15, 200), (1., False, 18, 5), (1.4, False, 18, 15), (1.6, False, 18, 5), (2.0, False, 18, 5),
           (2.1, False, 18, 5)]
  assert run(TurnPause(), steps) == [True, True, True, True, True, False]

def test_stays_paused_when_speeding_up_with_wheel_turned():
  # pulling out onto a main road: above turn speed but still turning -> keep paused
  steps = [(0., True, 15, 0), (1., True, 40, 60), (2., True, 50, 45)]
  assert run(TurnPause(), steps) == [True, True, True]

def test_blinker_left_on_resumes_when_clearly_past_turn_speed_and_straight():
  fast = 32 + 10 + 5  # km/h, above turn speed + margin
  steps = [(0., True, 15, 90), (5., True, fast, 3), (6., True, fast, 3), (7.0, True, fast, 3), (7.1, True, fast, 3)]
  assert run(TurnPause(), steps) == [True, True, True, False, False]

def test_blinker_left_on_just_above_turn_speed_stays_paused():
  # within the +10 km/h margin the fast path does not apply
  steps = [(0., True, 15, 90), (1., True, 36, 3), (5., True, 36, 3)]
  assert run(TurnPause(), steps) == [True, True, True]

def test_long_pause_counts_only_moving_time():
  tp = TurnPause()
  t = 0.
  # 60 s waiting at the junction with the blinker on: no warning
  while t <= 60.:
    tp.update(True, True, 0., 0., t, TURN); t += 0.1
  assert tp.paused and not tp.long_pause()
  # then creeping/turning with the wheel turned for LONG_PAUSE_S + 1 s
  end = t + LONG_PAUSE_S + 1
  while t <= end:
    tp.update(True, True, 15 * KPH, 90., t, TURN); t += 0.1
  assert tp.long_pause()

def test_long_pause_clears_on_resume():
  tp = TurnPause()
  t = 0.
  while t <= LONG_PAUSE_S + 2:
    tp.update(True, True, 15 * KPH, 90., t, TURN); t += 0.1
  assert tp.long_pause()
  for _ in range(10):
    tp.update(True, False, 20 * KPH, 0., t, TURN); t += 0.1
  assert not tp.paused and not tp.long_pause()

def test_lca_speed_zero_falls_back_to_20mph():
  assert turn_speed_ms(0) == turn_speed_ms(20)
  assert abs(turn_speed_ms(20) * CV.MS_TO_KPH - 32.19) < 0.01

def test_disable_while_paused_resets():
  tp = TurnPause()
  assert run(tp, [(0., True, 10, 90)]) == [True]
  assert run(tp, [(1., True, 10, 90)], enabled=False) == [False]
  assert not tp.paused

def test_hazards_are_not_a_turn_signal():
  assert turn_signal(True, False) and turn_signal(False, True)
  assert not turn_signal(True, True) and not turn_signal(False, False)
  tp = TurnPause()
  assert not tp.update(True, turn_signal(True, True), 10 * KPH, 0., 0., TURN)
