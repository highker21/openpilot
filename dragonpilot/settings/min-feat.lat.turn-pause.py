from dragonpilot.settings import tr

ITEMS = [
  {
    "section": "Lateral",
    "key": "dp_lat_turn_pause",
    "type": "toggle_item",
    "title": lambda: tr("Pause Steering While Turning"),
    "description": lambda: tr("With the blinker on below the Lane Change Assist speed (20 mph if LCA is off), openpilot/ALKA stops steering so you can turn freely. It resumes once the blinker is off and the wheel is straight, or when well above that speed with a straight wheel.<br>Only a single-side blinker triggers it: turns without signalling and hazard lights do not pause steering."),
    "flags": "PERSISTENT",
    "param_type": "BOOL",
    "default": "0",
  },
]
