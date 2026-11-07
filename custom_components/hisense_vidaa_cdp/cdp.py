"""Async Chrome DevTools Protocol client for Hisense VIDAA TVs.

The TV exposes a CDP endpoint on TCP port 9223. This module only talks to that
endpoint over HTTP/WebSocket using aiohttp; it has no Home Assistant imports so
it can be exercised standalone (see ``test_cdp.py``).
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
EVALUATE_TIMEOUT = 5
# Budget for fetching the CDP target list, in seconds.
TARGET_LIST_TIMEOUT = 4

_STATUS_EXPRESSION = (
    "(function(){var out={};"
    "try{out.source=window.model.source.getCurrentSource();}catch(e){}"
    "try{out.volume=window.model.sound.getMainVolume();}catch(e){}"
    "try{out.mute=window.model.sound.getMainMute();}catch(e){}"
    "try{var c=window.liveTV.getCurrentChannelInfo();"
    "if(c){out.channel_number=c.number;out.channel_name=c.name;}}catch(e){}"
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


class HisenseCDP:
    """Minimal CDP client for a Hisense VIDAA TV."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Store the TV host and the shared aiohttp session."""
        self.host = host
        self.session = session
        self.base_url = f"http://{host}:{CDP_PORT}"

    async def _ws_url(self) -> str:
        """Return the WebSocket debugger URL of the TV's CDP page target.

        Raises ``TVOffline`` when the TV does not answer or exposes no page.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=TARGET_LIST_TIMEOUT)
            async with self.session.get(
                f"{self.base_url}/json/list", timeout=timeout
            ) as resp:
                targets = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise TVOffline(f"TV at {self.host} is unreachable: {err}") from err

        if not isinstance(targets, list) or not targets:
            raise TVOffline(f"TV at {self.host} exposes no CDP targets")

        target = next(
            (t for t in targets if isinstance(t, dict) and t.get("type") == "page"),
            targets[0],
        )
        if not isinstance(target, dict) or not target.get("webSocketDebuggerUrl"):
            raise TVOffline(f"TV at {self.host} exposes no WebSocket debugger URL")

        return str(target["webSocketDebuggerUrl"])

    async def evaluate(self, expression: str) -> Any:
        """Evaluate ``expression`` in the TV UI and return its value."""
        ws_url = await self._ws_url()

        try:
            async with self.session.ws_connect(
                ws_url, timeout=EVALUATE_TIMEOUT
            ) as ws:
                await ws.send_json(
                    {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": expression,
                            "returnByValue": True,
                        },
                    }
                )
                reply = await self._wait_for_reply(ws)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            raise TVOffline(f"TV at {self.host} is unreachable: {err}") from err

        if "error" in reply:
            raise RuntimeError(f"CDP error: {reply['error']}")

        result = reply.get("result", {}).get("result", {})
        exception = reply.get("result", {}).get("exceptionDetails")
        if exception or result.get("wasThrown"):
            detail = ""
            if exception:
                detail = (
                    (exception.get("exception") or {}).get("description")
                    or exception.get("text")
                    or str(exception)
                )
            raise RuntimeError(f"JavaScript error: {detail or 'unknown error'}")

        return result.get("value")

    async def _wait_for_reply(
        self, ws: aiohttp.ClientWebSocketResponse
    ) -> dict[str, Any]:
        """Read messages until the reply with ``id == 1`` arrives."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + EVALUATE_TIMEOUT
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError("timed out waiting for CDP reply")
            try:
                msg = await ws.receive_json(timeout=remaining)
            except (ValueError, TypeError):
                # Non-JSON or binary frame (e.g. a CDP event): ignore it.
                continue
            if isinstance(msg, dict) and msg.get("id") == 1:
                return msg

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
