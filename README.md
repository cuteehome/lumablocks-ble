# LumaBlocks BLE

LumaBlocks 24G 毫米波雷达（RFP/RFM 系列）的 Home Assistant 自定义集成，通过 BLE 直连设备，无需网关。

中文 · [English](README_EN.md)

## 功能

- 自动发现 BLE 广播名为 `RF-*` 的 LumaBlocks 雷达设备
- 实体：
  - 二进制传感器：人体存在（目标指示）
  - 传感器：光敏采样值
  - 灯：开关 / 亮度 / 色温
  - 风扇：开关 / 转速（0~9 档）/ 正反转
  - 数字/选择：持续时间、最远距离、灵敏度、参数档位等协议参数配置
- 基于 RFP/RFM 24G 通信协议 v2.22（帧头 0x59/0x58，Check16 算术和校验）

## 安装

### HACS（推荐）

1. HACS → ⋮ → 自定义仓库
2. 仓库地址填 `https://github.com/cuteehome/lumablocks-ble`，类别选 **集成（Integration）**
3. 添加后在 HACS 中搜索 "LumaBlocks BLE" 安装
4. 重启 Home Assistant

### 手动安装

```bash
cd config/custom_components
git clone https://github.com/cuteehome/lumablocks-ble lumablocks_ble
```

重启 Home Assistant。

## 配置

1. 设置 → 设备与服务 → 添加集成 → 搜索 **LumaBlocks BLE**
2. 设备上电并处于 BLE 广播状态（名称 `RF-*`），集成会自动发现并列出，选择设备完成添加
3. 也可通过 蓝牙 发现弹窗直接添加

## 支持的设备

| 系列 | 说明 |
|---|---|
| RFP24 | 人体存在雷达（风扇灯/吸顶灯场景） |
| RFM24 | 仅支持持续时间 / 最远距离 / 灵敏度参数 |

> 双色灯模块无控制器链路，风扇相关功能不可用。

## 协议

协议文档见仓库 [rfp24_protocol](rfp24_protocol/) 目录及 `~/radar-lights/output/` 下的协议 md（v2.22 最新）。

## License

MIT
