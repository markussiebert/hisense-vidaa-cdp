"""Async Chrome DevTools Protocol client for Hisense VIDAA TVs.

The TV exposes a CDP endpoint on TCP port 9223. This module only talks to that
endpoint over HTTP/WebSocket using aiohttp; it has no Home Assistant imports so
it can be exercised standalone (see ``test_cdp.py``).

The TV's Chromium accepts only a single WebSocket debugger client per page, so
this client holds one connection open and reuses it across calls. A failed call
drops the socket and retries once on a fresh connection.

The single-persistent-connection approach (and the finding that a connect/close
cycle per call eventually strands a debugger session until the TV is mains power-
cycled), together with the ``parse_inputs`` 6-tuple decode below, are adapted from
chrisns/hisense_vidaa (MIT, Copyright (c) 2026 Chris Nesbitt-Smith). See
THIRD-PARTY-NOTICES.md.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

try:
    from .const import (
        CDP_PORT,
        KEY_VOLUME_DOWN,
        KEY_VOLUME_UP,
    )
except ImportError:  # pragma: no cover - allows running the file standalone
    from const import (  # type: ignore[no-redef]
        CDP_PORT,
        KEY_VOLUME_DOWN,
        KEY_VOLUME_UP,
    )

# Overall budget for a single Runtime.evaluate round-trip, in seconds.
EVALUATE_TIMEOUT = 10
# Budget for fetching the CDP target list, in seconds.
TARGET_LIST_TIMEOUT = 4
# Budget for establishing the WebSocket connection, in seconds.
WS_CONNECT_TIMEOUT = 10

_STATUS_EXPRESSION = (
    "(function(){var out={};"
    "try{out.source=window.model.source.getCurrentSource();}catch(e){}"
    "try{out.volume=window.model.sound.getMainVolume();}catch(e){}"
    "try{out.mute=window.model.sound.getMainMute();}catch(e){}"
    "try{var c=window.liveTV.getCurrentChannelInfo();"
    "if(c){out.channel_number=c.number;out.channel_name=c.name;}}catch(e){}"
    "try{out.inputs=model.source.getInputName();}catch(e){}"
    "try{out.backlight=model.video.getBacklight();}catch(e){}"
    "try{out.brightness=model.video.getBrightness();}catch(e){}"
    "try{out.contrast=model.video.getContrast();}catch(e){}"
    "try{out.colour_intensity=model.video.getColourIntensity();}catch(e){}"
    "try{out.sharpness=model.video.getSharpness();}catch(e){}"
    "try{out.eco_sensor=model.video.getEcoSensor();}catch(e){}"
    "try{out.freeze=model.video.getFreeze();}catch(e){}"
    "return JSON.stringify(out);})()"
)

_KEY_EXPRESSION = (
    "(function(){var c=__CODE__;"
    '["keydown","keyup"].forEach(function(t){'
    "var e=new KeyboardEvent(t,{bubbles:true,cancelable:true});"
    'Object.defineProperty(e,"keyCode",{get:function(){return c}});'
    'Object.defineProperty(e,"which",{get:function(){return c}});'
    'document.dispatchEvent(e);});return "ok";})()'
)

_POWER_OFF_EXPRESSION = (
    '(function(){try{switchOffTV("0");return "off";}'
    'catch(e){return "ERR:"+e.message;}})()'
)


class TVOffline(Exception):
    """Raised when the TV's CDP port cannot be reached (TV is in standby)."""


def parse_inputs(raw: list[str]) -> list[dict]:
    """Parse the flat 6-tuple array from model.source.getInputName().

    Adapted from chrisns/hisense_vidaa (MIT, (c) 2026 Chris Nesbitt-Smith).
    """
    out = []
    for i in range(0, len(raw) - 5, 6):
        out.append({
            "uid": int(raw[i]),
            "name": raw[i + 1],
            "available": raw[i + 2] == "1",
        })
    return out


class HisenseCDP:
    """Minimal CDP client for a Hisense VIDAA TV."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Store the TV host and the shared aiohttp session."""
        self.host = host
        self.base_url = f"http://{host}:{CDP_PORT}"
        self._session = session
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._msg_id = 0
        self._lock = asyncio.Lock()

    async def _ws_url(self) -> str:
        """Return the WebSocket debugger URL of the TV's CDP page target.

        Raises ``TVOffline`` when the TV does not answer or exposes no page.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=TARGET_LIST_TIMEOUT)
            async with self._session.get(
                f"{self.base_url}/json", timeout=timeout
            ) as resp:
                targets = await resp.json(content_type=None)
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            OSError,
            ValueError,
        ) as err:
            raise TVOffline(f"TV at {self.host} is unreachable: {err}") from err

        if not isinstance(targets, list) or not targets:
            raise TVOffline(f"TV at {self.host} exposes no CDP targets")

        candidates = [
            target
            for target in targets
            if isinstance(target, dict)
            and target.get("type") == "page"
            and target.get("webSocketDebuggerUrl")
        ]
        if not candidates:
            raise TVOffline(f"TV at {self.host} exposes no page target")

        target = next(
            (
                candidate
                for candidate in candidates
                if str(candidate.get("url", "")).endswith("index.html")
            ),
            candidates[0],
        )
        return str(target["webSocketDebuggerUrl"])

    async def _ensure_ws(self) -> aiohttp.ClientWebSocketResponse:
        """Return the held WebSocket, connecting first if necessary."""
        if self._ws is not None and not self._ws.closed:
            return self._ws

        ws_url = await self._ws_url()
        try:
            # No heartbeat: this Chromium never answers pings, and aiohttp
            # would tear the socket down when the pongs never arrive.
            ws = await asyncio.wait_for(
                self._session.ws_connect(ws_url), timeout=WS_CONNECT_TIMEOUT
            )
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            OSError,
        ) as err:
            self._ws = None
            raise TVOffline(f"TV at {self.host} is unreachable: {err}") from err

        self._ws = ws
        return ws

    async def _drop_ws(self) -> None:
        """Close the held WebSocket (best effort) and forget it."""
        ws, self._ws = self._ws, None
        if ws is None:
            return
        try:
            await ws.close()
        except Exception:  # noqa: BLE001 - closing is best effort
            pass

    async def async_close(self) -> None:
        """Release the held WebSocket connection."""
        async with self._lock:
            await self._drop_ws()

    async def _read_reply(
        self,
        ws: aiohttp.ClientWebSocketResponse,
        msg_id: int,
        timeout: float,
    ) -> dict[str, Any]:
        """Read messages until the reply with ``msg_id`` arrives."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError("timed out waiting for CDP reply")
            msg = await ws.receive(timeout=remaining)

            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                raise TVOffline(
                    f"WebSocket to {self.host} closed: {ws.exception()}"
                )

            if msg.type is not aiohttp.WSMsgType.TEXT:
                # Binary frames and events are not replies; ignore them.
                continue

            try:
                reply = json.loads(msg.data)
            except (ValueError, TypeError):
                continue
            if isinstance(reply, dict) and reply.get("id") == msg_id:
                return reply

    async def _ws_call(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = EVALUATE_TIMEOUT,
    ) -> dict[str, Any]:
        """Send one CDP command on the held socket and return its reply."""
        async with self._lock:
            last_err: Exception | None = None
            for _attempt in range(2):
                try:
                    ws = await self._ensure_ws()
                    self._msg_id += 1
                    msg_id = self._msg_id
                    await ws.send_json(
                        {"id": msg_id, "method": method, "params": params}
                    )
                    return await self._read_reply(ws, msg_id, timeout)
                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    OSError,
                    TVOffline,
                ) as err:
                    last_err = err
                    await self._drop_ws()

            raise TVOffline(
                f"TV at {self.host} is unreachable: {last_err}"
            ) from last_err

    async def evaluate(
        self, expression: str, timeout: float = EVALUATE_TIMEOUT
    ) -> Any:
        """Evaluate ``expression`` in the TV UI and return its value."""
        reply = await self._ws_call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout,
        )

        if "error" in reply:
            raise RuntimeError(f"CDP error: {reply['error']}")

        container = reply.get("result") or {}
        result = container.get("result") or {}
        exception = container.get("exceptionDetails")
        if (
            exception
            or container.get("wasThrown")
            or result.get("wasThrown")
            or result.get("subtype") == "error"
        ):
            detail = ""
            if exception:
                detail = (
                    (exception.get("exception") or {}).get("description")
                    or exception.get("text")
                    or str(exception)
                )
            elif result.get("description"):
                detail = result["description"]
            raise RuntimeError(f"JavaScript error: {detail or 'unknown error'}")

        return result.get("value")

    async def is_on(self) -> bool:
        """Return True when the TV's CDP port answers."""
        try:
            await self._ws_url()
        except TVOffline:
            return False
        return True

    async def get_status(self) -> dict[str, Any]:
        """Return the TV's current source, volume, mute and channel info."""
        raw = await self.evaluate(_STATUS_EXPRESSION)
        return json.loads(raw) if raw else {}

    async def set_source(self, index: int) -> None:
        """Switch the TV to the source with the given index."""
        await self.evaluate("changeSourceTo(%d)" % int(index))

    async def set_volume(self, level: int) -> None:
        """Set the main volume, clamped to 0..100."""
        level = max(0, min(100, int(level)))
        await self.evaluate("window.model.sound.setMainVolume(%d)" % level)

    async def set_mute(self, mute: bool) -> None:
        """Enable or disable mute."""
        await self.evaluate(
            "window.model.sound.setMainMute(%d)" % (1 if mute else 0)
        )

    async def set_backlight(self, value: int) -> None:
        """Set the backlight, clamped to 0..100."""
        value = max(0, min(100, int(value)))
        await self.evaluate("model.video.setBacklight(%d)" % value)

    async def set_brightness(self, value: int) -> None:
        """Set the brightness, clamped to 0..100."""
        value = max(0, min(100, int(value)))
        await self.evaluate("model.video.setBrightness(%d)" % value)

    async def set_contrast(self, value: int) -> None:
        """Set the contrast, clamped to 0..100."""
        value = max(0, min(100, int(value)))
        await self.evaluate("model.video.setContrast(%d)" % value)

    async def set_colour_intensity(self, value: int) -> None:
        """Set the colour intensity, clamped to 0..100."""
        value = max(0, min(100, int(value)))
        await self.evaluate("model.video.setColourIntensity(%d)" % value)

    async def set_sharpness(self, value: int) -> None:
        """Set the sharpness, clamped to 0..100."""
        value = max(0, min(100, int(value)))
        await self.evaluate("model.video.setSharpness(%d)" % value)

    async def set_eco_sensor(self, on: bool) -> None:
        """Enable or disable the eco sensor."""
        await self.evaluate(
            "model.video.setEcoSensor(%d)" % (1 if on else 0)
        )

    async def set_freeze(self, on: bool) -> None:
        """Enable or disable the picture freeze."""
        await self.evaluate("model.video.setFreeze(%d)" % (1 if on else 0))

    async def send_key(self, code: int) -> None:
        """Dispatch a DOM keyboard event with the given key code."""
        await self.evaluate(_KEY_EXPRESSION.replace("__CODE__", str(int(code))))

    async def volume_up(self) -> None:
        """Press the volume-up key."""
        await self.send_key(KEY_VOLUME_UP)

    async def volume_down(self) -> None:
        """Press the volume-down key."""
        await self.send_key(KEY_VOLUME_DOWN)

    async def power_off(self) -> None:
        """Put the TV into standby."""
        await self.evaluate(_POWER_OFF_EXPRESSION)

    async def start_app(self, name: str) -> None:
        """Launch the application with the given name."""
        await self.evaluate("StartApplication(" + json.dumps(name) + ")")
