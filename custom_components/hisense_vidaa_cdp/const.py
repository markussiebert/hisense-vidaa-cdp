"""Constants for the Hisense VIDAA CDP integration."""

DOMAIN = "hisense_vidaa_cdp"
CDP_PORT = 9223
DEFAULT_SCAN_INTERVAL = 10  # seconds

# config keys
CONF_HOST = "host"
CONF_MAC = "mac"
CONF_BROADCAST = "broadcast_address"
CONF_NAME = "name"

# source index <-> label (index is the argument to changeSourceTo)
SOURCES = {
    "TV": 0,
    "AV": 1,
    "Component": 2,
    "HDMI 1": 3,
    "HDMI 2": 4,
    "HDMI 3": 5,
    "HDMI 4": 6,
}
SOURCE_BY_INDEX = {v: k for k, v in SOURCES.items()}

# remote key codes (dispatched as DOM KeyboardEvent.keyCode in the TV UI)
KEY_VOLUME_UP = 447
KEY_VOLUME_DOWN = 448
KEY_MUTE = 449
