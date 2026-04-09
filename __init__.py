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

from .calculator import Journal, import_journal, read, write

__all__: list[str] = ["Journal", "read", "import_journal", "write", "plot_from_csv"]


def plot_from_csv(csv_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Lazily draw IF curves from CSV exported by `write(...)`.

    This wrapper keeps plotting optional and avoids importing plotting code
    until the function is actually called.
    """

    from .plotting import plot_from_csv as _plot_from_csv

    return _plot_from_csv(csv_path, output_path)
