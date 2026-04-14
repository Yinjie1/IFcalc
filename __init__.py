"""IF calculation package.

Public API:
- `Journal`: journal citation container.
- `read`: import citations from Web of Science txt export.
- `import_journal`: load a Journal from exported JSON.
- `write`: export IF table for one journal and multiple deltas.

Optional plotting API (lazy import):
- `plot_from_csv`: draw IF curves from CSV written by `write(...)`.
"""

from typing import Any
from pathlib import Path

from .calculator import Journal, analyse, import_journal, read, transpose, write

__all__: list[str] = [
    "Journal",
    "read",
    "import_journal",
    "write",
    "analyse",
    "transpose",
    "plot_from_csv",
    "plot_analysis_from_csv",
    "plot_decrease_from_csv",
]


def plot_from_csv(csv_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Lazily draw IF curves from CSV exported by `write(...)`.

    This wrapper keeps plotting optional and avoids importing plotting code
    until the function is actually called.
    """

    from .plotting import plot_from_csv as _plot_from_csv

    return _plot_from_csv(csv_path, output_path)


def plot_analysis_from_csv(csv_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Lazily draw mean/std analysis plot from analysis CSV."""

    from .plotting import plot_analysis_from_csv as _plot_analysis_from_csv

    return _plot_analysis_from_csv(csv_path, output_path)


def plot_decrease_from_csv(csv_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Lazily draw decrease curves from decrease CSV."""

    from .plotting import plot_decrease_from_csv as _plot_decrease_from_csv

    return _plot_decrease_from_csv(csv_path, output_path)
