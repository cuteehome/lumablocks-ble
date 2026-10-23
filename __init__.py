"""LumaBlocks BLE integration：设备会话与生命周期管理."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_register_callback,
    BluetoothScanningMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, RX_CHAR_UUID
from .connection import RFPDevice, SIGNAL_UPDATE

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.LIGHT, Platform.NUMBER, Platform.SELECT, Platform.FAN]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a RFP device from a config entry."""
    address = entry.unique_id or entry.data["address"]
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"无法通过蓝牙代理找到设备 {address}")

    device = RFPDevice(hass, entry, ble_device)
    try:
        await device.async_setup()
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(f"设备初始化失败: {err}") from err

    # 能力识别（而非名称前缀）：连接探测后无任何已知能力的设备视为
    # 非 LumaBlocks 设备，中止 setup（不会留在 HA 设备列表）
    from .rfp24_protocol import Capability
    if not any(device.capabilities.values()):
        _LOGGER.warning(
            "设备 %s 无灯/风扇/存在能力，不作为 LumaBlocks 设备接入",
            entry.data.get("name"),
        )
        raise ConfigEntryNotReady(
            "能力探测未发现灯/风扇/存在传感器，忽略该设备"
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device

    # 广播回归时刷新 ble_device（代理漫游/设备重连）
    @callback
    def _on_discovery(_service_info, _change):
        dev = async_ble_device_from_address(hass, address, connectable=True)
        if dev is not None:
            device.update_ble_device(dev)

    entry.async_on_unload(
        async_register_callback(
            hass,
            _on_discovery,
            {"local_name": entry.data.get("local_name", "")},
            BluetoothScanningMode.ACTIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device: RFPDevice | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if device is not None:
        await device.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def signal_update(entry_id: str) -> str:
    """每设备的更新信号."""
    return f"{SIGNAL_UPDATE}_{entry_id}"


def send_update(hass: HomeAssistant, entry_id: str) -> None:
    async_dispatcher_send(hass, signal_update(entry_id))
