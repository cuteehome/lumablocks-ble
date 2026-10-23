"""RFP/RFM 24G 雷达私有协议编解码（协议版本 V2.21）。

用法::

    from rfp24_protocol import build_host_frame, MsgID, encode_brightness

    # 下行控制：开灯、亮度 80
    frame = build_host_frame(MsgID.LIGHT_SWITCH, bytes([1]))
    frame = build_host_frame(MsgID.LIGHT_BRIGHTNESS, encode_brightness(80))
    await client.write_gatt_char(TX_UUID, frame, response=True)

    # 上行解析（GATT notification 数据流）
    from rfp24_protocol import extract_frames, decode_target_light_report
    frames, remainder = extract_frames(data + leftover)
    for f in frames:
        if f.msg_id == MsgID.REPORT_TARGET_LIGHT:
            rpt = decode_target_light_report(f.payload)
            print(rpt.target, rpt.light_raw)
"""

from .const import (
    DISTANCE_SEGMENT_MM,
    DISTANCE_SEGMENTS,
    ErrorCode,
    MAGICS,
    MsgID,
    PARAM_VALUE_LENGTHS,
    REPORT_MICRO_SPECTRUM_BIT,
    REPORT_PRESENCE_SPECTRUM_BIT,
    REPORT_TARGET_LIGHT_BIT,
    SPECTRUM_BINS,
    SPECTRUM_PAYLOAD_LEN,
)
from .frames import (
    FrameError,
    ParsedFrame,
    build_frame,
    calc_check16,
    extract_frames,
    parse_frame,
)
from .probe import (
    Capability,
    DeviceType,
    DEVICE_TYPE_NAMES,
    ProbeSpec,
    classify,
    probe_queries,
)
from .payloads import (
    Ack,
    QueryResult,
    SpectrumReport,
    TargetLightReport,
    build_device_frame,
    build_host_frame,
    decode_ack,
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
    encode_thresholds13,
    encode_u16,
    encode_u32,
)

__version__ = "0.1.0"

__all__ = [
    "DISTANCE_SEGMENT_MM", "DISTANCE_SEGMENTS", "ErrorCode", "MAGICS", "MsgID",
    "PARAM_VALUE_LENGTHS", "REPORT_MICRO_SPECTRUM_BIT",
    "REPORT_PRESENCE_SPECTRUM_BIT", "REPORT_TARGET_LIGHT_BIT",
    "SPECTRUM_BINS", "SPECTRUM_PAYLOAD_LEN",
    "FrameError", "ParsedFrame", "build_frame", "calc_check16",
    "extract_frames", "parse_frame",
    "Ack", "QueryResult", "SpectrumReport", "TargetLightReport",
    "build_device_frame", "build_host_frame",
    "decode_ack", "decode_query_response", "decode_response",
    "decode_spectrum_report", "decode_target_light_report",
    "encode_brightness", "encode_cct", "encode_fan_direction",
    "encode_fan_speed", "encode_fan_switch", "encode_light_switch",
    "encode_query", "encode_report_config", "encode_thresholds13",
    "encode_u16", "encode_u32",
    "Capability", "DeviceType", "DEVICE_TYPE_NAMES", "ProbeSpec",
    "classify", "probe_queries",
]
