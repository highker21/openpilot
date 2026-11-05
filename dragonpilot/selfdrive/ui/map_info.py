"""
dp - mapd: onroad speed-limit sign and map hints, drawn under the MAX box.

Display only. Reads ui_state.sm['mapdOut'] (pfeiferj/mapd, offline OSM) and
never feeds anything back to planning or controls. Draws nothing unless mapd
is running (dp_ui_map_display), publishing, and has a map tile loaded.
"""
import pyray as rl

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.text_measure import measure_text_cached

SIGN_RADIUS = 78
SIGN_RING = 14
SIGN_FONT_SIZE = 72
HINT_FONT_SIZE = 40
NEXT_LIMIT_MAX_DIST = 1000.  # m, only preview changes this close

RED = rl.Color(201, 34, 49, 255)
WHITE = rl.WHITE
BLACK = rl.Color(0, 0, 0, 255)
HINT_BG = rl.Color(0, 0, 0, 166)
HINT_TEXT = rl.Color(255, 255, 255, 230)
CURVE_TEXT = rl.Color(255, 200, 0, 255)


def _to_display_speed(v_ms: float) -> int:
  return round(v_ms * (CV.MS_TO_KPH if ui_state.is_metric else CV.MS_TO_MPH))


def map_info_active() -> bool:
  sm = ui_state.sm
  if 'mapdOut' not in sm.data or not sm.alive['mapdOut']:
    return False
  if sm.recv_frame['mapdOut'] < ui_state.started_frame:
    return False
  return bool(sm['mapdOut'].tileLoaded)


def draw_map_info(center_x: float, top_y: float, font_bold: rl.Font, font_semi_bold: rl.Font) -> None:
  if not map_info_active():
    return
  out = ui_state.sm['mapdOut']

  y = top_y
  if out.speedLimit > 0:
    center = rl.Vector2(center_x, y + SIGN_RADIUS)
    rl.draw_circle_v(center, SIGN_RADIUS, RED)
    rl.draw_circle_v(center, SIGN_RADIUS - SIGN_RING, WHITE)
    text = str(_to_display_speed(out.speedLimit))
    size = measure_text_cached(font_bold, text, SIGN_FONT_SIZE)
    rl.draw_text_ex(font_bold, text, rl.Vector2(center.x - size.x / 2, center.y - size.y / 2), SIGN_FONT_SIZE, 0, BLACK)
    y += 2 * SIGN_RADIUS + 16

  hints: list[tuple[str, rl.Color]] = []
  if out.nextSpeedLimit > 0 and 0 < out.nextSpeedLimitDistance < NEXT_LIMIT_MAX_DIST and \
     round(out.nextSpeedLimit, 1) != round(out.speedLimit, 1):
    hints.append((f"NEXT {_to_display_speed(out.nextSpeedLimit)} / {round(out.nextSpeedLimitDistance / 50) * 50:.0f}m", HINT_TEXT))
  if out.mapCurveSpeed > 0 and (out.speedLimit <= 0 or out.mapCurveSpeed < out.speedLimit):
    hints.append((f"CURVE {_to_display_speed(out.mapCurveSpeed)}", CURVE_TEXT))

  for text, color in hints:
    size = measure_text_cached(font_semi_bold, text, HINT_FONT_SIZE)
    bg = rl.Rectangle(center_x - size.x / 2 - 16, y, size.x + 32, size.y + 16)
    rl.draw_rectangle_rounded(bg, 0.35, 10, HINT_BG)
    rl.draw_text_ex(font_semi_bold, text, rl.Vector2(center_x - size.x / 2, y + 8), HINT_FONT_SIZE, 0, color)
    y += size.y + 28
