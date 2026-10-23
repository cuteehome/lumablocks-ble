"""Constants for the RFP BLE integration."""

DOMAIN = "lumablocks_ble"

# BLE GATT（真机枚举确认：RF-P2405_EDA20B，服务 0000ffe0）
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
TX_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"  # write-without-response
RX_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"  # notify

# 广播匹配（config_flow 发现用）
# 候选设备名匹配（发现初筛；真正识别靠连接后的能力探测）
LOCAL_NAME_PREFIXES = ("RF", "_CW", "_FAN")

# 灯色温映射：协议 0(全暖)~100(全冷) ↔ 开尔文
CCT_MIN_K = 2700
CCT_MAX_K = 6500
DEFAULT_CCT_K = 4100  # 协议默认 50

# 控制超时（两级转发模型下 ACK 可能慢）
CMD_TIMEOUT = 3.0
