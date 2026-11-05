"""
dp - turn pause: HUD hint while lateral control is paused for a signalled turn.

Runs the same TurnPause logic as controlsd on the UI's carState, so the hint
tracks what controlsd does up to message timing. Shown only while openpilot is
engaged or ALKA is steering; after LONG_PAUSE_S paused while moving it turns
into a red warning.
"""
import time

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.text_measure import measure_text_cached
from dragonpilot.selfdrive.controls.lib.turn_pause import TurnPause, turn_speed_ms, turn_signal

FONT_SIZE = 44
PARAMS_INTERVAL_S = 1.
HINT_BG = rl.Color(0, 0, 0, 166)
HINT_TEXT = rl.Color(255, 200, 0, 255)
WARN_BG = rl.Color(201, 34, 49, 230)


class TurnPauseHud:
  def __init__(self):
    self._tp = TurnPause()
    self._enabled = False
    self._turn_speed = turn_speed_ms(0)
    self._params_read = -1e9

  def _paused(self) -> bool:
    now = time.monotonic()
    if now - self._params_read > PARAMS_INTERVAL_S:
      self._params_read = now
      self._enabled = ui_state.params.get_bool("dp_lat_turn_pause")
      self._turn_speed = turn_speed_ms(int(ui_state.params.get("dp_lat_lca_speed") or 0))
    sm = ui_state.sm
    if sm.recv_frame['carState'] < ui_state.started_frame:
      self._tp.reset()
      return False
    cs = sm['carState']
    paused = self._tp.update(self._enabled, turn_signal(cs.leftBlinker, cs.rightBlinker), cs.vEgo, cs.steeringAngleDeg, now, self._turn_speed)
    steering_on = sm['selfdriveState'].enabled or ui_state.dp_alka_active
    return paused and steering_on

  def render(self, rect: rl.Rectangle, font: rl.Font) -> None:
    if not self._paused():
      return
    long_pause = self._tp.long_pause()
    text = "STEER ASSIST PAUSED" if long_pause else "TURN PAUSE"
    size = measure_text_cached(font, text, FONT_SIZE)
    x = rect.x + rect.width / 2 - size.x / 2
    y = rect.y + 330
    rl.draw_rectangle_rounded(rl.Rectangle(x - 24, y - 8, size.x + 48, size.y + 16), 0.35, 10, WARN_BG if long_pause else HINT_BG)
    rl.draw_text_ex(font, text, rl.Vector2(x, y), FONT_SIZE, 0, rl.WHITE if long_pause else HINT_TEXT)
