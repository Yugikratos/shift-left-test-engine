"""Teradata DDL parser.

Parses CREATE TABLE statements to extract:
- Table name, database, storage properties
- Column definitions (name, type, nullability)
- Primary index / unique primary index definitions
"""

import re
from pathlib import Path
from dataclasses import dataclass, field

from utils.logger import get_logger

log = get_logger("ddl_parser")


@dataclass
class DDLColumn:
    """A single column from a CREATE TABLE statement."""
    name: str
    data_type: str           # CHAR(9), INTEGER, DATE, etc.
    char_set: str | None = None
    is_not_null: bool = False
    is_casespecific: bool = False
    format_str: str | None = None

    @property
    def base_type(self) -> str:
        """Base type without size (CHAR, INTEGER, DECIMAL, etc.)."""
        return re.match(r'(\w+)', self.data_type).group(1) if self.data_type else ""

    @property
    def length(self) -> int | None:
        """Extract length from type like CHAR(9) → 9."""
        m = re.search(r'\((\d+)', self.data_type)
        return int(m.group(1)) if m else None


@dataclass
class DDLTable:
    """Represents a parsed CREATE TABLE statement."""
    file_path: str
    database_name: str | None = None
    table_name: str | None = None
    full_name: str | None = None          # database.table
    table_type: str = "MULTISET"          # SET or MULTISET
    fallback: bool = True
    columns: list[DDLColumn] = field(default_factory=list)
    primary_index_columns: list[str] = field(default_factory=list)
    is_unique_primary_index: bool = False
    primary_index_name: str | None = None

    @property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> DDLColumn | None:
        for c in self.columns:
            if c.name.upper() == name.upper():
                return c
        return None

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "database": self.database_name,
            "table_name": self.table_name,
            "full_name": self.full_name,
            "table_type": self.table_type,
            "column_count": self.column_count,
            "primary_index": {
                "columns": self.primary_index_columns,
                "is_unique": self.is_unique_primary_index,
                "name": self.primary_index_name,
            },
            "columns": [
                {
                    "name": c.name,
                    "type": c.data_type,
                    "base_type": c.base_type,
                    "length": c.length,
                    "not_null": c.is_not_null,
                    "charset": c.char_set,
                }
                for c in self.columns
            ],
        }


class DDLParser:
    """Parses Teradata CREATE TABLE DDL statements."""

    # Column definition pattern
    COL_PATTERN = re.compile(
        r'^\s*(\w+)\s+'                          # Column name
        r'((?:CHAR|VARCHAR|INTEGER|BIGINT|SMALLINT|DECIMAL|NUMERIC|DATE|TIMESTAMP|FLOAT|NUMBER)'
        r'(?:\s*\([^)]+\))?)'                    # Data type with optional size
        r'(?:\s+FORMAT\s+\'([^\']+)\')?'          # Optional FORMAT
        r'(?:\s+CHARACTER\s+SET\s+(\w+))?'        # Optional CHARACTER SET
        r'(?:\s+(NOT\s+NULL))?'                   # Optional NOT NULL
        r'(?:\s+(NOT\s+)?CASESPECIFIC)?',         # Optional CASESPECIFIC
        re.IGNORECASE
    )

    def parse_file(self, file_path: str | Path) -> list[DDLTable]:
        """Parse a DDL file — may contain multiple CREATE TABLE statements."""
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return self.parse_content(content, str(file_path))

    def parse_content(self, content: str, file_path: str = "unknown") -> list[DDLTable]:
        """Parse DDL content string."""
        tables = []

        # Split on CREATE statements
        create_blocks = re.split(r'(?=CREATE\s+(?:MULTISET|SET)\s+TABLE)', content, flags=re.IGNORECASE)

        for block in create_blocks:
            block = block.strip()
            if not block or not re.match(r'CREATE\s+', block, re.IGNORECASE):
                continue

            table = self._parse_create_table(block, file_path)
            if table:
                tables.append(table)

        return tables

    def _parse_create_table(self, block: str, file_path: str) -> DDLTable | None:
        """Parse a single CREATE TABLE block."""
        table = DDLTable(file_path=file_path)

        # Extract table name: CREATE MULTISET TABLE schema.table_name
        name_match = re.search(
            r'CREATE\s+(?P<type>MULTISET|SET)\s+TABLE\s+(?P<name>[\w.]+)',
            block, re.IGNORECASE
        )
        if not name_match:
            return None

        table.table_type = name_match.group("type").upper()
        table.full_name = name_match.group("name").strip().rstrip(",")

        parts = table.full_name.split(".")
        if len(parts) == 2:
            table.database_name = parts[0]
            table.table_name = parts[1]
        else:
            table.table_name = table.full_name

        # Check FALLBACK
        table.fallback = "FALLBACK" in block.upper() and "NO FALLBACK" not in block.upper()

        # Extract column block (between first ( and matching ))
        col_block = self._extract_column_block(block)
        if col_block:
            table.columns = self._parse_columns(col_block)

        # Extract primary index
        self._parse_primary_index(block, table)

        return table

    def _extract_column_block(self, block: str) -> str | None:
        """Extract the column definition section between parentheses."""
        # Find the opening paren after MAP = or after table properties
        paren_depth = 0
        start = None

        for i, ch in enumerate(block):
            if ch == '(':
                if paren_depth == 0:
                    start = i + 1
                paren_depth += 1
            elif ch == ')':
                paren_depth -= 1
                if paren_depth == 0 and start is not None:
                    return block[start:i]

        return None

    def _parse_columns(self, col_block: str) -> list[DDLColumn]:
        """Parse column definitions from the column block."""
        columns = []

        # Split by comma, but handle nested parens
        col_defs = self._split_column_defs(col_block)

        for col_def in col_defs:
            col_def = col_def.strip()
            if not col_def:
                continue

            # Skip non-column lines (like MAP, CHECKSUM, etc.)
            if re.match(r'^\s*(NO\s+BEFORE|NO\s+AFTER|CHECKSUM|DEFAULT|MAP)\s', col_def, re.IGNORECASE):
                continue

            col = self._parse_column_def(col_def)
            if col:
                columns.append(col)

        return columns

    def _split_column_defs(self, col_block: str) -> list[str]:
        """Split column block by commas, respecting parentheses."""
        defs = []
        current = []
        depth = 0

        for ch in col_block:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 0:
                defs.append("".join(current))
                current = []
                continue
            current.append(ch)

        if current:
            defs.append("".join(current))

        return defs

    def _parse_column_def(self, col_def: str) -> DDLColumn | None:
        """Parse a single column definition."""
        col_def = col_def.strip()

        match = self.COL_PATTERN.match(col_def)
        if match:
            return DDLColumn(
                name=match.group(1),
                data_type=match.group(2).strip(),
                format_str=match.group(3),
                char_set=match.group(4),
                is_not_null=bool(match.group(5)),
                is_casespecific="CASESPECIFIC" in col_def.upper() and "NOT CASESPECIFIC" not in col_def.upper(),
            )

        # Fallback: try simpler parsing
        simple_match = re.match(r'^\s*(\w+)\s+(\w+(?:\s*\([^)]+\))?)', col_def)
        if simple_match:
            name = simple_match.group(1)
            dtype = simple_match.group(2)
            # Skip keywords that aren't column names
            if name.upper() in ('NO', 'CHECKSUM', 'DEFAULT', 'MAP', 'UNIQUE', 'PRIMARY'):
                return None
            return DDLColumn(
                name=name,
                data_type=dtype,
                is_not_null="NOT NULL" in col_def.upper(),
            )

        return None

    def _parse_primary_index(self, block: str, table: DDLTable):
        """Extract primary index definition."""
        # UNIQUE PRIMARY INDEX name ( col1, col2 )
        pi_match = re.search(
            r'(UNIQUE\s+)?PRIMARY\s+INDEX\s+(\w+)\s*\(\s*([^)]+)\s*\)',
            block, re.IGNORECASE
        )
        if pi_match:
            table.is_unique_primary_index = bool(pi_match.group(1))
            table.primary_index_name = pi_match.group(2)
            table.primary_index_columns = [
                c.strip() for c in pi_match.group(3).split(",")
            ]
            return

        # PRIMARY INDEX ( col1, col2 ) — without name
        pi_match2 = re.search(
            r'(UNIQUE\s+)?PRIMARY\s+INDEX\s*\(\s*([^)]+)\s*\)',
            block, re.IGNORECASE
        )
        if pi_match2:
            table.is_unique_primary_index = bool(pi_match2.group(1))
            table.primary_index_columns = [
                c.strip() for c in pi_match2.group(2).split(",")
            ]


def parse_all_ddls(ddl_dir: str | Path) -> list[DDLTable]:
    """Parse all .sql files in a directory."""
    ddl_dir = Path(ddl_dir)
    parser = DDLParser()
    tables = []

    for ddl_file in sorted(ddl_dir.glob("*.sql")):
        try:
            parsed = parser.parse_file(ddl_file)
            tables.extend(parsed)
        except Exception as e:
            log.warning(f"Failed to parse {ddl_file.name}: {e}")

    return tables


if __name__ == "__main__":
    """Quick test — parse all mock DDLs."""
    from config.settings import DDL_DIR
    print(f"Parsing DDLs from: {DDL_DIR}\n")

    tables = parse_all_ddls(DDL_DIR)
    for t in tables:
        pi_type = "UPI" if t.is_unique_primary_index else "PI"
        print(f"  {t.full_name or t.table_name}")
        print(f"    Columns: {t.column_count}")
        print(f"    {pi_type}:      ({', '.join(t.primary_index_columns)})")
        for c in t.columns[:5]:
            print(f"      - {c.name:<30} {c.data_type:<20} {'NOT NULL' if c.is_not_null else ''}")
        if t.column_count > 5:
            print(f"      ... and {t.column_count - 5} more columns")
        print()
