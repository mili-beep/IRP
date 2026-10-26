# Data Dictionary

The first supported dataset is the real RBC-ASHRAE1312 collection. Its raw feature names, descriptions, and units are summarized in [the RBC feature dictionary](reference/rbc_ashrae1312/feature_dictionary.md). The supplied `FeaturesNames.xls` remains authoritative.

The canonical table will preserve raw columns and add metadata columns rather than renaming or overwriting source values:

- `source_type`: `real` for the current release.
- `season`: `Summer`, `Transition`, or `Winter`.
- `date_folder`: source scenario date.
- `scenario_file`: source CSV basename.
- `scenario_abbreviation`, `fault_type`, `fault_intensity`, `controlled_device`: parsed taxonomy fields.
- `is_fault`: false for `baseline.csv`, true for named fault files.
- `timestamp`: parsed combination of `DATE` and `TIME`.

The source uses one-minute measurements. Raw units are primarily degrees F, CFM, percent, WG, PSI, GPM, watts, amps, mBar, and MPH. Unit conversion is not part of the ingestion contract and must be configured as an explicit feature step.

The real-only schema includes AHU controls and symptoms, VAV/test-room measurements, energy fields, and optional weather data. Weather remains a separate feature group so experiments can compare AHU-only and context-augmented models.
