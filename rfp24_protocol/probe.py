"""复合设备能力探测与分类。

设备分五类（厂商确认 2026-09-27）：
  1. 单独存在传感器
  2. 单独双色温灯
  3. 风扇 + 双色温灯
  4. 存在传感器 + 双色温灯
  5. 存在传感器 + 风扇灯 + 双色温灯

复合设备识别方法：通过 0x40 逐字段查询——
  - 灯：读色温字段(0x75)
  - 风扇：读风扇档位字段(0x71)
  - 存在传感器：读灵敏度设置(0x38)
查询成功（返回值）→ 具备该能力；返回错误码 → 不具备。

实现注意：协议 0x40 的失败响应是整帧错误（0x58 0x40 0x01 [错误码]），
无法从一次多参数查询中区分是哪个字段失败，因此探测时每个能力字段
单独发一条单参数查询，逐条判定成败。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, unique

from .const import MsgID
from .payloads import build_host_frame, encode_query

__all__ = [
    "Capability", "DeviceType", "ProbeSpec",
    "probe_queries", "classify", "DEVICE_TYPE_NAMES",
]

# 探测字段：能力 → 0x40 查询的参数 ID
PROBE_FIELD = {
    "presence": MsgID.SET_SENSITIVITY,   # 0x38 灵敏度设置
    "fan": MsgID.FAN_SPEED,              # 0x71 风扇档位
    "light": MsgID.LIGHT_CCT,            # 0x75 灯具色温
}


@unique
class Capability(IntFlag):
    """设备能力位。"""

    NONE = 0
    PRESENCE = 1 << 0   # 存在传感器
    FAN = 1 << 1        # 风扇
    LIGHT = 1 << 2      # 双色温灯


@unique
class DeviceType(IntFlag):
    """五类设备。值与 Capability 组合一致，便于直接比较。"""

    PRESENCE_ONLY = Capability.PRESENCE
    LIGHT_ONLY = Capability.LIGHT
    FAN_LIGHT = Capability.FAN | Capability.LIGHT
    PRESENCE_LIGHT = Capability.PRESENCE | Capability.LIGHT
    PRESENCE_FAN_LIGHT = Capability.PRESENCE | Capability.FAN | Capability.LIGHT


DEVICE_TYPE_NAMES: dict[DeviceType, str] = {
    DeviceType.PRESENCE_ONLY: "单独存在传感器",
    DeviceType.LIGHT_ONLY: "单独双色温灯",
    DeviceType.FAN_LIGHT: "风扇+双色温灯",
    DeviceType.PRESENCE_LIGHT: "存在传感器+双色温灯",
    DeviceType.PRESENCE_FAN_LIGHT: "存在传感器+风扇灯+双色温灯",
}


@dataclass(frozen=True)
class ProbeSpec:
    """一条能力探测查询：能力位 + 待发送的 0x40 完整帧。"""

    capability: Capability
    frame: bytes


def probe_queries() -> list[ProbeSpec]:
    """生成三条单参数 0x40 探测帧（灯/风扇/存在各一条），逐条发送判定。"""
    return [
        ProbeSpec(cap, build_host_frame(MsgID.QUERY_PARAMS, encode_query([param])))
        for cap, param in (
            (Capability.LIGHT, PROBE_FIELD["light"]),
            (Capability.FAN, PROBE_FIELD["fan"]),
            (Capability.PRESENCE, PROBE_FIELD["presence"]),
        )
    ]


def classify(capabilities: dict[Capability, bool]) -> DeviceType:
    """根据逐字段探测结果（能力 → 是否查询成功）分类设备。

    不在五类定义内的能力组合（如单独风扇）会正常返回组合值，
    由调用方决定是否按未知设备处理。
    """
    caps = Capability.NONE
    for cap, present in capabilities.items():
        if present:
            caps |= cap
    return DeviceType(caps)
