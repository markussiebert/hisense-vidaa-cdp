"""Shared entity helpers for the Hisense VIDAA (CDP) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cdp import HisenseCDP
from .const import CONF_HOST, CONF_MAC, DOMAIN
from .coordinator import HisenseCoordinator


class HisenseEntity(CoordinatorEntity[HisenseCoordinator]):
    """Base class providing shared device info, ids and availability."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HisenseCoordinator,
        client: HisenseCDP,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity with its config entry and data key."""
        super().__init__(coordinator)
        self.client = client
        self._entry = entry
        self._key = key
        unique_id = entry.data.get(CONF_MAC) or entry.data[CONF_HOST]
        self._attr_unique_id = f"{DOMAIN}_{unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info, grouping all entities under one device."""
        unique_id = (
            self._entry.data.get(CONF_MAC) or self._entry.data[CONF_HOST]
        )
        return DeviceInfo(
            identifiers={(DOMAIN, f"{DOMAIN}_{unique_id}")},
            name=self._entry.title,
            manufacturer="Hisense",
            model="VIDAA (CDP)",
        )

    @property
    def available(self) -> bool:
        """Return True when the TV is on and reports this control."""
        data = self.coordinator.data or {}
        return (
            self.coordinator.last_update_success
            and data.get("power") == "on"
            and self._key in data
        )
