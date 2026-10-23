"""通用帧编解码：构建、解析、流式分帧。

帧结构: [magic(1)] [msg_id(1)] [length(1)] [payload(N)] [check16(2, 大端)]
Check16 = (magic + msg_id + length + sum(payload)) & 0xFFFF
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import CHECK_LEN, DEVICE_MAGIC, HEADER_LEN, HOST_MAGIC, MAGICS


class FrameError(ValueError):
    """帧不完整或校验失败。"""


def calc_check16(data: bytes) -> int:
    """除 Check16 自身外、前述所有字节的算术和（低 16 位）。"""
    return sum(data) & 0xFFFF


def build_frame(msg_id: int, payload: bytes = b"", magic: int = HOST_MAGIC) -> bytes:
    """构建一帧。默认上位机方向(0x59)；设备方向传 magic=DEVICE_MAGIC。"""
    if magic not in MAGICS:
        raise FrameError(f"invalid magic 0x{magic:02X}")
    if len(payload) > 0xFF:
        raise FrameError("payload too long")
    head = bytes((magic, msg_id & 0xFF, len(payload)))
    body = head + payload
    return body + calc_check16(body).to_bytes(CHECK_LEN, "big")


@dataclass(frozen=True)
class ParsedFrame:
    magic: int
    msg_id: int
    payload: bytes
    check16: int

    @property
    def from_host(self) -> bool:
        return self.magic == HOST_MAGIC

    @property
    def from_device(self) -> bool:
        return self.magic == DEVICE_MAGIC


def parse_frame(data: bytes) -> ParsedFrame:
    """解析一段恰好包含一个完整帧的字节串，校验 Check16。"""
    if len(data) < HEADER_LEN + CHECK_LEN:
        raise FrameError(f"frame too short: {len(data)} bytes")
    if data[0] not in MAGICS:
        raise FrameError(f"bad magic 0x{data[0]:02X}")
    length = data[2]
    total = HEADER_LEN + length + CHECK_LEN
    if len(data) != total:
        raise FrameError(f"length mismatch: header says {total}, got {len(data)}")
    check16 = int.from_bytes(data[total - CHECK_LEN:total], "big")
    actual = calc_check16(data[: total - CHECK_LEN])
    if check16 != actual:
        raise FrameError(f"checksum mismatch: frame 0x{check16:04X}, calc 0x{actual:04X}")
    return ParsedFrame(data[0], data[1], bytes(data[HEADER_LEN:HEADER_LEN + length]), check16)


def extract_frames(buffer: bytes) -> tuple[list[ParsedFrame], bytes]:
    """从字节流中提取所有完整帧（容错重同步），返回 (帧列表, 剩余未完成的尾部)。

    BLE GATT notification 常见"一次通知含粘包/半包"，用本函数做流式分帧：
    - 从任意偏移扫描特征码 0x59/0x58，Check16 通过才认帧；
    - 校验失败向前滑动 1 字节继续找（抵抗 payload 中出现 0x59/0x58 的误同步）；
    - 尾部不足一个完整帧时作为 remainder 留待与下次数据拼接。
    """
    frames: list[ParsedFrame] = []
    i = 0
    n = len(buffer)
    while i < n:
        if buffer[i] not in MAGICS:
            i += 1
            continue
        if i + HEADER_LEN > n:
            break  # 头都不完整
        length = buffer[i + 2]
        total = HEADER_LEN + length + CHECK_LEN
        if i + total > n:
            break  # 半包，留待拼接
        try:
            frames.append(parse_frame(buffer[i:i + total]))
        except FrameError:
            i += 1  # 误同步，滑动重试
            continue
        i += total
    return frames, buffer[i:]
