"""Number platform for the Hisense VIDAA (CDP) integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cdp import HisenseCDP
from .const import DOMAIN
from .coordinator import HisenseCoordinator
from .entity import HisenseEntity

# (data key, display name, client setter method)
PICTURE_CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("backlight", "Backlight", "set_backlight"),
    ("brightness", "Brightness", "set_brightness"),
    ("contrast", "Contrast", "set_contrast"),
    ("colour_intensity", "Colour", "set_colour_intensity"),
    ("sharpness", "Sharpness", "set_sharpness"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense picture control numbers from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    async_add_entities(
        HisensePictureNumber(coordinator, client, entry, key, name, setter)
        for key, name, setter in PICTURE_CONTROLS
    )


class HisensePictureNumber(HisenseEntity, NumberEntity):
    """A picture control exposed as a slider."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HisenseCoordinator,
        client: HisenseCDP,
        entry: ConfigEntry,
        key: str,
        name: str,
        setter: str,
    ) -> None:
        """Initialize the picture control number entity."""
        super().__init__(coordinator, client, entry, key)
        self._attr_name = name
        self._setter = setter

    @property
    def native_value(self) -> float | None:
        """Return the current picture control value."""
        value = (self.coordinator.data or {}).get(self._key)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the picture control to the given value."""
        await getattr(self.client, self._setter)(int(value))
        await self.coordinator.async_request_refresh()
