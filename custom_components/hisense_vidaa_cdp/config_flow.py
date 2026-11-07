"""Config flow for the Hisense VIDAA (CDP) integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import CDP_PORT, CONF_BROADCAST, CONF_HOST, CONF_MAC, CONF_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Hisense TV"
VALIDATION_TIMEOUT = 4

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_MAC): str,
        vol.Optional(CONF_BROADCAST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


async def _async_host_reachable(host: str) -> bool:
    """Return True when the host is reachable at the IP level.

    A refused connection still means the device is there (the TV is simply in
    standby or the DevTools server is not up yet). Only timeouts and DNS
    failures count as unreachable.
    """
    url = f"http://{host}:{CDP_PORT}/json/version"
    timeout = aiohttp.ClientTimeout(total=VALIDATION_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                await response.read()
    except aiohttp.ClientConnectorError as err:
        # Connection refused = something answered on that IP/port.
        return isinstance(err.os_error, ConnectionRefusedError)
    except (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError, OSError):
        return False
    return True


class HisenseVidaaCDPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hisense VIDAA (CDP)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            mac = (user_input.get(CONF_MAC) or "").strip()
            broadcast = (user_input.get(CONF_BROADCAST) or "").strip()
            name = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_NAME

            if await _async_host_reachable(host):
                await self.async_set_unique_id(mac or host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_MAC: mac,
                        CONF_BROADCAST: broadcast,
                        CONF_NAME: name,
                    },
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )
