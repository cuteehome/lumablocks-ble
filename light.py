"""Light：双色温灯（0x73 开关 / 0x74 亮度 / 0x75 色温）."""

from __future__ import annotations

import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import signal_update
from .const import CCT_MAX_K, CCT_MIN_K
from .connection import RFPDevice
from .rfp24_protocol import Capability

_LOGGER = logging.getLogger(__name__)

MAX_HA_BRIGHTNESS = 255


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: RFPDevice = hass.data["lumablocks_ble"][entry.entry_id]
    if device.capabilities.get(Capability.LIGHT):
        async_add_entities([RFPColorTempLight(device, entry)])


def _cct_pct_to_kelvin(pct: int) -> int:
    """协议 0(全暖)~100(全冷) → 开尔文（线性）."""
    return round(CCT_MIN_K + (CCT_MAX_K - CCT_MIN_K) * pct / 100)


def _kelvin_to_cct_pct(kelvin: int) -> int:
    return round((kelvin - CCT_MIN_K) * 100 / (CCT_MAX_K - CCT_MIN_K))


class RFPColorTempLight(LightEntity):
    """双色温灯."""

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = CCT_MIN_K
    _attr_max_color_temp_kelvin = CCT_MAX_K
    _attr_has_entity_name = True

    def __init__(self, device: RFPDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_name = "Light"

    @property
    def is_on(self) -> bool | None:
        return self._device.light_on

    @property
    def brightness(self) -> int | None:
        """HA 0-255 ← 协议 0-100."""
        if self._device.brightness is None:
            return None
        return round(self._device.brightness * MAX_HA_BRIGHTNESS / 100)

    @property
    def color_temp_kelvin(self) -> int | None:
        if self._device.cct is None:
            return None
        return _cct_pct_to_kelvin(self._device.cct)

    async def async_turn_on(self, **kwargs) -> None:  # noqa: ANN003
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        on = True if (brightness is None and kelvin is None) else None
        await self._device.async_set_light(
            on=on,
            brightness=None if brightness is None else round(brightness * 100 / MAX_HA_BRIGHTNESS),
            cct=None if kelvin is None else _kelvin_to_cct_pct(int(kelvin)),
        )

    async def async_turn_off(self, **kwargs) -> None:  # noqa: ANN003
        await self._device.async_set_light(on=False)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._device.entry.entry_id), self._async_update
            )
        )

    @callback
    def _async_update(self) -> None:
        self.async_write_ha_state()
