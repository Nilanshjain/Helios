"""Download NAB and SMD datasets into ``data/`` on first run.

Both datasets are public and small enough (~50 MB combined) to keep locally
without committing. The data/ directory is gitignored.

Sources:
    NAB: https://github.com/numenta/NAB (Apache 2.0)
        - data/ : 58 labeled CSV time series
        - labels/combined_windows.json : anomaly windows per stream
    SMD: https://github.com/NetManAIOps/OmniAnomaly/tree/master/ServerMachineDataset (MIT)
        - train/  : pure normal training data (28 machines)
        - test/   : test data with anomalies
        - test_label/ : per-timestep anomaly labels (1 = anomaly)

We clone the repos shallowly to avoid pulling history. If git is unavailable
we fall back to fetching specific files via HTTPS.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
NAB_DIR = DATA_ROOT / "nab"
SMD_DIR = DATA_ROOT / "smd"

NAB_REPO = "https://github.com/numenta/NAB.git"
SMD_REPO = "https://github.com/NetManAIOps/OmniAnomaly.git"


def _have_git() -> bool:
    return shutil.which("git") is not None


def _shallow_clone(repo: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", repo, str(dest)],
        check=True,
    )


def ensure_nab(force: bool = False) -> Path:
    """Download NAB if not already present. Returns the local NAB path."""
    if NAB_DIR.exists() and not force:
        return NAB_DIR
    if not _have_git():
        raise RuntimeError(
            "git is required to download NAB. Install git or place a clone at "
            f"{NAB_DIR}"
        )
    if NAB_DIR.exists():
        shutil.rmtree(NAB_DIR)
    print(f"Cloning NAB into {NAB_DIR} (one-time, ~30 MB)...")
    _shallow_clone(NAB_REPO, NAB_DIR)
    return NAB_DIR


def ensure_smd(force: bool = False) -> Path:
    """Download SMD if not already present. Returns the local SMD path.

    SMD lives inside the OmniAnomaly repo under ServerMachineDataset/.
    We clone the whole repo (small) and return the inner path.
    """
    smd_inner = SMD_DIR / "ServerMachineDataset"
    if smd_inner.exists() and not force:
        return smd_inner
    if not _have_git():
        raise RuntimeError(
            "git is required to download SMD. Install git or place a clone of "
            f"OmniAnomaly at {SMD_DIR}"
        )
    if SMD_DIR.exists():
        shutil.rmtree(SMD_DIR)
    print(f"Cloning OmniAnomaly (for SMD) into {SMD_DIR} (one-time, ~20 MB)...")
    _shallow_clone(SMD_REPO, SMD_DIR)
    if not smd_inner.exists():
        raise RuntimeError(f"Expected SMD path not found after clone: {smd_inner}")
    return smd_inner
