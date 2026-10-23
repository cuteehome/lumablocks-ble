"""Select：探测档位（0x3A 参数档位，0/1/2 三档）."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import signal_update
from .connection import RFPDevice
from .rfp24_protocol import Capability

# 0x3A: 0=最灵敏, 1=标准(默认), 2=最不灵敏
GEAR_OPTIONS = ["0", "1", "2"]
GEAR_LABELS = {"0": "最灵敏", "1": "标准", "2": "最不灵敏"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: RFPDevice = hass.data["lumablocks_ble"][entry.entry_id]
    if device.capabilities.get(Capability.PRESENCE):
        async_add_entities([RFPGearSelect(device, entry)])


class RFPGearSelect(SelectEntity):
    """雷达探测档位."""

    _attr_options = GEAR_OPTIONS
    _attr_has_entity_name = True
    _attr_icon = "mdi:tune"

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_gear"
        self._attr_name = "Sensitivity Gear"

    @property
    def current_option(self) -> str | None:
        if self._device.gear is None:
            return None
        return str(self._device.gear)

    async def async_select_option(self, option: str) -> None:
        if await self._device.async_set_gear(int(option)):
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        cur = self.current_option
        if cur is None:
            return {}
        return {"label": GEAR_LABELS.get(cur, cur)}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._device.entry.entry_id), self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()
