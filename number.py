"""Number：雷达参数（最远探测距离 / 无人判断时间）."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import signal_update
from .connection import RFPDevice
from .rfp24_protocol import Capability

# 0x32 最远距离: uint16 mm, 0~9750, 默认 6000
# 0x31 持续时间(无人判断时间): uint32 ms, 厂商约束最短 3s, 上限 600s, 默认 12s


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: RFPDevice = hass.data["lumablocks_ble"][entry.entry_id]
    if device.capabilities.get(Capability.PRESENCE):
        async_add_entities([RFPMaxDistanceNumber(device, entry), RFPHoldTimeNumber(device, entry)])


class _RFPNumberBase(NumberEntity):
    """公共基类."""

    _attr_mode = NumberMode.BOX
    _attr_has_entity_name = True

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._entry_id = entry.entry_id

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._entry_id), self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()


class RFPMaxDistanceNumber(_RFPNumberBase):
    """最远探测距离（毫米，超过该距离的目标不探测）."""

    _attr_native_min_value = 0
    _attr_native_max_value = 9750
    _attr_native_step = 50
    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_icon = "mdi:radar"

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{self._entry_id}_max_distance"
        self._attr_name = "Max Distance"

    @property
    def native_value(self) -> float | None:
        return self._device.max_distance

    async def async_set_native_value(self, value: float) -> None:
        if await self._device.async_set_max_distance(int(value)):
            self.async_write_ha_state()


class RFPHoldTimeNumber(_RFPNumberBase):
    """无人判断时间（秒，检测不到人后保持占用的时长，最短 3 秒）."""

    _attr_native_min_value = 3
    _attr_native_max_value = 600
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{self._entry_id}_hold_time"
        self._attr_name = "Hold Time"

    @property
    def native_value(self) -> float | None:
        return self._device.hold_time

    async def async_set_native_value(self, value: float) -> None:
        if await self._device.async_set_hold_time(int(value)):
            self.async_write_ha_state()
