from dragonpilot.settings import tr

ITEMS = [
  {
    "section": "UI",
    "key": "dp_ui_map_display",
    "type": "toggle_item",
    "title": lambda: tr("Map Info Display (Beta)"),
    "description": lambda: tr("Run mapd (offline OpenStreetMap) and show speed limit, next speed limit and map curve speed on the HUD.<br>Display only: openpilot does NOT change speed based on map data.<br>Maps must be downloaded first. Restart required."),
    "condition": "not MICI",
    "flags": "PERSISTENT",
    "param_type": "BOOL",
    "default": "0",
  },
]
