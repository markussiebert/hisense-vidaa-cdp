"""Data update coordinator for the Hisense VIDAA (CDP) integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .cdp import HisenseCDP, TVOffline
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HisenseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the TV's CDP endpoint and expose its state.

    Standby is a normal operating state: when the CDP port does not answer the
    coordinator reports ``{"power": "off"}`` instead of failing the update.
    """

    def __init__(self, hass: HomeAssistant, client: HisenseCDP) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the current state from the TV."""
        try:
            status = await self.client.get_status()
        except TVOffline:
            # Standby is expected, not an error.
            return {"power": "off"}
        except Exception as err:  # noqa: BLE001 - report any other failure to HA
            raise UpdateFailed(f"Error communicating with the TV: {err}") from err

        return {"power": "on", **status}
