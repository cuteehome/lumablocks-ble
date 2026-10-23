"""Binary sensor：目标存在（0x51 target）."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import signal_update
from .connection import RFPDevice
from .rfp24_protocol import Capability


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: RFPDevice = hass.data["lumablocks_ble"][entry.entry_id]
    if device.capabilities.get(Capability.PRESENCE):
        async_add_entities([RFPOccupancySensor(device, entry)])


class RFPOccupancySensor(BinarySensorEntity):
    """雷达人体存在."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_occupancy"
        self._attr_name = "Occupancy"

    @property
    def is_on(self) -> bool | None:
        return self._device.target

    @property
    def available(self) -> bool:
        return self._device.target is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._device.entry.entry_id), self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()
