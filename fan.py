"""Fan：风扇灯的风扇（0x70 开关 / 0x71 转速 / 0x72 正反转）."""

from __future__ import annotations

import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import signal_update
from .connection import RFPDevice
from .rfp24_protocol import Capability

_LOGGER = logging.getLogger(__name__)

# 协议 0x71: 0=停转, 1~9 档位递增
SPEED_OFF = 0
SPEED_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: RFPDevice = hass.data["lumablocks_ble"][entry.entry_id]
    if device.capabilities.get(Capability.FAN):
        async_add_entities([RFPFan(device, entry)])


class RFPFan(FanEntity):
    """风扇（9 档 + 正反转）."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(SPEED_ORDER)
    _attr_has_entity_name = True

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._attr_name = "Fan"

    @property
    def is_on(self) -> bool | None:
        return self._device.fan_on

    @property
    def percentage(self) -> int | None:
        """HA 0-100 ← 协议档位 1~9."""
        if self._device.fan_speed is None or self._device.fan_speed == SPEED_OFF:
            return None if self._device.fan_speed is None else 0
        return ordered_list_item_to_percentage(SPEED_ORDER, self._device.fan_speed)

    @property
    def oscillating(self) -> bool | None:
        """True=正转(1), False=反转(0)."""
        if self._device.fan_direction is None:
            return None
        return bool(self._device.fan_direction)

    async def async_turn_on(self, percentage: int | None = None,
                            preset_mode: str | None = None, **kwargs) -> None:  # noqa: ANN003
        if percentage is not None:
            speed = percentage_to_ordered_list_item(SPEED_ORDER, percentage)
            await self._device.async_set_fan_speed(int(speed))
        else:
            await self._device.async_set_fan_switch(True)

    async def async_turn_off(self, **kwargs) -> None:  # noqa: ANN003
        await self._device.async_set_fan_switch(False)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self._device.async_set_fan_speed(SPEED_OFF)
        else:
            speed = percentage_to_ordered_list_item(SPEED_ORDER, percentage)
            await self._device.async_set_fan_speed(int(speed))

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._device.async_set_fan_direction(oscillating)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._device.entry.entry_id), self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()
