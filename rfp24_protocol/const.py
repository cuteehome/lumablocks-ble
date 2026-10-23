"""RFP/RFM 24G 毫米波雷达私有协议常量。

依据《RFP/RFM 24G 毫米波雷达传感器通信协议说明书》V2.21（广东锐泛感知）。
帧经 BLE GATT 封装传输：网关/HA 为上位机（0x59），子设备为雷达侧（0x58）。
"""

from enum import IntEnum

# 特征码
HOST_MAGIC = 0x59  # 上位机(网关/HA) → 雷达
DEVICE_MAGIC = 0x58  # 雷达 → 上位机
MAGICS = frozenset({HOST_MAGIC, DEVICE_MAGIC})

# 帧字段长度：[magic][msg_id][length][payload...][check16(BE)]
HEADER_LEN = 3
CHECK_LEN = 2


class MsgID(IntEnum):
    """功能指令 ID。"""

    # ---- 参数配置（上位机 → 雷达）----
    SET_LED_DURATION = 0x31      # LED 持续点亮时间, uint32 ms, 0..600000, 默认 12000
    SET_MAX_DISTANCE = 0x32      # 最远距离, uint16 mm, 0..9750, 默认 6000
    START_BG_LEARNING = 0x33     # 启动背景学习, 空 Payload
    SET_LEARN_TIME = 0x34        # 背景学习时长, uint16 s, 默认 20
    SET_LIGHT_THRESHOLD = 0x35   # 光敏阈值, uint16, 0..2000, 默认 220
    SET_MICRO_THRESHOLDS = 0x36  # 微动门限, uint8[13], 每段 750mm
    SET_PRESENCE_THRESHOLDS = 0x37  # 人存门限, uint8[13]
    SET_SENSITIVITY = 0x38       # 灵敏度, uint8, 0..32, 默认 26, 仅 RFM24
    SET_PARAM_GEAR = 0x3A        # 参数档位, uint8, 0(最灵敏)..2, 默认 1
    SET_LEARN_WAIT_TIME = 0x3B   # 学习前等待, uint16 s, 默认 30
    SET_MICRO_FLOAT = 0x3C       # 微动上浮门限, uint8, 默认 5
    SET_PRESENCE_FLOAT = 0x3D    # 人存上浮门限, uint8, 默认 4
    SET_TRIG_PWM = 0x3E          # 触发 PWM 占空比, uint8 %, 默认 100
    SET_UNTRIG_PWM = 0x3F        # 未触发 PWM 占空比, uint8 %, 默认 0
    QUERY_PARAMS = 0x40          # 查询参数（含 0x70~0x75 专用状态）
    RESET_DEFAULTS = 0x41        # 恢复出厂默认

    # ---- 上报 ----
    SET_REPORT_CONFIG = 0x50     # 设置上报内容: [mask][multiplier]
    REPORT_TARGET_LIGHT = 0x51   # 雷达→上位机: [seq u16][target u8][light u16]
    REPORT_MICRO_SPECTRUM = 0x52 # 雷达→上位机: [seq u16][39B 频谱]
    REPORT_PRESENCE_SPECTRUM = 0x53
    STOP_REPORT = 0x54           # 停止所有连续上报

    # ---- 系统 ----
    SET_RF_SWITCH = 0x60         # 雷达射频开关, uint8, 掉电保存
    SET_LIGHT_SWITCH = 0x61      # 光敏功能开关, uint8, 掉电保存
    FIND_DEVICE = 0x62           # 寻找设备(闪灯), 空 Payload

    # ---- 专用指令（风扇灯/吸顶灯/色温灯，5.2 转发模型）----
    FAN_SWITCH = 0x70            # 0 关 / 1 开
    FAN_SPEED = 0x71             # 0 停转 / 1..9 递增
    FAN_DIRECTION = 0x72         # 0 反转 / 1 正转
    LIGHT_SWITCH = 0x73          # 0 关 / 1 开
    LIGHT_BRIGHTNESS = 0x74      # 0..100, 默认 100
    LIGHT_CCT = 0x75             # 0 全暖..100 全冷, 默认 50


class ErrorCode(IntEnum):
    """0x58 [MsgID] 0x01 [错误码] 通用响应。"""

    OK = 0x00            # ACK
    CHECKSUM = 0x01      # 校验和错误
    BAD_MSGID = 0x02     # 无效 MsgID
    BAD_LENGTH = 0x03    # 无效数据长度
    BAD_MASK = 0x04      # 无效位掩码（仅 0x50）
    BUFFER_OVERFLOW = 0x05
    RX_TIMEOUT = 0x06    # 传输中断 / 外部设备转发无响应
    PARAM_RANGE = 0x08   # 参数超出范围
    API_ERROR = 0x09
    BUSY_LEARNING = 0x0A # 背景学习中无法设置

# 0x50 上报类型位掩码
REPORT_TARGET_LIGHT_BIT = 0x02   # 0x51
REPORT_MICRO_SPECTRUM_BIT = 0x04 # 0x52
REPORT_PRESENCE_SPECTRUM_BIT = 0x08  # 0x53

# 频谱上报 Payload 固定长度: seq(2) + 39 bins
SPECTRUM_BINS = 39
SPECTRUM_PAYLOAD_LEN = 2 + SPECTRUM_BINS

# 0x40 查询响应中各参数值的字节长度（0x70~0x75 按对应写指令 1 Byte 记录，待固件确认）
PARAM_VALUE_LENGTHS: dict[int, int] = {
    MsgID.SET_LED_DURATION: 4,
    MsgID.SET_MAX_DISTANCE: 2,
    MsgID.SET_LEARN_TIME: 2,
    MsgID.SET_LIGHT_THRESHOLD: 2,
    MsgID.SET_MICRO_THRESHOLDS: 13,
    MsgID.SET_PRESENCE_THRESHOLDS: 13,
    MsgID.SET_SENSITIVITY: 1,
    MsgID.SET_PARAM_GEAR: 1,
    MsgID.SET_LEARN_WAIT_TIME: 2,
    MsgID.SET_MICRO_FLOAT: 1,
    MsgID.SET_PRESENCE_FLOAT: 1,
    MsgID.SET_TRIG_PWM: 1,
    MsgID.SET_UNTRIG_PWM: 1,
    MsgID.SET_RF_SWITCH: 1,
    MsgID.SET_LIGHT_SWITCH: 1,
    MsgID.FAN_SWITCH: 1,
    MsgID.FAN_SPEED: 1,
    MsgID.FAN_DIRECTION: 1,
    MsgID.LIGHT_SWITCH: 1,
    MsgID.LIGHT_BRIGHTNESS: 1,
    MsgID.LIGHT_CCT: 1,
}

# 距离门限: 13 段，每段 750mm（0..9750mm）
DISTANCE_SEGMENTS = 13
DISTANCE_SEGMENT_MM = 750
