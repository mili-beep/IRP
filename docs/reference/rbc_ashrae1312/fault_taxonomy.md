# RBC-ASHRAE1312 Real Fault Taxonomy

This is a searchable project summary of the supplied RBC-ASHRAE1312 explanation document. The PDF remains the authoritative source.

| Family | Abbreviations/examples | Meaning |
|---|---|---|
| Outdoor-air damper | `OADamStuck_0`, `OADamStuck_40`, `OADamLea_45`, `OADamLea_52` | Damper stuck at a position or leakage emulated by a fixed intermediate position |
| Exhaust-air damper | `EADamStuck_0`, `EADamStuck_40`, `EADamStuck_100`, `EADamLea_55`, `EADamLea_62` | Exhaust damper stuck or leakage scenario |
| Cooling coil valve | `CooCoiValStuck_0`, `CooCoiValStuck_15`, `CooCoiValStuck_20`, `CooCoiValStuck_50`, `CooCoiValStuck_65`, `CooCoiValStuck_100` | Cooling coil valve held at a fixed opening |
| Heating coil valve | `HeaCoiValLea_0.4`, `HeaCoiValLea_1`, `HeaCoiValLea_2` | Heating coil bypass leakage in GPM |
| Duct/equipment | `SupDucLea_AfterSF`, `SupDucLea_BeforeSF`, `HeaCoiFou_1`, `HeaCoiFou_2`, `HeaCoiReduCapa_1`..`_3`, `AirFilBlock_10`, `AirFilBlock_25` | Duct leakage, coil fouling/reduced capacity, or air-filter blockage |
| Return/supply fan | `RetFan_Fail`, `RetFanFixed_20`, `RetFanFixed_30`, `RetFanFixed_80` | Return fan failure or fixed-speed condition |
| Controller | `ConSupFan_Unst`, `ConCooCoiVal_Unst`, `CooCoiVal_Reverse`, `MADam_Unst`, `Con_MADamCooCoi_Unst`, `HeaCooSeq_Unst` | Unstable, reverse-action, or sequence-control behavior |
| Sensor | `TOut_p3`, `TOut_m3` | Outdoor-air temperature sensor bias of +3 or -3 degrees F |

## Source-reported seasonal coverage

The source reports 49 real fault scenarios across summer, winter, and spring/transition. Not every fault family appears in every season. The dataset adapter must derive the actual local coverage from the date folders and preserve missing seasonal combinations as meaningful metadata.

## Labeling rule for this project

Every row inherits scenario metadata from its source fault file. `baseline.csv` rows receive `is_fault = false`; named fault files receive `is_fault = true` and the parsed taxonomy fields. This is scenario labeling, not a claim that every timestamp is the exact onset of a fault.
