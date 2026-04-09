"""IF calculation package.

Public API:
- `Journal`: journal citation container.
- `read`: import citations from Web of Science txt export.
"""

from .calculator import Journal, read

__all__: list[str] = ["Journal", "read"]
