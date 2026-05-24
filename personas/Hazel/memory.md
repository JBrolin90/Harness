# Hazel Memory - Home Assistant Context

## Infrastructure

- **HA Config Path**: `/mnt/ha_config/`
- **HA API Access**: Use `~/bin/ha_cmd.sh` (e.g., `~/bin/ha_cmd.sh GET /api/status`)
- **HA Version**: 2026.3.4
- **Running Environment**: VM with Conbee II Zigbee coordinator

## Known Devices & Integrations

### Zigbee (ZHA - Conbee II)
| Entity | Model | Notes |
|--------|-------|-------|
| `switch.tz3000_ww6drja5_ts011f_plug` | TS011F _TZ3000 | Water boiler plug |
| `switch.tz3000_cehuw1lw_ts011f_plug_2` | TS011F _TZ3000 | Unknown purpose |
| `switch.tz3000_cehuw1lw_ts011f_plug_3` | TS011F _TZ3000 | Unknown purpose |
| `switch.tz3000_kqvb5akv_ts0001` | TS0001 _TZ3000 | Switch |
| `sensor.tz3000_ww6drja5_ts011f_plug_current` | TS011F | Current reading (for water boiler detection) |
| `light.dresden_elektronik_conbee_ii_lounge_lights` | TRADFRI bulb | Lounge |
| `light.ceiling_bulb_light` | AwoX ESMLFzm | Ceiling |
| `light.kitchenbulb_light` | AwoX ESMLFzm | Kitchen |
| `light.speaker_bulb_light` | AwoX ESMLFzm | Speaker |
| `light.pool_wall` | TS0505B RGB | Pool area |
| `binary_sensor.water_boiler` | Template sensor | Derived from plug current > 1.0A |

### Other Integrations
- **Sonos**: SYMFONISK Table lamp (Family Room)
- **Samsung TV**: 65" QLED TQ65Q77DATXXC
- **Google Cast**: Nest Mini (Den speaker)
- **Roomba**: i557840 at `192.168.33.128` - **OFFLINE/UNREACHABLE**
- **IPP Printer**: HP DeskJet 2700 series
- **TP-Link Router**: GT-AC5300

## Automations

1. **Water Boiler off** (ID: `1744288685497`) - Triggers when `binary_sensor.water_boiler` goes off
2. **Water Boiler on** (ID: `1744289101235`) - **BROKEN** - conflicting time conditions (disabled)
3. **AutoLights** (ID: `1763730548273`) - Sunrise/sunset + scheduled light control

## Known Issues

### High Priority
- **Roomba unreachable**: Connection timeout to `192.168.33.128` - MQTT connection fails consistently

### Medium Priority
- **Water boiler on automation**: Has impossible time condition (`after: 16:00` before `before: 14:00`)
- **Zigbee cluster warning**: Minor cluster direction mismatch on TS011F (cosmetic only)

## User Preferences
- Address as "Joachim"
- Use local LLM for Home Assistant work