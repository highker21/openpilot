from dragonpilot.settings import tr

ITEMS = [
  {
    "section": "Longitudinal",
    "key": "dp_lon_curve_speed",
    "type": "toggle_item",
    "title": lambda: tr("Curve Speed (shadow, log only)"),
    "description": lambda: tr("Works out how much to slow for a bend the model sees ahead (sunnypilot's vision Smart Cruise Control) and logs it. Shadow only: it never changes speed or braking."),
    "condition": "openpilotLongitudinalControl",
    "flags": "PERSISTENT",
    "param_type": "BOOL",
    "default": "0",
  },
]
