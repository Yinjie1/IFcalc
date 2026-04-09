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

from .calculator import Journal, import_journal, read, write

__all__: list[str] = ["Journal", "read", "import_journal", "write", "plot_from_csv"]


def __getattr__(name: str) -> Any:
    """Lazily expose optional plotting functions.

    This avoids importing matplotlib unless plotting APIs are actually used.
    """

    if name == "plot_from_csv":
        from .plotting import plot_from_csv

        return plot_from_csv
    raise AttributeError(f"module 'IFcalc' has no attribute {name!r}")
