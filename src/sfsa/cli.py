"""Command-line entry point for the SFSA project."""

import argparse
from pathlib import Path

from .config import load_yaml
from .data.manifest import build_real_manifest
from .data.rbc_ashrae1312 import discover_real_files, validate_pairing
from .diagnosis import apply_reliability_policy
from .events import build_events
from .patterns import run_pattern_discovery
from .priorities import build_priority_cards
from .training import run_training


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sfsa")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_info = subparsers.add_parser("run-info", help="Inspect a building configuration")
    run_info.add_argument("--config", required=True, type=Path)
    audit = subparsers.add_parser("audit-rbc", help="Audit the real RBC dataset layout")
    audit.add_argument("--data-root", required=True, type=Path)
    audit.add_argument("--manifest", type=Path)
    train = subparsers.add_parser("train", help="Run a configured real-data benchmark")
    train.add_argument("--building-config", required=True, type=Path)
    train.add_argument("--experiment-config", required=True, type=Path)
    train.add_argument("--results-root", default=Path("results/runs"), type=Path)
    train.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override a resolved configuration value, for example include_weather=true",
    )
    train.add_argument(
        "--allow-audit-failures",
        action="store_true",
        help="Write a diagnostic run even if the required data audit checks fail",
    )
    patterns = subparsers.add_parser("patterns", help="Discover and profile normal operating modes")
    patterns.add_argument("--building-config", required=True, type=Path)
    patterns.add_argument("--experiment-config", required=True, type=Path)
    patterns.add_argument("--results-root", default=Path("results/runs"), type=Path)
    patterns.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")
    patterns.add_argument("--allow-audit-failures", action="store_true")
    events = subparsers.add_parser("events", help="Group saved anomaly rows into rate-limited events")
    events.add_argument("--run-dir", required=True, type=Path)
    events.add_argument(
        "--policy", default=Path("configs/operational_policies/event_grouping.yaml"), type=Path
    )
    events.add_argument("--patterns-run", type=Path, help="Optional P01 normal-mode run for event context")
    events.add_argument("--output-name", default="events", help="Named event subdirectory; default: events")
    reliability = subparsers.add_parser(
        "calibrate-diagnosis",
        help="Gate diagnosis labels using held-out report reliability evidence",
    )
    reliability.add_argument("--run-dir", required=True, type=Path)
    reliability.add_argument("--policy", required=True, type=Path)
    reliability.add_argument("--output-name", default="O01_reliability_gated")
    priority = subparsers.add_parser(
        "prioritise-events",
        help="Create configurable priority cards from saved events and diagnoses",
    )
    priority.add_argument("--events-dir", required=True, type=Path)
    priority.add_argument("--diagnosis-dir", required=True, type=Path)
    priority.add_argument(
        "--policy", default=Path("configs/operational_policies/O02_priority_policy.yaml"), type=Path
    )
    priority.add_argument("--output-name", default="O02_priority_cards")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run-info":
        config = load_yaml(args.config)
        print(f"Building: {config.get('name', args.config.stem)}")
        print(f"Data path: {config.get('data_path', 'not configured')}")
    elif args.command == "audit-rbc":
        records = discover_real_files(args.data_root)
        pairings = validate_pairing(args.data_root)
        print(f"Scenario files: {len(records)}")
        print(f"Fault files: {sum(record.is_fault for record in records)}")
        print(f"Fault pairings checked: {len(pairings)}")
        print(f"Missing baselines: {sum(not item['baseline_present'] for item in pairings)}")
        print(f"Unaligned pairs: {sum(not item['timestamps_aligned'] for item in pairings)}")
        manifest = build_real_manifest(args.data_root)
        validation = manifest["validation"]
        print(f"Audit accepted: {validation['accepted']}")
        if validation["blockers"]:
            print(f"Audit blockers: {'; '.join(validation['blockers'])}")
        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            import json

            args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(f"Saved manifest to {args.manifest}")
    elif args.command == "train":
        run_dir = run_training(
            args.building_config,
            args.experiment_config,
            results_root=args.results_root,
            override_values=args.overrides,
            allow_audit_failures=args.allow_audit_failures,
        )
        print(f"Saved run to {run_dir}")
    elif args.command == "patterns":
        run_dir = run_pattern_discovery(
            args.building_config,
            args.experiment_config,
            results_root=args.results_root,
            override_values=args.overrides,
            allow_audit_failures=args.allow_audit_failures,
        )
        print(f"Saved normal-pattern run to {run_dir}")
    elif args.command == "events":
        output = build_events(
            args.run_dir,
            args.policy,
            patterns_run=args.patterns_run,
            output_name=args.output_name,
        )
        print(f"Saved event artefacts to {output}")
    elif args.command == "calibrate-diagnosis":
        output = apply_reliability_policy(args.run_dir, args.policy, output_name=args.output_name)
        print(f"Saved reliability-policy artefacts to {output}")
    elif args.command == "prioritise-events":
        output = build_priority_cards(
            args.events_dir,
            args.diagnosis_dir,
            args.policy,
            output_name=args.output_name,
        )
        print(f"Saved priority cards to {output}")


if __name__ == "__main__":
    main()
