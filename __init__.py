"""IF calculation package.

Public API:
- `Journal`: journal citation container.
- `read`: import citations from Web of Science txt export.
- `import_journal`: load a Journal from exported JSON.
- `write`: export IF table for one journal and multiple deltas.
"""

from .calculator import Journal, import_journal, read, write

__all__: list[str] = ["Journal", "read", "import_journal", "write"]
