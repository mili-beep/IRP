# RBC-ASHRAE1312 Feature Dictionary

This searchable summary is based on the supplied `FeaturesNames.xls`. The spreadsheet remains the authoritative feature reference. Raw abbreviations must remain available in the canonical dataset.

## Time fields

| Raw field | Meaning | Unit/format |
|---|---|---|
| `DATE` | Measurement date | `dd/mm/yyyy` in the source dictionary; validate against local files |
| `TIME` | Time of day, stored as `HHMM` (for example, `1` = 00:01 and `2359` = 23:59) | `HHMM` |

## AHU features

| Raw field(s) | Meaning | Unit |
|---|---|---|
| `SYS-CTL` | System occupancy control mode | 0 unoccupied, 1 occupied |
| `ACCH-SEL` | Chiller selection | source-defined |
| `OA-TEMP`, `OAD-TEMP` | Outdoor-air temperature / outdoor-air duct temperature | deg F |
| `RA-TEMP`, `MA-TEMP`, `SA-TEMP` | Return, mixed, and supply air temperature | deg F |
| `HWC-DAT`, `CHWC-DAT` | Heating/chilled-water coil discharge air temperature | deg F |
| `SA-SPT` | AHU supply-air temperature setpoint | deg F |
| `OA-CFM`, `RA-CFM`, `SA-CFM`, `RMT-CFM` | Outdoor, return, supply, and sum-of-room airflow | CFM |
| `OA-DMPR`, `RA-DMPR`, `EA-DMPR` | Outdoor, recirculated, and exhaust damper position | percent open/closed per source definition |
| `SA-SP`, `SF-DP`, `RF-DP` | Supply static pressure and fan differential pressures | WG |
| `SF-SST`, `RF-SST` | Supply/return fan start-stop | 1 on, 0 off |
| `SF-SPD`, `RF-SPD` | Supply/return fan VFD speed | percent |
| `SF-WAT`, `RF-WAT` | Supply/return fan power | watts |
| `HWC-VLV`, `CHWC-VLV` | Heating/chilled-water valve position | percent closed/open per source definition |
| `HWP-GPM`, `CHWP-GPM` | Heating/chilled-water pump flow | GPM |
| `HWP-DP` | Heating-water pump differential pressure | PSI |
| `HWC-EWT`, `HWC-LWT`, `HWC-MWT` | Heating coil entering, leaving, and mixed water temperature | deg F |
| `CHWC-EWT`, `CHWC-LWT`, `CHWC-MWT` | Chilled-water coil entering, leaving, and mixed water temperature | deg F |
| `CHWC-EAH`, `CHWC-LAH` | Chilled-water coil entering/leaving air relative humidity | percent relative humidity |
| `E_hcoil`, `E_ccoil`, `E_SF`, `E_RF`, `E_ZONE_*` | Heating/cooling coil, fan, and zone energy | watts/source-defined |

## VAV and test-room features

The real baseline schema includes repeated VAV groups with suffixes such as `.1`, `.2`, and `.3`. These include room temperature, discharge temperature, setpoints, damper position, valve control, flow, pressure, and hot-water temperatures.

Examples:

- `RM-TEMP`: room temperature, deg F
- `VAV-EAT`, `VAV-DAT`: VAV entering/discharge air temperature, deg F
- `RMC LGSPT`, `RMHTGSPT`: room cooling/heating setpoints, deg F
- `VAV-DP`, `VAVCFMDP`: VAV pressure/flow-related measurements
- `VAV-DMPR`: VAV damper position, percent open
- `VAVHCVLV`: VAV heating valve control, percent closed
- `VAVHCGPM`: VAV heating coil water flow, GPM

The exact raw headers in CSVs take precedence over typography in this summary.

## Test-room heating and lighting

Fields such as `IABBHT1`, `WABBHT1`, `SABBHT1`, and `EABBHT1` represent test-room baseboard heat stages. Fields such as `IALITES1`, `WALITES1`, `SALITES1`, and `EALITES1` represent lighting stages. Binary fields use the source's 1-on/0-off convention; power/current fields use amps or watts as documented.

## Weather features

Real `weather.csv` files contain:

| Raw field | Meaning | Unit |
|---|---|---|
| `BAR-PRES` | Barometric pressure normalized to sea level | mBar |
| `IR-RADIA` | Infrared radiation | B/Hft2 |
| `OA-HUMD` | Outdoor relative humidity | percent |
| `OA-TEMP` | Outdoor temperature | deg F |
| `SOL-ALM` | Solar alarm | 0 normal, 1 alarm |
| `SOL-BEAM`, `SOL-HORZ` | Solar beam/horizontal flux | B/Hft2 |
| `WIND-DIR` | Wind direction | degrees from north |
| `WIND-VEL` | Wind velocity | MPH |

## Canonical feature policy

The first implementation will preserve raw names and add a category mapping:

- `metadata`: `DATE`, `TIME`, source path, season, scenario metadata
- `control`: setpoints, control modes, valves, dampers, fan commands
- `symptom`: temperatures, airflow, pressure, humidity, and response measurements
- `weather`: fields from `weather.csv`
- `energy`: coil, fan, and zone energy
- `vav`: VAV/test-room measurements

Experiments must explicitly select `symptom_only`, `control_inclusive`, or an approved context-augmented policy. Missing columns must never be silently interpreted as physical zero.
