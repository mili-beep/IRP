"""Small shared utilities used by commands and reproducible run records."""

import hashlib
import json
import platform
import random
import sys
from importlib import metadata
from pathlib import Path
from typing import Any


def set_seed(seed: int) -> None:
    """Set the standard-library and NumPy seeds when NumPy is available."""
    random.seed(seed)
    try:
        import numpy as np
    except ImportError:
        return
    np.random.seed(seed)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write a readable JSON run record."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: str | Path) -> str:
    """Return a SHA-256 digest without loading a complete file into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture_environment(project_root: str | Path) -> dict[str, Any]:
    """Capture runtime, dependency, and lock-file details for one run."""
    root = Path(project_root).resolve()
    package_names = ("numpy", "pandas", "PyYAML", "scikit-learn", "joblib")
    packages: dict[str, str | None] = {}
    for package_name in package_names:
        try:
            packages[package_name] = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            packages[package_name] = None

    lock_files: dict[str, dict[str, str | int]] = {}
    for name in ("pyproject.toml", "uv.lock"):
        path = root / name
        if path.exists():
            lock_files[name] = {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }

    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "packages": packages,
        "project_files": lock_files,
    }
