"""RFP 设备 GATT 会话：连接、协议解析、命令下发."""

from __future__ import annotations

import asyncio
import logging

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CMD_TIMEOUT, RX_CHAR_UUID, TX_CHAR_UUID
from .rfp24_protocol import (
    Capability,
    MsgID,
    build_host_frame,
    decode_query_response,
    decode_response,
    decode_spectrum_report,
    decode_target_light_report,
    encode_brightness,
    encode_cct,
    encode_fan_direction,
    encode_fan_speed,
    encode_fan_switch,
    encode_light_switch,
    encode_query,
    encode_report_config,
    extract_frames,
    probe_queries,
)

_LOGGER = logging.getLogger(__name__)
SIGNAL_UPDATE = "lumablocks_ble_update"

# 灯状态回读参数
_LIGHT_STATE_PARAMS = [
    MsgID.LIGHT_SWITCH,
    MsgID.LIGHT_BRIGHTNESS,
    MsgID.LIGHT_CCT,
]


# 雷达参数（存在能力设备回读/设置）
_PRESENCE_PARAMS = [
    MsgID.SET_LED_DURATION,       # 0x31 无人判断时间
    MsgID.SET_MAX_DISTANCE,       # 0x32 最远距离
    MsgID.SET_PARAM_GEAR,         # 0x3A 探测档位
]

# 风扇状态回读参数
_FAN_STATE_PARAMS = [
    MsgID.FAN_SWITCH,           # 0x70
    MsgID.FAN_SPEED,            # 0x71
    MsgID.FAN_DIRECTION,        # 0x72
]


class RFPDevice:
    """一台 RFP/RFM 子设备的连接会话."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, ble_device) -> None:
        self.hass = hass
        self.entry = entry
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._leftover = b""
        self._lock = asyncio.Lock()  # 串行化命令（连接槽有限）
        # 待处理的 0x40 查询：future 完成时携带 QueryResult 或 Ack(错误)
        self._pending_query: asyncio.Future | None = None
        self._pending_ack: asyncio.Future | None = None

        # 能力（连接探测后填充）
        self.capabilities: dict[Capability, bool] = {}

        # 上报状态缓存（实体从这里读）
        self.target: bool | None = None
        self.light_raw: int | None = None          # lux
        self.light_on: bool | None = None
        self.brightness: int | None = None          # 0-100
        self.cct: int | None = None                 # 0-100（0全暖）
        self.max_distance: int | None = None        # mm
        self.hold_time: int | None = None           # 秒
        self.gear: int | None = None                # 0/1/2
        self.fan_on: bool | None = None
        self.fan_speed: int | None = None             # 0~9
        self.fan_direction: int | None = None         # 1正转/0反转

    # ------------------------------------------------------------------ 生命周期
    async def async_setup(self) -> None:
        """连接并完成握手：停上报 → 探测能力 → 回读灯状态 → 重启上报.

        厂商固件行为：0x51 连续上报进行中 0x40 查询不响应（真机实测），
        因此探测前必须先 0x54 停止上报。
        """
        await self._ensure_connected()
        await self._send_raw(build_host_frame(MsgID.STOP_REPORT))
        await asyncio.sleep(0.3)
        await self._probe_capabilities()
        await self._restore_light_state()
        await self._start_reporting()

    async def async_refresh(self) -> None:
        """手动刷新（扫描按钮触发）：重新握手、探测能力、回读全部状态."""
        try:
            if self._client is None or not self._client.is_connected:
                await self._ensure_connected()
            await self._send_raw(build_host_frame(MsgID.STOP_REPORT))
            await asyncio.sleep(0.3)
            await self._probe_capabilities()
            await self._restore_light_state()
            await self._start_reporting()
            _LOGGER.info("手动刷新完成: %s", self.entry.data.get("name"))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("手动刷新失败: %s", err)
            self._client = None  # 连接已坏，下轮自动重连

    async def async_shutdown(self) -> None:
        if self._client is not None and self._client.is_connected:
            try:
                await self._client.write_gatt_char(
                    TX_CHAR_UUID,
                    build_host_frame(MsgID.STOP_REPORT),
                    response=False,
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._client = None

    def update_ble_device(self, ble_device) -> None:
        """代理漫游后刷新底层 BLE 设备句柄."""
        self._ble_device = ble_device

    # ------------------------------------------------------------------ 连接
    async def _ensure_connected(self) -> BleakClient:
        if self._client is not None and self._client.is_connected:
            return self._client
        # bleak-retry-connector 4.x：签名无 hass 参数（client_class, device, name, ...）
        client = await establish_connection(
            BleakClient,
            self._ble_device,
            self.entry.data.get("name", "RFP device"),
            max_attempts=3,
        )
        await client.start_notify(RX_CHAR_UUID, self._on_notification)
        self._client = client
        self._leftover = b""
        return client

    # ------------------------------------------------------------------ 通知
    def _on_notification(self, _char, data: bytearray) -> None:
        frames, self._leftover = extract_frames(bytes(data) + self._leftover)
        for f in frames:
            try:
                self._handle_frame(f)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("解析帧失败: %s", f.payload.hex())

    def _handle_frame(self, f) -> None:
        if f.msg_id == MsgID.REPORT_TARGET_LIGHT:
            rpt = decode_target_light_report(f.payload)
            self.target = rpt.target
            self.light_raw = rpt.light_raw
            self._notify()
        elif f.msg_id in (MsgID.REPORT_MICRO_SPECTRUM, MsgID.REPORT_PRESENCE_SPECTRUM):
            decode_spectrum_report(f.payload)  # 校验，暂不落地实体
        elif f.msg_id == MsgID.QUERY_PARAMS:
            if len(f.payload) > 1:  # 查询成功（参数+值）
                try:
                    self._apply_query_result(decode_query_response(f.payload))
                except ValueError:
                    pass
                if self._pending_query is not None and not self._pending_query.done():
                    self._pending_query.set_result(True)
                self._notify()
            else:  # 单字节 = 错误码（BAD_MSGID 等）
                ack = decode_response(f.msg_id, f.payload)
                if self._pending_query is not None and not self._pending_query.done():
                    self._pending_query.set_result(False)
                if ack is not None and not ack.ok:
                    _LOGGER.debug("0x40 查询被拒: %s", ack.error.name)
        elif (ack := decode_response(f.msg_id, f.payload)) is not None:
            if self._pending_ack is not None and not self._pending_ack.done():
                self._pending_ack.set_result(ack)
            if not ack.ok:
                _LOGGER.warning("设备 NACK 0x%02X: %s", f.msg_id, ack.error.name)

    def _apply_query_result(self, res) -> None:
        try:
            if MsgID.LIGHT_SWITCH in res.values:
                self.light_on = res.get_u8(MsgID.LIGHT_SWITCH) == 1
            if MsgID.LIGHT_BRIGHTNESS in res.values:
                self.brightness = res.get_u8(MsgID.LIGHT_BRIGHTNESS)
            if MsgID.LIGHT_CCT in res.values:
                self.cct = res.get_u8(MsgID.LIGHT_CCT)
            if MsgID.SET_MAX_DISTANCE in res.values:
                self.max_distance = res.get_u16(MsgID.SET_MAX_DISTANCE)
            if MsgID.SET_PARAM_GEAR in res.values:
                self.gear = res.get_u8(MsgID.SET_PARAM_GEAR)
            if MsgID.FAN_SWITCH in res.values:
                self.fan_on = res.get_u8(MsgID.FAN_SWITCH) == 1
            if MsgID.FAN_SPEED in res.values:
                self.fan_speed = res.get_u8(MsgID.FAN_SPEED)
            if MsgID.FAN_DIRECTION in res.values:
                self.fan_direction = res.get_u8(MsgID.FAN_DIRECTION)
            if MsgID.SET_LED_DURATION in res.values:
                # uint32 ms → 秒
                raw = res.values[MsgID.SET_LED_DURATION]
                if len(raw) == 4:
                    self.hold_time = int.from_bytes(raw, "big") / 1000
        except (KeyError, ValueError):
            pass

    def _notify(self) -> None:
        from . import send_update

        send_update(self.hass, self.entry.entry_id)

    # ------------------------------------------------------------------ 探测/上报
    async def _query(self, param_ids: list[MsgID], timeout: float = 2.0) -> bool:
        """发送 0x40 查询并等待结果（True=返回值 / False=错误码）."""
        client = await self._ensure_connected()
        loop = asyncio.get_running_loop()
        # future 必须在锁内创建，否则并发调用互相覆盖（wait_for(None) 崩溃 / ACK 错配）
        async with self._lock:
            self._pending_query = loop.create_future()
            try:
                await client.write_gatt_char(
                    TX_CHAR_UUID,
                    build_host_frame(MsgID.QUERY_PARAMS, encode_query(param_ids)),
                    response=False,
                )
                return await asyncio.wait_for(self._pending_query, timeout)
            except asyncio.TimeoutError:
                _LOGGER.warning("0x40 查询超时: %s", [hex(int(p)) for p in param_ids])
                return False
            finally:
                self._pending_query = None

    async def _probe_capabilities(self) -> None:
        """按厂商确认的字段逐个探测：灯=0x75 风扇=0x71 存在=0x38."""
        self.capabilities = {}
        for spec in probe_queries():
            ok = await self._query([_param_of(spec)])
            self.capabilities[spec.capability] = ok
        _LOGGER.info(
            "设备 %s 能力: %s",
            self.entry.data.get("name"),
            {c.name: v for c, v in self.capabilities.items()},
        )

    async def _restore_light_state(self) -> None:
        if self.capabilities.get(Capability.LIGHT):
            await self._query(_LIGHT_STATE_PARAMS)
        if self.capabilities.get(Capability.FAN):
            await self._query(_FAN_STATE_PARAMS)
        if self.capabilities.get(Capability.PRESENCE):
            await self._query(_PRESENCE_PARAMS)

    async def _start_reporting(self) -> None:
        if self.capabilities.get(Capability.PRESENCE):
            await self._send_cmd(MsgID.SET_REPORT_CONFIG, encode_report_config())

    # ------------------------------------------------------------------ 命令
    async def _send_raw(self, frame: bytes) -> None:
        """发送原始帧（不等待 ACK）."""
        client = await self._ensure_connected()
        async with self._lock:
            await client.write_gatt_char(TX_CHAR_UUID, frame, response=False)

    async def _send_cmd(self, msg_id: MsgID, payload: bytes) -> bool:
        """发送命令帧并等待 ACK."""
        client = await self._ensure_connected()
        loop = asyncio.get_running_loop()
        async with self._lock:
            # future 必须在锁内创建，否则并发调用互相覆盖（wait_for(None) 崩溃 / ACK 错配）
            self._pending_ack = loop.create_future()
            try:
                await client.write_gatt_char(
                    TX_CHAR_UUID, build_host_frame(msg_id, payload), response=False
                )
                ack = await asyncio.wait_for(self._pending_ack, CMD_TIMEOUT)
                return ack.ok
            except asyncio.TimeoutError:
                _LOGGER.warning("命令 0x%02X 等待 ACK 超时", msg_id)
                return False
            finally:
                self._pending_ack = None

    # ------------------------------------------------------------------ 实体接口
    async def async_set_light(self, on: bool | None = None,
                              brightness: int | None = None,
                              cct: int | None = None) -> bool:
        """设置灯（None 的参数保持不变）."""
        if not self.capabilities.get(Capability.LIGHT):
            return False
        ok = True
        if on is not None:
            if await self._send_cmd(MsgID.LIGHT_SWITCH, encode_light_switch(on)):
                self.light_on = on
            else:
                ok = False
        if brightness is not None:
            if await self._send_cmd(MsgID.LIGHT_BRIGHTNESS, encode_brightness(brightness)):
                self.brightness = brightness
            else:
                ok = False
        if cct is not None:
            if await self._send_cmd(MsgID.LIGHT_CCT, encode_cct(cct)):
                self.cct = cct
            else:
                ok = False
        self._notify()
        return ok

    async def async_set_sensitivity(self, value: int) -> bool:
        return await self._send_cmd(MsgID.SET_SENSITIVITY, bytes([value]))

    async def async_set_max_distance(self, mm: int) -> bool:
        """0x32 最远距离（毫米，0~9750）."""
        ok = await self._send_cmd(
            MsgID.SET_MAX_DISTANCE, (mm & 0xFFFF).to_bytes(2, "big")
        )
        if ok:
            self.max_distance = mm
        return ok

    async def async_set_hold_time(self, seconds: int) -> bool:
        """0x31 无人判断时间（秒，最短 3）."""
        ms = max(3, int(seconds)) * 1000
        ok = await self._send_cmd(MsgID.SET_LED_DURATION, ms.to_bytes(4, "big"))
        if ok:
            self.hold_time = ms / 1000
        return ok

    async def async_set_gear(self, gear: int) -> bool:
        """0x3A 探测档位（0 最灵敏 / 1 标准 / 2 最不灵敏）."""
        ok = await self._send_cmd(MsgID.SET_PARAM_GEAR, bytes([gear]))
        if ok:
            self.gear = gear
        return ok

    async def async_set_fan_switch(self, on: bool) -> bool:
        ok = await self._send_cmd(MsgID.FAN_SWITCH, encode_fan_switch(on))
        if ok:
            self.fan_on = on
        return ok

    async def async_set_fan_speed(self, speed: int) -> bool:
        """0x71: 0=停转, 1~9 递增."""
        ok = await self._send_cmd(MsgID.FAN_SPEED, encode_fan_speed(speed))
        if ok:
            self.fan_speed = speed
            self.fan_on = speed > 0
        return ok

    async def async_set_fan_direction(self, forward: bool) -> bool:
        ok = await self._send_cmd(MsgID.FAN_DIRECTION, encode_fan_direction(forward))
        if ok:
            self.fan_direction = int(forward)
        return ok

    async def async_find_device(self) -> bool:
        return await self._send_cmd(MsgID.FIND_DEVICE)


def _param_of(spec) -> MsgID:
    """ProbeSpec 帧里取回其查询的参数 ID（payload 首字节）."""
    from .rfp24_protocol import parse_frame

    f = parse_frame(spec.frame)
    return MsgID(f.payload[0])
