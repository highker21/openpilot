"""
dp - mapd: "Download Taiwan Map" button for the dragonpilot settings panel.

Sends a single mapdIn download (or cancelDownload) to a running mapd and shows
progress from mapdExtendedOut.downloadProgress. Offroad only, and only while
dp_ui_map_display is on and mapd is publishing. Map tiles land in MAPS_DIR.
"""
import os
import time

import cereal.messaging as messaging
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import DialogResult
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog
from openpilot.system.ui.widgets.list_view import button_item
from dragonpilot.system.ui.lib.multilang import tr

DOWNLOAD_AREA = "nation.TW"
DOWNLOAD_SIZE_MB = 40  # offline/{20,22,24}/120.tar.gz on map-data.pfeifer.dev, ~38 MB total (2026-11-05)
MAPS_DIR = "/data/media/0/osm"
SEND_LOCKOUT_S = 15.  # ignore repeat presses until mapd reports the download as active


class MapDownload:
  def __init__(self):
    self._pm: messaging.PubMaster | None = None
    self._last_send = 0.
    self._maps_checked = 0.
    self._has_maps = False
    self.item = button_item(lambda: tr("Download Taiwan Map"), self._button_text, self._description,
                            callback=self._on_click, enabled=self._enabled)

  def _progress(self):
    sm = ui_state.sm
    if 'mapdExtendedOut' not in sm.data or not sm.alive['mapdExtendedOut']:
      return None
    return sm['mapdExtendedOut'].downloadProgress

  def _mapd_running(self) -> bool:
    sm = ui_state.sm
    return 'mapdOut' in sm.data and sm.alive['mapdOut']

  def _downloading(self) -> bool:
    p = self._progress()
    return p is not None and p.active

  def _maps_present(self) -> bool:
    now = time.monotonic()
    if now - self._maps_checked > 5.:
      self._maps_checked = now
      try:
        self._has_maps = any(os.scandir(MAPS_DIR))
      except OSError:
        self._has_maps = False
    return self._has_maps

  def _enabled(self) -> bool:
    if not ui_state.is_offroad() or not ui_state.params.get_bool("dp_ui_map_display") or not self._mapd_running():
      return False
    return self._downloading() or time.monotonic() - self._last_send > SEND_LOCKOUT_S

  def _button_text(self) -> str:
    return tr("CANCEL") if self._downloading() else tr("DOWNLOAD")

  def _description(self) -> str:
    if not ui_state.params.get_bool("dp_ui_map_display"):
      return tr("Turn on Map Info Display and restart the device first.")
    if not ui_state.is_offroad():
      return tr("Available while offroad.")
    if not self._mapd_running():
      return tr("Map service not running. Restart the device.")
    p = self._progress()
    if p is not None and p.active:
      return tr("Downloading: {} / {} files").format(p.downloadedFiles, p.totalFiles)
    if time.monotonic() - self._last_send <= SEND_LOCKOUT_S:
      return tr("Starting download...")
    base = tr("Uses about {} MB of data. Wi-Fi or phone hotspot required.").format(DOWNLOAD_SIZE_MB)
    if p is not None and p.cancelled:
      return tr("Download cancelled. ") + base
    if self._maps_present():
      return tr("Maps downloaded. Press again to update. ") + base
    return base

  def _send(self, input_type: str) -> None:
    if self._pm is None:
      self._pm = messaging.PubMaster(['mapdIn'])
    msg = messaging.new_message('mapdIn')
    msg.mapdIn.type = input_type
    if input_type == 'download':
      msg.mapdIn.str = DOWNLOAD_AREA
    self._pm.send('mapdIn', msg)

  def _on_click(self) -> None:
    if not self._enabled():
      return
    if self._downloading():
      self._send('cancelDownload')
      self._last_send = time.monotonic()
      return

    def confirm(result: int):
      if result != DialogResult.CONFIRM or not self._enabled() or self._downloading():
        return
      self._send('download')
      self._last_send = time.monotonic()

    text = tr("Download the Taiwan map now? It uses about {} MB of data.").format(DOWNLOAD_SIZE_MB)
    gui_app.push_widget(ConfirmDialog(text, tr("Download"), callback=confirm))
