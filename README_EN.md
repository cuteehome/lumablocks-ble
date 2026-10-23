# LumaBlocks BLE

Custom Home Assistant integration for LumaBlocks 24G mmWave radar (RFP/RFM series) devices over direct BLE connection — no gateway required.

[中文](README.md)

## Features

- Auto-discovery of LumaBlocks radar devices advertising as `RF-*`
- Entities:
  - Binary sensor: occupancy (target indication)
  - Sensor: light sensor value
  - Light: on/off, brightness, color temperature
  - Fan: on/off, speed (0–9), direction
  - Number/select entities: duration, max distance, sensitivity, preset gear, and other protocol parameters
- Built on RFP/RFM 24G communication protocol v2.22 (frame heads 0x59/0x58, Check16 arithmetic-sum checksum)

## Installation

### HACS (recommended)

1. HACS → ⋮ → Custom repositories
2. Add `https://github.com/cuteehome/lumablocks-ble` with category **Integration**
3. Install "LumaBlocks BLE" from HACS
4. Restart Home Assistant

### Manual

```bash
cd config/custom_components
git clone https://github.com/cuteehome/lumablocks-ble lumablocks_ble
```

Restart Home Assistant.

## Configuration

1. Settings → Devices & Services → Add Integration → **LumaBlocks BLE**
2. Power on the device (BLE advertisement name `RF-*`); it will be discovered automatically — select it to finish setup
3. Devices can also be added via the Bluetooth discovery prompt

## Supported devices

| Series | Notes |
|---|---|
| RFP24 | Presence radar (fan light / ceiling light scenarios) |
| RFM24 | Only duration / max distance / sensitivity parameters |

> Dual-color light modules have no controller link; fan features are unavailable.

## License

MIT
