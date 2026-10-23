"""各 MsgID 的 Payload 编解码（纯函数，便于单测与双端复用）。

上行构建（上位机→雷达, magic=0x59）用 encode_*；下行解析（雷达→上位机,
magic=0x58）用 decode_*。所有 decode 均严格校验长度，坏数据抛 ValueError。
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    DISTANCE_SEGMENTS,
    ErrorCode,
    MsgID,
    PARAM_VALUE_LENGTHS,
    REPORT_MICRO_SPECTRUM_BIT,
    REPORT_PRESENCE_SPECTRUM_BIT,
    REPORT_TARGET_LIGHT_BIT,
    SPECTRUM_BINS,
    SPECTRUM_PAYLOAD_LEN,
)
from .frames import build_frame, calc_check16

__all__ = [
    "build_host_frame", "build_device_frame",
    "Ack", "TargetLightReport", "SpectrumReport", "QueryResult",
    "encode_u16", "encode_u32",
    "encode_query", "decode_query_response", "decode_ack",
    "decode_target_light_report", "decode_spectrum_report",
    "encode_fan_switch", "encode_fan_speed", "encode_fan_direction",
    "encode_light_switch", "encode_brightness", "encode_cct",
    "encode_report_config",
]


# ---------------------------------------------------------------- 帧便捷构建
def build_host_frame(msg_id: MsgID | int, payload: bytes = b"") -> bytes:
    """上位机(网关/HA) → 雷达，特征码 0x59。"""
    return build_frame(int(msg_id), payload, magic=0x59)


def build_device_frame(msg_id: MsgID | int, payload: bytes = b"") -> bytes:
    """雷达 → 上位机，特征码 0x58（主要用于测试与外部设备模拟）。"""
    return build_frame(int(msg_id), payload, magic=0x58)


# ---------------------------------------------------------------- 基础编码
def encode_u16(value: int) -> bytes:
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"u16 out of range: {value}")
    return value.to_bytes(2, "big")


def encode_u32(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"u32 out of range: {value}")
    return value.to_bytes(4, "big")


def _decode_u16(payload: bytes, offset: int = 0) -> int:
    return int.from_bytes(payload[offset:offset + 2], "big")


# ---------------------------------------------------------------- 通用响应
@dataclass(frozen=True)
class Ack:
    """0x58 [MsgID] 0x01 [错误码]：参数/系统/专用指令的通用响应。"""

    msg_id: int
    error: ErrorCode
    ok: bool


def decode_ack(payload: bytes) -> Ack:
    if len(payload) != 1:
        raise ValueError(f"ack payload must be 1 byte, got {len(payload)}")
    err = ErrorCode(payload[0])
    return Ack(msg_id=-1, error=err, ok=err is ErrorCode.OK)
    # 注：msg_id 由外层 ParsedFrame 提供，见 decode_response()


def decode_response(frame_msg_id: int, payload: bytes) -> Ack | None:
    """len(payload)==1 的设备帧按通用响应（ACK/NACK）解释。"""
    if len(payload) == 1:
        err = ErrorCode(payload[0])
        return Ack(msg_id=frame_msg_id, error=err, ok=err is ErrorCode.OK)
    return None


# ---------------------------------------------------------------- 上报 0x51
@dataclass(frozen=True)
class TargetLightReport:
    """0x51 目标与光照状态上报。

    light_raw 数值越大表示光照越弱（厂商原始语义，映射 HA 亮度需取反或注明）。
    """

    seq: int
    target: bool
    light_raw: int


def decode_target_light_report(payload: bytes) -> TargetLightReport:
    if len(payload) != 5:
        raise ValueError(f"0x51 payload must be 5 bytes, got {len(payload)}")
    seq = int.from_bytes(payload[0:2], "big")
    target = payload[2]
    if target not in (0, 1):
        raise ValueError(f"0x51 target must be 0/1, got {target}")
    return TargetLightReport(seq=seq, target=bool(target), light_raw=_decode_u16(payload, 3))


# ---------------------------------------------------------------- 上报 0x52/0x53
@dataclass(frozen=True)
class SpectrumReport:
    """0x52/0x53 微动/人存频谱上报：39 个 dB 值，按频率从小到大。"""

    seq: int
    bins: tuple[int, ...]


def decode_spectrum_report(payload: bytes) -> SpectrumReport:
    if len(payload) != SPECTRUM_PAYLOAD_LEN:
        raise ValueError(
            f"spectrum payload must be {SPECTRUM_PAYLOAD_LEN} bytes, got {len(payload)}"
        )
    seq = int.from_bytes(payload[0:2], "big")
    return SpectrumReport(seq=seq, bins=tuple(payload[2:]))


# ---------------------------------------------------------------- 0x40 查询
def encode_query(param_ids: list[MsgID | int]) -> bytes:
    """查询一个或多个参数当前值（含 0x70~0x75 专用状态）。"""
    ids = [int(p) for p in param_ids]
    if not ids:
        raise ValueError("query needs at least one param id")
    return bytes(ids)


@dataclass(frozen=True)
class QueryResult:
    """0x40 查询响应：参数 ID → 原始值字节。"""

    values: dict[int, bytes]

    def get_u8(self, param_id: int) -> int:
        raw = self.values[param_id]
        if len(raw) != 1:
            raise ValueError(f"param 0x{param_id:02X} not u8: {raw.hex()}")
        return raw[0]

    def get_u16(self, param_id: int) -> int:
        raw = self.values[param_id]
        if len(raw) != 2:
            raise ValueError(f"param 0x{param_id:02X} not u16: {raw.hex()}")
        return int.from_bytes(raw, "big")


def decode_query_response(payload: bytes) -> QueryResult:
    """按“参数 ID + 对应长度值”连续排列解析。

    值长度取 PARAM_VALUE_LENGTHS；未知 ID 长度按协议无法判定，抛错
    （固件若返回未登记参数，需先在 const.PARAM_VALUE_LENGTHS 补充）。
    """
    values: dict[int, bytes] = {}
    i = 0
    while i < len(payload):
        pid = payload[i]
        i += 1
        vlen = PARAM_VALUE_LENGTHS.get(pid)
        if vlen is None:
            raise ValueError(f"unknown param id 0x{pid:02X} at offset {i - 1}")
        if i + vlen > len(payload):
            raise ValueError(f"param 0x{pid:02X} value truncated")
        values[pid] = bytes(payload[i:i + vlen])
        i += vlen
    return QueryResult(values=values)


# ---------------------------------------------------------------- 0x50 上报配置
def encode_report_config(
    target_light: bool = True,
    micro_spectrum: bool = False,
    presence_spectrum: bool = False,
    multiplier: int = 1,
) -> bytes:
    """设置上报内容。multiplier: 每 N 帧上报一次（1=与帧周期同步）。"""
    if not 1 <= multiplier <= 0xFF:
        raise ValueError(f"multiplier out of range: {multiplier}")
    mask = 0
    if target_light:
        mask |= REPORT_TARGET_LIGHT_BIT
    if micro_spectrum:
        mask |= REPORT_MICRO_SPECTRUM_BIT
    if presence_spectrum:
        mask |= REPORT_PRESENCE_SPECTRUM_BIT
    if mask == 0:
        raise ValueError("at least one report type must be enabled (or use 0x54 to stop)")
    return bytes((mask, multiplier))


# ---------------------------------------------------------------- 专用指令 0x70~0x75
def _encode_u8_payload(value: int, lo: int, hi: int, what: str) -> bytes:
    if not lo <= value <= hi:
        raise ValueError(f"{what} out of range [{lo},{hi}]: {value}")
    return bytes((value,))


def encode_fan_switch(on: bool) -> bytes:
    return _encode_u8_payload(int(on), 0, 1, "fan switch")


def encode_fan_speed(speed: int) -> bytes:
    """0=停转, 1~9 档位递增。"""
    return _encode_u8_payload(speed, 0, 9, "fan speed")


def encode_fan_direction(forward: bool) -> bytes:
    """True=正转(1), False=反转(0)。"""
    return _encode_u8_payload(int(forward), 0, 1, "fan direction")


def encode_light_switch(on: bool) -> bytes:
    return _encode_u8_payload(int(on), 0, 1, "light switch")


def encode_brightness(brightness: int) -> bytes:
    """0 最暗 ~ 100 最亮。"""
    return _encode_u8_payload(brightness, 0, 100, "brightness")


def encode_cct(cct: int) -> bytes:
    """0 全暖光 ~ 100 全冷光。"""
    return _encode_u8_payload(cct, 0, 100, "cct")


# ---------------------------------------------------------------- 参数配置便捷编码
def encode_thresholds13(thresholds: list[int]) -> bytes:
    """0x36/0x37 的 13 段距离门限（每段 750mm）。"""
    if len(thresholds) != DISTANCE_SEGMENTS:
        raise ValueError(f"need {DISTANCE_SEGMENTS} thresholds, got {len(thresholds)}")
    if any(not 0 <= t <= 255 for t in thresholds):
        raise ValueError("threshold out of range [0,255]")
    return bytes(thresholds)
