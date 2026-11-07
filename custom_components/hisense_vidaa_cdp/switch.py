"""Switch platform for the Hisense VIDAA (CDP) integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .cdp import HisenseCDP
from .const import DOMAIN
from .coordinator import HisenseCoordinator
from .entity import HisenseEntity

# (data key, display name, client setter method)
SWITCHES: tuple[tuple[str, str, str], ...] = (
    ("eco_sensor", "Eco Sensor", "set_eco_sensor"),
    ("freeze", "Freeze", "set_freeze"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    async_add_entities(
        HisenseSwitch(coordinator, client, entry, key, name, setter)
        for key, name, setter in SWITCHES
    )


class HisenseSwitch(HisenseEntity, SwitchEntity):
    """A TV picture option exposed as a switch."""

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
        """Initialize the switch entity."""
        super().__init__(coordinator, client, entry, key)
        self._attr_name = name
        self._setter = setter

    @property
    def is_on(self) -> bool:
        """Return True when the option is enabled."""
        return bool((self.coordinator.data or {}).get(self._key))

    async def _async_set(self, on: bool) -> None:
        """Apply the given state to the TV."""
        await getattr(self.client, self._setter)(on)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Enable the option."""
        await self._async_set(True)

    async def async_turn_off(self) -> None:
        """Disable the option."""
        await self._async_set(False)
