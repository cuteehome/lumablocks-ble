"""Config flow for LumaBlocks BLE（蓝牙发现 + 手动添加）."""

from __future__ import annotations

import logging

from homeassistant.components.bluetooth import (
    async_discovered_service_info,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOCAL_NAME_PREFIXES

_LOGGER = logging.getLogger(__name__)


class RFPBLEFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle the RFP BLE config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info) -> FlowResult:
        """蓝牙发现入口（local_name 匹配 RF-P*）."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered[discovery_info.address] = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, _user_input=None) -> FlowResult:
        """确认添加."""
        discovery_info = list(self._discovered.values())[0]
        name = discovery_info.name
        return self.async_create_entry(
            title=name,
            data={"address": discovery_info.address, "name": name, "local_name": name},
        )

    async def async_step_user(self, _user_input=None) -> FlowResult:
        """手动添加：列出广播名匹配候选规则的设备（RF 前缀或 _CW/_FAN 结尾）."""
        current = self._get_current_entry_addresses()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current or not info.name:
                continue
            if any(info.name.startswith(p) for p in LOCAL_NAME_PREFIXES) or info.name.endswith(("_CW", "_FAN")):
                self._discovered[info.address] = info
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        if len(self._discovered) == 1:
            info = list(self._discovered.values())[0]
            await self.async_set_unique_id(info.address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=info.name,
                data={"address": info.address, "name": info.name, "local_name": info.name},
            )
        # 多台：让用户选
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol_schema(list(self._discovered.values())),
        )

    async def async_step_pick_device(self, user_input=None) -> FlowResult:
        if user_input is not None:
            address = user_input["address"]
            info = self._discovered[address]
            await self.async_set_unique_id(info.address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=info.name,
                data={"address": info.address, "name": info.name, "local_name": info.name},
            )
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol_schema(list(self._discovered.values())),
        )

    def _get_current_entry_addresses(self) -> set[str]:
        return {
            entry.unique_id
            for entry in self._async_current_entries(include_ignore=False)
            if entry.unique_id
        }


def vol_schema(infos):
    import voluptuous as vol

    return vol.Schema(
        {vol.Required("address"): vol.In({i.address: f"{i.name} ({i.address})" for i in infos})}
    )
