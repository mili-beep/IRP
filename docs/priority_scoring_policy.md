# Operational priority scoring policy

This layer ranks saved anomaly events after detection. It is a transparent,
configurable facilities-management policy; it is not a learned risk model.

## Inputs

- Event duration from grouped anomaly alerts.
- Fault group/type from the reliability-gated diagnosis output, when available.
- Equipment criticality from a client asset register. The public RBC dataset has
  no such register, so `rbc_ers_ahu` is assigned Medium (3/5) only as a
  documented project assumption.

## Score

Each component has a 1--5 level and is first normalised to 0--1:

`score = 100 × [0.50 × (severity - 1) / 4 + 0.30 × (duration - 1) / 4 + 0.20 × (criticality - 1) / 4]`

The exact mappings, weights, thresholds, and action text are saved in
`configs/priority_policy.yaml` with every generated output.

| Score | Priority | Response |
|---:|---|---|
| 80--100 | Critical | Escalate immediately |
| 60--79.9 | High | Investigate today |
| 40--59.9 | Medium | Inspect during the next shift |
| Below 40 | Low | Monitor in the next review cycle |

## Dataset limitation

The controlled RBC fault sessions span complete recording days. The software
therefore calculates duration correctly, but this dataset cannot validate how
the policy differentiates short and long real incidents. Likewise, severity
and equipment criticality must be confirmed with the client before deployment.
