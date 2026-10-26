"""Static, artefact-only investigation view for report and demonstration use."""

from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path

import pandas as pd

from .utils import write_json


def _table(frame: pd.DataFrame, *, max_rows: int = 100) -> str:
    if frame.empty:
        return "<p>No saved data available for this section.</p>"
    return frame.head(max_rows).to_html(index=False, escape=True, classes="data-table")


def _event_table(events: pd.DataFrame) -> str:
    if events.empty:
        return "<p>No event artefact exists yet. Run <code>sfsa events --run-dir ...</code>.</p>"
    columns = [
        "event_id", "model", "event_outcome", "start_timestamp", "duration_minutes",
        "max_score", "supporting_feature_evidence",
    ]
    available = [column for column in columns if column in events]
    header = "".join(f"<th>{html.escape(column)}</th>" for column in available)
    rows = []
    for record in events.head(200).to_dict("records"):
        values = "".join(
            f"<td>{html.escape(str(record.get(column, '')))}</td>"
            for column in available
        )
        rows.append(f'<tr data-model="{html.escape(str(record.get("model", "")))}">{values}</tr>')
    return (
        f'<table id="events" class="data-table"><thead><tr>{header}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _write_model_figure(metrics: pd.DataFrame, path: Path) -> bool:
    if metrics.empty or not {"model", "f1", "precision", "recall", "fpr"}.issubset(metrics.columns):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = path.parent / ".matplotlib_cache"
    cache_dir.mkdir(exist_ok=True)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(9, 5))
    metrics.set_index("model")[["f1", "precision", "recall", "fpr"]].plot(kind="bar", ax=axis)
    axis.set(title="Held-out model comparison", ylabel="Score", ylim=(0, 1))
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return True


def build_investigation_view(
    run_dir: str | Path, *, patterns_run: str | Path | None = None
) -> Path:
    """Create HTML and PNG outputs using only saved benchmark artefacts."""
    source = Path(run_dir)
    metrics_path = source / "metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Run metrics not found: {metrics_path}")
    output = source / "dashboard"
    output.mkdir(exist_ok=True)
    (output / "figures").mkdir(exist_ok=True)
    metrics = pd.read_csv(metrics_path)
    comparison_path = source / "model_comparison.csv"
    comparison = pd.read_csv(comparison_path) if comparison_path.exists() else metrics
    fault_breakdown_path = source / "metrics_by_fault_group.csv"
    fault_breakdown = (
        pd.read_csv(fault_breakdown_path)
        if fault_breakdown_path.exists()
        else pd.DataFrame()
    )
    events_path = source / "events" / "events.csv"
    events = pd.read_csv(events_path) if events_path.exists() else pd.DataFrame()
    figure_path = output / "figures" / "model_comparison.png"
    chart_created = _write_model_figure(metrics, figure_path)
    manifest_path = source / "data_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    quality = pd.DataFrame([{
        "manifest_accepted": manifest.get("validation", {}).get("accepted"),
        "source_files": len(manifest.get("files", [])),
        "validation_blockers": "; ".join(
            manifest.get("validation", {}).get("blockers", [])
        ),
    }])
    normal_catalogue = pd.DataFrame()
    normal_quality = pd.DataFrame()
    if patterns_run:
        patterns_source = Path(patterns_run)
        catalogue_path = patterns_source / "normal_mode_catalogue.csv"
        normal_catalogue = (
            pd.read_csv(catalogue_path) if catalogue_path.exists() else pd.DataFrame()
        )
        quality_path = patterns_source / "normal_mode_quality.json"
        if quality_path.exists():
            normal_quality = pd.DataFrame([json.loads(quality_path.read_text())])
        for filename in ("normal_modes_pca.png", "normal_modes_by_hour.png"):
            image = patterns_source / "figures" / filename
            if image.exists():
                shutil.copy2(image, output / "figures" / filename)
    model_options = "".join(
        f'<option value="{html.escape(str(model))}">{html.escape(str(model))}</option>'
        for model in sorted(events.get("model", pd.Series(dtype=str)).dropna().unique())
    )
    chart = (
        '<img src="figures/model_comparison.png" alt="Held-out model comparison">'
        if chart_created
        else ""
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SFSA investigation view</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:1400px}}
.data-table{{border-collapse:collapse;width:100%;font-size:.85rem}}
th,td{{border:1px solid #ccc;padding:.4rem;text-align:left;vertical-align:top}}
th{{background:#eef}} img{{max-width:900px;width:100%}}
.note{{background:#fff6dd;padding:1rem}}
</style>
</head><body><h1>Smart Facilities investigation view</h1>
<p class="note">Demonstration only. This page reads saved run artefacts and does
not retrain or query live systems. Controlled HVAC scenario labels are not
verified fault-onset or deployment alerts.</p>
<h2>Dataset quality and coverage</h2>{_table(quality)}
<h2>Held-out model comparison and alert burden</h2>{chart}{_table(comparison)}
<h2>Fault-family, intensity, and season breakdown</h2>{_table(fault_breakdown)}
<h2>Normal operating modes</h2>{_table(normal_quality)}{_table(normal_catalogue)}
<img src="figures/normal_modes_pca.png" alt="Normal operating modes"
onerror="this.style.display='none'">
<h2>Grouped anomaly events</h2>
<label>Model <select id="model"><option value="">All</option>{model_options}</select></label>
{_event_table(events)}
<script>
const eventTable=document.getElementById('events');
if(eventTable)document.getElementById('model').onchange=()=>{{
 const m=document.getElementById('model').value;
 eventTable.querySelectorAll('tbody tr').forEach(r=>r.hidden=m&&r.dataset.model!==m);
}};
</script>
<h2>Sources</h2><ul><li>metrics.csv</li><li>model_comparison.csv</li>
<li>events/events.csv, when generated</li>
<li>alert_explanations.csv, when referenced by events</li></ul></body></html>"""
    html_path = output / "index.html"
    html_path.write_text(page, encoding="utf-8")
    write_json(output / "dashboard_manifest.json", {
        "source_run": str(source),
        "sources": ["metrics.csv", "model_comparison.csv", "events/events.csv"],
        "patterns_run": str(patterns_run) if patterns_run else None,
        "chart_created": chart_created,
    })
    return html_path
