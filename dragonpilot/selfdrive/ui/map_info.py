"""
dp - mapd: onroad speed-limit sign and map hints, drawn under the MAX box.

Display only. Reads ui_state.sm['mapdOut'] (pfeiferj/mapd, offline OSM) and
never feeds anything back to planning or controls. Draws nothing unless mapd
is running (dp_ui_map_display), publishing, and has a map tile loaded.
"""
from importlib.resources import as_file

import pyray as rl

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FONT_DIR, FONT_SCALE
from openpilot.system.ui.lib.text_measure import measure_text_cached

SIGN_RADIUS = 78
SIGN_RING = 14
SIGN_FONT_SIZE = 60
HINT_FONT_SIZE = 40
NEXT_LIMIT_MAX_DIST = 1000.  # m, only preview changes this close

RED = rl.Color(201, 34, 49, 255)
WHITE = rl.WHITE
BLACK = rl.Color(0, 0, 0, 255)
HINT_BG = rl.Color(0, 0, 0, 166)
HINT_TEXT = rl.Color(255, 255, 255, 230)
CURVE_TEXT = rl.Color(255, 200, 0, 255)

# Road names are mostly CJK, but the prebuilt .fnt atlases only carry the glyphs used by the
# translations, so load just the glyphs of the current name from the full OpFont on change.
ROAD_FONT_FILE = "OpFont-SemiBold.otf"
ROAD_FONT_SIZE = 56
ROAD_NAME_MAX_CHARS = 20
ROAD_BOTTOM_MARGIN = 40


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
    # left-aligned with the MAX box so longer hints grow rightwards instead of off-screen
    left = max(center_x - SIGN_RADIUS - 22, 16)
    bg = rl.Rectangle(left, y, size.x + 32, size.y + 16)
    rl.draw_rectangle_rounded(bg, 0.35, 10, HINT_BG)
    rl.draw_text_ex(font_semi_bold, text, rl.Vector2(left + 16, y + 8), HINT_FONT_SIZE, 0, color)
    y += size.y + 28


class RoadNameFont:
  def __init__(self):
    self._text = ""
    self._font = None  # rl.Font, loaded lazily per road name

  def get(self, text: str):
    if text != self._text:
      self._unload()
      self._text = text
      codepoints = sorted({ord(c) for c in text})
      try:
        with as_file(FONT_DIR.joinpath(ROAD_FONT_FILE)) as path:
          cp = rl.ffi.new("int[]", codepoints)
          font = rl.load_font_ex(str(path), round(ROAD_FONT_SIZE * FONT_SCALE), rl.ffi.cast("int *", cp), len(codepoints))
        if font.glyphCount > 0 and font.texture.id > 0:
          rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
          self._font = font
      except Exception:
        self._font = None
    return self._font

  def _unload(self) -> None:
    if self._font is not None:
      rl.unload_font(self._font)
      self._font = None


_road_font = RoadNameFont()


def road_name_text() -> str:
  if not map_info_active():
    return ""
  name = ui_state.sm['mapdOut'].roadName.strip()
  return name if len(name) <= ROAD_NAME_MAX_CHARS else name[:ROAD_NAME_MAX_CHARS] + "\u2026"


def draw_road_name(rect: rl.Rectangle) -> None:
  """Current road name at the bottom center; yields to alerts, which also live at the bottom."""
  if ui_state.sm['selfdriveState'].alertSize != 0:
    return
  text = road_name_text()
  if not text:
    return
  font = _road_font.get(text)
  if font is None:
    return
  # This font is not one of gui_app's, so bypass the patched draw_text_ex (its font_fallback would
  # swap it for an atlas without these glyphs after a language switch) and apply FONT_SCALE here.
  font_size = ROAD_FONT_SIZE * FONT_SCALE
  draw_text = getattr(rl, "_orig_draw_text_ex", rl.draw_text_ex)
  size = rl.measure_text_ex(font, text, font_size, 0)  # noqa: TID251
  x = rect.x + rect.width / 2 - size.x / 2
  y = rect.y + rect.height - ROAD_BOTTOM_MARGIN - size.y - 16
  rl.draw_rectangle_rounded(rl.Rectangle(x - 24, y - 8, size.x + 48, size.y + 16), 0.35, 10, HINT_BG)
  draw_text(font, text, rl.Vector2(x, y), font_size, 0, WHITE)
