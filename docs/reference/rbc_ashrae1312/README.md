# RBC-ASHRAE1312 Reference

This directory records the provenance and searchable interpretation of the RBC-ASHRAE1312 dataset used by SFSA.

## Authoritative local sources

The raw dataset is stored at:

`IRP/data/raw/01_RBC-ASHRAE1312/`

The local source documents are:

- `00_explanations.pdf`: dataset explanation and fault-scenario information.
- `FeaturesNames.xls`: raw feature abbreviations, descriptions, and units.

The project currently uses only:

`IRP/data/raw/01_RBC-ASHRAE1312/Real/`

The `Simulation/` tree is intentionally out of scope for the first release.

## Dataset identity

- Dataset: RBC-ASHRAE1312.
- Site: Iowa Energy Center Energy Resource Station, Iowa City, Iowa, USA.
- System: two similar single-duct VAV AHUs, each serving four zones.
- Real data: faults were injected into AHU A while parallel AHU B supplied fault-free baseline data.
- Sampling: one minute.
- Duration: one day per scenario.
- Occupied period described by the source: 06:00-18:00.
- Real feature count reported by the source: 162.
- Reported real fault count: 49 across summer, winter, and transition/spring seasons.

## Local source inventory

The real tree is organized as:

```text
Real/
  Summer/YYYYMMDD/
  Transition/YYYYMMDD/
  Winter/YYYYMMDD/
```

A date directory normally contains:

- `baseline.csv`: fault-free reference data for that date.
- One named fault CSV: a controlled fault scenario.
- `weather.csv`: real outdoor conditions, when provided.

The baseline and fault data are described by the source as sharing timestamps. The ingestion contract must verify this rather than assume it.

## Fault taxonomy summary

Filename abbreviations are scenario labels, not row-level sensor labels. The initial adapter will parse these fields from filenames and taxonomy metadata:

- Fault abbreviation
- Fault family/type
- Intensity or parameter
- Controlled device
- Season
- Date
- Real source tag

The supplied taxonomy includes damper, coil, duct, fan, controller, and sensor faults. Examples include `OADamStuck`, `EADamStuck`, `CooCoiValStuck`, `HeaCoiValLea`, `SupDucLea`, `HeaCoiFou`, `RetFan_Fail`, `RetFanFixed`, and outdoor-temperature sensor bias scenarios.

The distinction between an outdoor-air damper being stuck and leaking must be retained as separate fault mechanisms even when both were implemented by fixing the damper at a position in the real facility.

The local CSV distribution contains a few explicit spelling/separator variants, including `OADamLeak`/`OADamLea`, `CooCoilValStuck`/`CooCoiValStuck`, `HeaCoiValLeak`/`HeaCoiValLea`, and `HeatCoiReduCapa`/`HeaCoiReduCapa`. The adapter maps only these documented aliases; unknown scenario names fail loudly.

## Interpretation limits

- A fault filename labels a scenario/file. It does not by itself identify the exact fault onset timestamp.
- These are controlled injected faults, not a sample of naturally occurring maintenance events.
- Real and simulation files have different feature schemas and must not be merged by filling absent columns with zero.
- Raw abbreviations and units must be preserved; canonical display names are a separate mapping.
- Any occupied-hours filtering must be configured and reported, not applied silently.

## Provenance and checksums

Before publishing a run or copying the reference documents into another repository, record SHA-256 checksums for:

- `00_explanations.pdf`
- `FeaturesNames.xls`
- Every raw Real CSV used by the run

The generated manifest should include source paths, file sizes, row counts, columns, timestamp range, cadence checks, and baseline/fault pairing status.
