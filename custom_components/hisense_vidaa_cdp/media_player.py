"""Media player platform for the Hisense VIDAA (CDP) integration."""

from __future__ import annotations

import logging
from typing import Any

from wakeonlan import send_magic_packet

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .cdp import HisenseCDP
from .const import (
    CONF_BROADCAST,
    CONF_HOST,
    CONF_MAC,
    DOMAIN,
    SOURCE_BY_INDEX,
    SOURCES,
)
from .coordinator import HisenseCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense media player from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HisenseMediaPlayer(data["coordinator"], data["client"], entry)]
    )


class HisenseMediaPlayer(
    CoordinatorEntity[HisenseCoordinator], MediaPlayerEntity
):
    """Representation of a Hisense VIDAA TV."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )
    _attr_source_list = list(SOURCES)

    def __init__(
        self,
        coordinator: HisenseCoordinator,
        client: HisenseCDP,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator)
        self.client = client
        self._entry = entry
        self._mac: str | None = entry.data.get(CONF_MAC) or None
        self._broadcast: str | None = entry.data.get(CONF_BROADCAST) or None

        unique_id = entry.data.get(CONF_MAC) or entry.data[CONF_HOST]
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._entry.title,
            manufacturer="Hisense",
            model="VIDAA (CDP)",
        )

    @property
    def available(self) -> bool:
        """Return True when the TV state is known.

        Standby is represented as ``power == "off"`` in the coordinator data,
        so a powered-off TV still counts as available. Hard update failures
        make the entity unavailable through the coordinator.
        """
        return self.coordinator.last_update_success

    @property
    def _is_on(self) -> bool:
        """Return True when the TV is powered on."""
        return self.coordinator.data.get("power") == "on"

    @property
    def state(self) -> MediaPlayerState:
        """Return the current power state."""
        return MediaPlayerState.ON if self._is_on else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0..1)."""
        if not self._is_on:
            return None
        volume = self.coordinator.data.get("volume")
        if volume is None:
            return None
        return volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True when the TV is muted."""
        if not self._is_on:
            return None
        return bool(self.coordinator.data.get("mute"))

    @property
    def source(self) -> str | None:
        """Return the currently selected source label."""
        if not self._is_on:
            return None
        return SOURCE_BY_INDEX.get(self.coordinator.data.get("source"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the current channel information."""
        attrs: dict[str, Any] = {}
        if (channel_number := self.coordinator.data.get("channel_number")) is not None:
            attrs["channel_number"] = channel_number
        if (channel_name := self.coordinator.data.get("channel_name")) is not None:
            attrs["channel_name"] = channel_name
        return attrs

    @property
    def media_title(self) -> str | None:
        """Return the current channel name while watching TV."""
        if self.source != "TV":
            return None
        return self.coordinator.data.get("channel_name")

    async def async_turn_off(self) -> None:
        """Put the TV into standby."""
        await self.client.power_off()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Wake the TV with a Wake-on-LAN magic packet."""
        if not self._mac:
            _LOGGER.warning(
                "Cannot turn on %s: no MAC address configured", self._entry.title
            )
            return

        mac = self._mac
        broadcast = self._broadcast

        def _send_magic_packet() -> None:
            if broadcast:
                send_magic_packet(mac, ip_address=broadcast)
            else:
                send_magic_packet(mac)

        await self.hass.async_add_executor_job(_send_magic_packet)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the absolute volume (0..1)."""
        await self.client.set_volume(round(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Increase the volume."""
        await self.client.volume_up()
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Decrease the volume."""
        await self.client.volume_down()
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the TV."""
        await self.client.set_mute(mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Switch to the given input source."""
        index = SOURCES.get(source)
        if index is None:
            _LOGGER.warning("Unknown source: %s", source)
            return
        await self.client.set_source(index)
        await self.coordinator.async_request_refresh()

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Launch an app on the TV by name."""
        await self.client.start_app(media_id)
        await self.coordinator.async_request_refresh()
