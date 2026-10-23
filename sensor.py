"""Sensor：环境光照（厂商确认为 lux 单位）."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
        async_add_entities([RFPLightSensor(device, entry)])


class RFPLightSensor(SensorEntity):
    """环境光照（0x51 光敏采样，单位 lux）."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "lx"
    _attr_has_entity_name = True

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_name = "Light"

    @property
    def native_value(self) -> int | None:
        return self._device.light_raw

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._device.entry.entry_id), self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()
