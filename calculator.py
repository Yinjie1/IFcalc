"""Core data model and I/O for IF calculation.

This module provides a `Journal` class for storing citation arrays by year,
plus a `read` function for importing Web of Science exported txt files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
import json
import re
from pathlib import Path
from collections.abc import Iterator

import numpy as np
import numpy.typing as npt

type Year = np.int16
type CitationArray = npt.NDArray[np.int16]
type CitationMap = dict[Year, CitationArray]
type IFResult = dict[Year, np.float16]

_YEAR_PATTERN: re.Pattern[str] = re.compile(r"\b(19|20)\d{2}\b")
_INT16_INFO: np.iinfo[np.int16] = np.iinfo(np.int16)
_JOURNAL_REGISTRY: dict[str, Journal] = {}


def _register_journal(journal: Journal) -> None:
    """Register a journal object in memory by identifier.

    Args:
        journal: Journal instance to register.

    Raises:
        ValueError: If another journal with the same identifier already exists.
    """

    existing: Journal | None = _JOURNAL_REGISTRY.get(journal.identifier)
    if existing is not None and existing is not journal:
        raise ValueError(f"Journal '{journal.identifier}' already exists in memory.")
    _JOURNAL_REGISTRY[journal.identifier] = journal


def _to_camel_case(raw_name: str) -> str:
    """Convert a raw journal name to CamelCase.

    Args:
        raw_name: Original journal name from query text.

    Returns:
        CamelCase journal name.
    """

    words: list[str] = re.findall(r"[A-Za-z0-9]+", raw_name)
    if not words:
        raise ValueError("Journal name is empty or invalid.")
    return "".join(word.capitalize() for word in words)


def _canonicalize_journal_name(raw_name: str) -> str:
    """Canonicalize raw journal name text for stable identifier building.

    This removes descriptive parenthetical suffixes from query text (for example
    `(Publication Titles)`) and normalizes whitespace.

    Args:
        raw_name: Raw journal name segment from query line.

    Returns:
        Canonicalized journal name string.
    """

    without_parentheses: str = re.sub(r"\s*\([^)]*\)", "", raw_name)
    normalized_spaces: str = re.sub(r"\s+", " ", without_parentheses).strip()
    return normalized_spaces


def _parse_query_line(query_line: str) -> tuple[str, str, Year]:
    """Parse journal identifier/name and target citation year from first line.

    The first line is expected to look like:
    "journal name and 2008 or 2009 (Publication Years) ..."

    Args:
        query_line: First line in exported txt file.

    Returns:
        A tuple of `(journal_identifier, journal_name_raw, target_year)`.

    Raises:
        ValueError: If line format is invalid or years cannot be inferred.
    """

    marker: str = " and "
    split_index: int = query_line.lower().find(marker)
    if split_index < 0:
        raise ValueError("Cannot parse query line: missing 'and' separator.")

    raw_journal_name: str = query_line[:split_index].strip()
    canonical_name: str = _canonicalize_journal_name(raw_journal_name)
    journal_identifier: str = _to_camel_case(canonical_name)

    years: list[int] = [int(match.group()) for match in _YEAR_PATTERN.finditer(query_line)]
    if len(years) == 0:
        raise ValueError("Cannot infer publication years from query line.")

    # Normal case: two publication years (y-2, y-1) -> target year y.
    # Fallback case: only one publication year (y-1) -> still compute target y.
    target_year: Year = np.int16(max(years) + 1)
    return journal_identifier, raw_journal_name, target_year


def _parse_csv_rows(lines: list[str], header_index: int) -> tuple[list[str], list[list[str]]]:
    """Parse csv header and rows from txt lines.

    Args:
        lines: Full text lines.
        header_index: Index of csv header line.

    Returns:
        Parsed header and data rows.
    """

    csv_text: str = "\n".join(lines[header_index:])
    reader: csv.reader[str] = csv.reader(csv_text.splitlines())
    all_rows: list[list[str]] = list(reader)
    if not all_rows:
        raise ValueError("No CSV rows found after header.")
    return all_rows[0], all_rows[1:]


def _find_header_index(lines: list[str]) -> int:
    """Find index of CSV header line.

    Args:
        lines: Full file lines.

    Returns:
        Header index.

    Raises:
        ValueError: If no valid header exists.
    """

    for index, line in enumerate(lines):
        if line.startswith('"Title"'):
            return index
    raise ValueError("Cannot find CSV header line starting with 'Title'.")


def _to_citation_array(values: list[int]) -> CitationArray:
    """Convert citation values to int16 numpy array with range check.

    Args:
        values: Citation values.

    Returns:
        Numpy array with dtype int16.

    Raises:
        ValueError: If any citation exceeds int16 range.
    """

    if not values:
        return np.array([], dtype=np.int16)

    min_value: int = min(values)
    max_value: int = max(values)
    if min_value < _INT16_INFO.min or max_value > _INT16_INFO.max:
        raise ValueError(
            "Citation value exceeds int16 range: "
            f"min={min_value}, max={max_value}."
        )
    return np.array(values, dtype=np.int16)


def _trim_sorted(citations: CitationArray, ratio: float) -> CitationArray:
    """Return a trimmed copy from sorted citation values.

    Args:
        citations: Citation array for one target year.
        ratio: Trim ratio per side in [0, 0.5).

    Returns:
        Trimmed citation array.

    Raises:
        ValueError: If no sample remains after trimming.
    """

    sorted_values: CitationArray = np.sort(citations)
    sample_size: int = int(sorted_values.size)
    trim_count: int = int(sample_size * ratio)

    if trim_count == 0:
        return sorted_values

    end_index: int = sample_size - trim_count
    trimmed: CitationArray = sorted_values[trim_count:end_index]
    if trimmed.size == 0:
        raise ValueError("No samples remain after trimming.")
    return trimmed


@dataclass(slots=True)
class Journal:
    """Journal citations grouped by IF target year.

    Attributes:
        identifier: Normalized journal identifier in CamelCase.
        name: Raw journal name from source text.
        _citations: Mapping of target year to citation array.

    Examples:
        >>> journal = Journal(identifier="ChinesePhysicsC", name="chinese physics c")
        >>> journal.append_citations(np.int16(2010), np.array([5, 2, 1], dtype=np.int16))
        >>> journal[np.int16(2010)]
        array([5, 2, 1], dtype=int16)
        >>> len(journal)
        1
        >>> for year in journal:
        ...     print(int(year))
        2010
        >>> list(journal)
        [np.int16(2010)]
        >>> journal.ifCalc(delta=10)
        {np.int16(2010): np.float16(2.0)}
    """

    identifier: str
    name: str
    _citations: CitationMap = field(default_factory=dict)

    @property
    def citations(self) -> CitationMap:
        """Read-only access to citation mapping.

        Returns:
            Dictionary of year to citation arrays.
        """

        return self._citations

    def __getitem__(self, year: int | Year) -> CitationArray:
        year_key: Year = np.int16(year)
        return self._citations[year_key]

    def __len__(self) -> int:
        return len(self._citations)

    def __iter__(self) -> Iterator[Year]:
        return iter(self._citations)

    def append_citations(self, year: int | Year, citations: CitationArray) -> None:
        """Append citation values to an existing year bucket.

        Args:
            year: IF target year.
            citations: Citation values to append.
        """

        year_key: Year = np.int16(year)
        if year_key in self._citations:
            self._citations[year_key] = np.concatenate((self._citations[year_key], citations))
            return
        self._citations[year_key] = citations.copy()

    def ifCalc(self, delta: float) -> IFResult:
        """Calculate IF values by year after trimming top and bottom delta.

        The method does not modify original citation data. Trimming is performed
        on sorted copies per year.

        Args:
            delta: Trimming amount for each tail.
                - `0 <= delta < 0.5` means ratio directly.
                - `1 <= delta < 50` means percentage and will be converted to ratio.

        Returns:
            Dictionary mapping year to trimmed IF value (`np.float16`).

        Raises:
            ValueError: If `delta` is out of range or sample is invalid.

        Examples:
            >>> journal = Journal(identifier="Demo", name="demo")
            >>> journal.append_citations(np.int16(2010), np.array([1, 2, 3, 100], dtype=np.int16))
            >>> journal.ifCalc(delta=25)
            {np.int16(2010): np.float16(2.5)}
        """

        if delta < 0:
            raise ValueError("delta must be non-negative.")

        ratio: float = delta / 100.0 if delta >= 1 else delta
        if ratio >= 0.5:
            raise ValueError("delta is too large; trim ratio must be < 0.5.")

        result: IFResult = {}
        for year, citations in sorted(self._citations.items(), key=lambda item: int(item[0])):
            if citations.size == 0:
                raise ValueError(f"Year {int(year)} has no citation data.")
            trimmed: CitationArray = _trim_sorted(citations, ratio)
            if_value: np.float16 = np.float16(np.mean(trimmed, dtype=np.float64))
            result[np.int16(year)] = if_value
        return result

    def export(self, output_dir: str | Path = "./data") -> Path:
        """Export the whole journal to a JSON file.

        Args:
            output_dir: Directory where JSON file will be written.

        Returns:
            Absolute path of exported JSON file.

        Raises:
            OSError: If output directory or file cannot be written.

        Examples:
            >>> journal = Journal(identifier="Demo", name="demo")
            >>> journal.append_citations(np.int16(2010), np.array([1, 2], dtype=np.int16))
            >>> path = journal.export()
            >>> path.name
            'Demo.json'
        """

        export_dir: Path = Path(output_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        payload: dict[str, object] = {
            "identifier": self.identifier,
            "name": self.name,
            "citations": {
                str(int(year)): citations.astype(np.int16).tolist()
                for year, citations in sorted(self._citations.items(), key=lambda item: int(item[0]))
            },
        }

        file_path: Path = export_dir / f"{self.identifier}.json"
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path.resolve()


def read(file_path: str | Path, journal: Journal | None = None) -> Journal:
    """Read Web of Science txt export and append citations to a Journal.

    The function parses:
    - journal identifier from the first line (before first "and"), converted to CamelCase
    - raw journal name from the same query segment
    - two publication years from the first line
    - target year column as the next year of the publication year range

    Citation values from the target year column are appended, not overwritten.

    Args:
        file_path: Path to exported txt file.
        journal: Existing journal object to append data into.

    Returns:
        A journal object containing merged citation data.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If parsing fails or journal mismatch is detected.

    Examples:
        >>> loaded = read("2010.txt")
        >>> loaded.ifCalc(delta=10)
        {np.int16(2010): np.float16(...)}
    """

    path: Path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content: str = path.read_text(encoding="utf-8-sig")
    lines: list[str] = content.splitlines()
    if not lines:
        raise ValueError("Input file is empty.")

    query_line: str = lines[0].strip()
    parsed_identifier, parsed_name, target_year = _parse_query_line(query_line)

    if journal is None:
        target_journal: Journal = Journal(identifier=parsed_identifier, name=parsed_name)
    else:
        target_journal = journal
        if target_journal.identifier != parsed_identifier:
            raise ValueError(
                "Journal identifier mismatch when appending data: "
                f"expected {target_journal.identifier}, got {parsed_identifier}."
            )

    header_index: int = _find_header_index(lines)
    header, rows = _parse_csv_rows(lines, header_index)

    year_column_name: str = str(int(target_year))
    if year_column_name not in header:
        raise ValueError(f"Target year column '{year_column_name}' not found in header.")
    year_column_index: int = header.index(year_column_name)

    values: list[int] = []
    for row in rows:
        if len(row) <= year_column_index:
            continue
        raw_value: str = row[year_column_index].strip()
        if raw_value == "":
            continue
        try:
            citation: int = int(raw_value)
        except ValueError:
            continue
        values.append(citation)

    citation_array: CitationArray = _to_citation_array(values)
    target_journal.append_citations(target_year, citation_array)
    _register_journal(target_journal)
    return target_journal


def import_journal(file_path: str | Path) -> Journal:
    """Import a journal from exported JSON file.

    The function checks in-memory registry by journal identifier. If a journal
    with the same identifier already exists in memory, import is rejected.

    Args:
        file_path: Path to exported journal JSON file.

    Returns:
        Imported Journal object.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file schema is invalid or same journal is already loaded.

    Examples:
        >>> imported = import_journal("./data/ChinesePhysicsC.json")
        >>> imported.identifier
        'ChinesePhysicsC'
    """

    path: Path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    raw_content: str = path.read_text(encoding="utf-8")
    data: object = json.loads(raw_content)
    if not isinstance(data, dict):
        raise ValueError("Invalid journal JSON: root must be an object.")

    raw_identifier: object = data.get("identifier")
    raw_name: object = data.get("name")
    raw_citations: object = data.get("citations")

    if raw_identifier is None and isinstance(raw_name, str):
        raw_identifier = _to_camel_case(raw_name)

    if not isinstance(raw_identifier, str) or raw_identifier.strip() == "":
        raise ValueError("Invalid journal JSON: 'identifier' must be a non-empty string.")
    if not isinstance(raw_name, str) or raw_name.strip() == "":
        raise ValueError("Invalid journal JSON: 'name' must be a non-empty string.")
    if not isinstance(raw_citations, dict):
        raise ValueError("Invalid journal JSON: 'citations' must be an object.")

    if raw_identifier in _JOURNAL_REGISTRY:
        raise ValueError(f"Journal '{raw_identifier}' already exists in memory.")

    journal: Journal = Journal(identifier=raw_identifier, name=raw_name)
    for raw_year, raw_values in raw_citations.items():
        try:
            year: Year = np.int16(int(raw_year))
        except ValueError as exc:
            raise ValueError(f"Invalid year key in JSON: {raw_year}") from exc

        if not isinstance(raw_values, list):
            raise ValueError(f"Invalid citations for year {raw_year}: must be a list.")

        citation_values: list[int] = []
        for raw_value in raw_values:
            if not isinstance(raw_value, int):
                raise ValueError(f"Invalid citation value for year {raw_year}: {raw_value!r}")
            citation_values.append(raw_value)

        citation_array: CitationArray = _to_citation_array(citation_values)
        journal.append_citations(year, citation_array)

    _register_journal(journal)
    return journal


def write(journal: Journal, *deltas: float) -> Path:
    """Write IF results for multiple deltas into one CSV file.

    CSV format:
    - header: `delta,<year1>,<year2>,...`
    - each row: `delta_value,if_year1,if_year2,...`

    Args:
        journal: Journal object to calculate IF from.
        *deltas: Arbitrary number of trim parameters.

    Returns:
        Absolute path to the generated CSV file.

    Raises:
        ValueError: If no delta is provided.

    Examples:
        >>> j = read("2010.txt")
        >>> path = write(j, 0, 5, 10)
        >>> path.name
        'chinese physics c.csv'
    """

    if len(deltas) == 0:
        raise ValueError("At least one delta value must be provided.")

    years: list[Year] = sorted(journal.citations.keys(), key=int)

    file_path: Path = Path(f"{journal.name}.csv")

    with file_path.open("w", encoding="utf-8", newline="") as fp:
        writer: csv.writer = csv.writer(fp)
        header: list[str] = ["delta", *[str(int(year)) for year in years]]
        writer.writerow(header)

        for delta in deltas:
            if_values: IFResult = journal.ifCalc(delta)
            row: list[str] = [str(delta)]
            for year in years:
                row.append(str(float(if_values[year])))
            writer.writerow(row)

    return file_path.resolve()


def transpose(file_path: str | Path) -> Path:
    """Transpose rows and columns of a CSV file.

    The transposed CSV will be written in the same directory with suffix
    `-t.csv`, and the output path will be returned.

    Args:
        file_path: Source CSV file path.

    Returns:
        Absolute path of transposed CSV file.

    Raises:
        FileNotFoundError: If source file does not exist.
        ValueError: If CSV is empty or has inconsistent row lengths.

    Examples:
        >>> path = transpose("chinese physics c.csv")
        >>> path.name
        'chinese physics c-t.csv'
    """

    path: Path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as fp:
        reader: csv.reader = csv.reader(fp)
        rows: list[list[str]] = list(reader)

    if len(rows) == 0:
        raise ValueError("CSV is empty and cannot be transposed.")

    column_count: int = len(rows[0])
    if column_count == 0:
        raise ValueError("CSV has an empty header row.")

    for index, row in enumerate(rows, start=1):
        if len(row) != column_count:
            raise ValueError(
                f"CSV has inconsistent row length at line {index}: "
                f"expected {column_count}, got {len(row)}."
            )

    transposed_rows: list[list[str]] = [list(column) for column in zip(*rows)]
    output_path: Path = path.with_name(f"{path.stem}-t.csv")

    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer: csv.writer = csv.writer(fp)
        writer.writerows(transposed_rows)

    return output_path.resolve()
