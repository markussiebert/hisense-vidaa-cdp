# Hisense VIDAA (CDP) for Home Assistant

A local Home Assistant integration for Hisense VIDAA TVs. It talks directly to
the TV's Chrome DevTools Protocol endpoint on port **9223** — no MQTT broker, no
cloud account, no extra hardware.

The TV is exposed as a `media_player` entity with power, volume, mute, source
selection, app launching and current channel readout.

## Features

| Feature | How it works |
| --- | --- |
| Power on | Wake-on-LAN magic packet |
| Power off | Native standby via the TV's own `switchOffTV()` |
| Absolute volume | `window.model.sound.setMainVolume()` |
| Volume step | Native volume-up/down key events |
| Mute | `window.model.sound.setMainMute()` |
| Source selection | TV, AV, Component, HDMI 1–4 |
| App launch | `StartApplication(name)` |
| Current channel / source | Polled from the TV UI every 10 seconds |

## Requirements

- Home Assistant 2024.1 or newer
- A Hisense VIDAA TV reachable over the network with the DevTools port (9223)
  open while the TV is on
- The TV's IP address
- Recommended: the TV's MAC address for Wake-on-LAN power-on

## Installation

### HACS (custom repository)

1. Open HACS in Home Assistant.
2. Click the three-dot menu in the top right and choose **Custom repositories**.
3. Enter `https://github.com/markussiebert/hisense-vidaa-cdp` and select the
   **Integration** category.
4. Add the repository, search for **Hisense VIDAA (CDP)** and install it.
5. Restart Home Assistant.

### Manual installation

Copy `custom_components/hisense_vidaa_cdp` into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Hisense VIDAA (CDP)**.
3. Enter the TV's IP address, its MAC address (for Wake-on-LAN power-on) and,
   optionally, a broadcast address.
4. Give the device a name and submit.

The config flow only fails with `cannot_connect` if the host cannot be reached
at all (timeout or DNS failure). A connection refused is accepted, because that
usually just means the TV is in standby and its DevTools port is not listening.

## Wake-on-LAN caveats

- Power-on works **only** via Wake-on-LAN: the DevTools port disappears when the
  TV enters standby, so a powered-off TV cannot be woken over CDP.
- Home Assistant and the TV must be on the same L2 network segment for the magic
  packet to arrive. If they are on different subnets/VLANs, enter the TV
  subnet's broadcast address (for example `192.168.1.255`) in the optional
  broadcast field.
- Wake-on-LAN must be enabled on the TV (some models call this "Wake on LAN" or
  "Network standby").

## Notes

- Polling interval is 10 seconds.
- Standby is treated as a normal state: the entity stays available and simply
  reports `off` instead of becoming unavailable.
- This integration is not affiliated with Hisense.

## Development

`test_cdp.py` is a small standalone client for poking a real TV without Home
Assistant:

```bash
python3 test_cdp.py <tv-ip> status
python3 test_cdp.py <tv-ip> vol 20
python3 test_cdp.py <tv-ip> source 3
python3 test_cdp.py <tv-ip> app Netflix
```
