"""Ab Initio DML file parser.

Supports two DML formats:
1. SQL-generated flat records (target DMLs with Teradata type comments)
2. Typed DMLs with 'type X =' and 'metadata type = X' declarations (control DMLs)

Does NOT support EBCDIC/COBOL nested record DMLs (out of scope for POC).
"""

import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class DMLField:
    """Represents a single field parsed from a DML file."""
    name: str
    ab_initio_type: str          # string, decimal, date, datetime
    delimiter: str = "\\x01"
    maximum_length: int | None = None
    nullable: bool = True
    default_null: str | None = None
    teradata_type: str | None = None  # From comment like /*CHAR(9)*/
    is_not_null: bool = False
    format_str: str | None = None     # For date/datetime fields
    sign_reserved: bool = False

    @property
    def display_type(self) -> str:
        """Human-readable type string."""
        if self.teradata_type:
            return self.teradata_type
        base = self.ab_initio_type
        if self.maximum_length:
            return f"{base}({self.maximum_length})"
        return base


@dataclass
class DMLSchema:
    """Represents a parsed DML file."""
    file_path: str
    source_table: str | None = None     # From SQL comment (e.g., FIN_STAGE.STG_BUSINESS_ENTITY)
    source_database: str | None = None  # Database portion
    table_name: str | None = None       # Table portion
    type_name: str | None = None        # For typed DMLs (e.g., ETL_SRC_CTL_T)
    generated_date: str | None = None
    fields: list[DMLField] = field(default_factory=list)
    is_typed: bool = False
    has_metadata_type: bool = False
    raw_sql: str | None = None          # Original SQL from comment

    @property
    def field_count(self) -> int:
        return len(self.fields)

    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]

    def get_field(self, name: str) -> DMLField | None:
        for f in self.fields:
            if f.name.lower() == name.lower():
                return f
        return None

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "source_table": self.source_table,
            "source_database": self.source_database,
            "table_name": self.table_name,
            "type_name": self.type_name,
            "is_typed": self.is_typed,
            "field_count": self.field_count,
            "fields": [
                {
                    "name": f.name,
                    "type": f.ab_initio_type,
                    "max_length": f.maximum_length,
                    "nullable": f.nullable,
                    "teradata_type": f.teradata_type,
                    "not_null": f.is_not_null,
                    "format": f.format_str,
                }
                for f in self.fields
            ],
        }


class DMLParser:
    """Parses Ab Initio DML files into structured DMLSchema objects."""

    # Regex patterns for field parsing
    FIELD_PATTERN = re.compile(
        r'^\s*'
        r'(?P<type>string|decimal|date|datetime)'  # Ab Initio type
        r'\s*\('
        r'(?P<params>[^)]*(?:\([^)]*\)[^)]*)*)'   # Parameters (handles nested parens)
        r'\)\s*'
        r'(?:\(\s*"(?P<delim>[^"]*)"\s*\)\s*)?'    # Optional delimiter
        r'(?P<name>\w+)'                            # Field name
        r'(?:\s*=\s*NULL\(\s*"(?P<null_val>[^"]*)"\s*\))?'  # Optional NULL default
        r'\s*(?:/\*(?P<comment>[^*]*)\*/)?'         # Optional Teradata type comment
        r'\s*;'
    )

    # Simpler pattern for fields with format strings like date("YYYY-MM-DD")
    DATE_FIELD_PATTERN = re.compile(
        r'^\s*'
        r'(?P<type>date|datetime)\s*\(\s*"(?P<format>[^"]+)"\s*\)'
        r'\s*\(\s*"(?P<delim>[^"]*)"\s*\)\s*'
        r'(?P<name>\w+)'
        r'(?:\s*=\s*NULL\(\s*"(?P<null_val>[^"]*)"\s*\))?'
        r'\s*(?:/\*(?P<comment>[^*]*)\*/)?'
        r'\s*;'
    )

    # Pattern for string/decimal fields
    STR_DEC_PATTERN = re.compile(
        r'^\s*'
        r'(?P<type>string|decimal)\s*\(\s*"(?P<delim>[^"]*)"\s*'
        r'(?:,\s*maximum_length\s*=\s*(?P<maxlen>\d+))?'
        r'(?:,\s*(?P<precision>\d+))?'
        r'(?:,\s*maximum_length\s*=\s*(?P<maxlen2>\d+))?'
        r'(?:,\s*sign_reserved)?'
        r'\s*\)\s*'
        r'(?P<name>\w+)'
        r'(?:\s*=\s*NULL\(\s*"(?P<null_val>[^"]*)"\s*\))?'
        r'\s*(?:/\*(?P<comment>[^*]*)\*/)?'
        r'\s*;'
    )

    # Pattern for newline terminator
    NEWLINE_PATTERN = re.compile(
        r'^\s*string\s*\(\s*1\s*\)\s*newline\s*=\s*"\\n"\s*;'
    )

    def parse_file(self, file_path: str | Path) -> DMLSchema:
        """Parse a DML file and return a DMLSchema object."""
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return self.parse_content(content, str(file_path))

    def parse_content(self, content: str, file_path: str = "unknown") -> DMLSchema:
        """Parse DML content string into a DMLSchema."""
        schema = DMLSchema(file_path=file_path)
        lines = content.split("\n")

        # Extract header comments for source table info
        self._parse_header(lines, schema)

        # Check if typed DML
        self._parse_type_declaration(lines, schema)

        # Parse fields
        self._parse_fields(lines, schema)

        # Derive table name from file path if not found in header
        if not schema.table_name:
            schema.table_name = Path(file_path).stem

        return schema

    def _parse_header(self, lines: list[str], schema: DMLSchema):
        """Extract source table and generation info from header comments."""
        for line in lines:
            line = line.strip()

            # Match: /* DML Generated for SQL: SELECT * FROM SCHEMA.TABLE
            sql_match = re.search(
                r'DML Generated for SQL:\s*(?:SELECT\s+.*?\s+FROM\s+)?(\w+\.\w+)',
                line, re.IGNORECASE
            )
            if sql_match:
                schema.source_table = sql_match.group(1)
                parts = schema.source_table.split(".")
                if len(parts) == 2:
                    schema.source_database = parts[0]
                    schema.table_name = parts[1]

            # Also check for simpler: /* DML Generated for SQL: select col1, col2 ... from SCHEMA.TABLE
            from_match = re.search(r'\bfrom\s+(\w+\.\w+)', line, re.IGNORECASE)
            if from_match and not schema.source_table:
                schema.source_table = from_match.group(1)
                parts = schema.source_table.split(".")
                if len(parts) == 2:
                    schema.source_database = parts[0]
                    schema.table_name = parts[1]

            # Match: * On: Wed Nov 25 06:00:21 2015
            date_match = re.search(r'\*\s*On:\s*(.+)', line)
            if date_match:
                schema.generated_date = date_match.group(1).strip()

    def _parse_type_declaration(self, lines: list[str], schema: DMLSchema):
        """Detect typed DMLs with 'type X =' declarations."""
        for line in lines:
            line = line.strip()

            # Match: type ETL_SRC_CTL_T =
            type_match = re.match(r'^type\s+(\w+)\s*=', line)
            if type_match:
                schema.type_name = type_match.group(1)
                schema.is_typed = True

            # Match: metadata type = ETL_SRC_CTL_T
            meta_match = re.match(r'^metadata\s+type\s*=\s*(\w+)', line)
            if meta_match:
                schema.has_metadata_type = True

    def _parse_fields(self, lines: list[str], schema: DMLSchema):
        """Parse individual field definitions."""
        in_record = False

        for line in lines:
            stripped = line.strip()

            # Track record block
            if stripped.startswith("record"):
                in_record = True
                continue
            if stripped == "end" or stripped.startswith("end;"):
                in_record = False
                continue

            if not in_record:
                continue

            # Skip comments, empty lines, newline terminator
            if stripped.startswith("/*") or stripped.startswith("/***"):
                continue
            if not stripped or stripped.startswith("//"):
                continue
            if self.NEWLINE_PATTERN.match(stripped):
                continue

            # Try to parse the field
            field = self._parse_field_line(stripped)
            if field:
                schema.fields.append(field)

    def _parse_field_line(self, line: str) -> DMLField | None:
        """Parse a single field definition line."""

        # Try date/datetime pattern first
        match = self.DATE_FIELD_PATTERN.match(line)
        if match:
            return self._build_field_from_date_match(match)

        # Try general pattern via manual parsing (more reliable than complex regex)
        return self._manual_parse(line)

    def _build_field_from_date_match(self, match) -> DMLField:
        """Build DMLField from a date/datetime regex match."""
        comment = match.group("comment") or ""
        return DMLField(
            name=match.group("name"),
            ab_initio_type=match.group("type"),
            format_str=match.group("format"),
            delimiter=match.group("delim") or "\\x01",
            nullable=match.group("null_val") is not None or "NULL" in comment,
            default_null=match.group("null_val"),
            teradata_type=self._extract_teradata_type(comment),
            is_not_null="NOT NULL" in comment,
        )

    def _manual_parse(self, line: str) -> DMLField | None:
        """Manually parse a field line — more robust than regex for complex cases."""
        try:
            # Remove trailing semicolon
            line = line.rstrip(";").strip()

            # Extract comment if present
            comment = ""
            comment_match = re.search(r'/\*(.+?)\*/', line)
            if comment_match:
                comment = comment_match.group(1)
                line = line[:comment_match.start()].strip()

            # Extract NULL default if present
            null_val = None
            null_match = re.search(r'=\s*NULL\(\s*"([^"]*)"\s*\)', line)
            if null_match:
                null_val = null_match.group(1)
                line = line[:null_match.start()].strip()

            # Now line should be: type(...) field_name
            # Find field name (last word)
            parts = line.rsplit(None, 1)
            if len(parts) < 2:
                return None

            field_name = parts[1].strip()
            type_def = parts[0].strip()

            # Parse type definition
            type_match = re.match(r'(string|decimal|date|datetime)\s*\(', type_def)
            if not type_match:
                return None

            ab_type = type_match.group(1)

            # Extract parameters
            max_length = None
            format_str = None
            delimiter = "\\x01"
            sign_reserved = False

            len_match = re.search(r'maximum_length\s*=\s*(\d+)', type_def)
            if len_match:
                max_length = int(len_match.group(1))

            fmt_match = re.search(r'"(YYYY[^"]*)"', type_def)
            if fmt_match:
                format_str = fmt_match.group(1)

            delim_match = re.search(r'"(\\x01)"', type_def)
            if delim_match:
                delimiter = delim_match.group(1)

            if "sign_reserved" in type_def:
                sign_reserved = True

            return DMLField(
                name=field_name,
                ab_initio_type=ab_type,
                delimiter=delimiter,
                maximum_length=max_length,
                nullable=null_val is not None or "NULL" in comment,
                default_null=null_val,
                teradata_type=self._extract_teradata_type(comment),
                is_not_null="NOT NULL" in comment,
                format_str=format_str,
                sign_reserved=sign_reserved,
            )

        except Exception:
            return None

    def _extract_teradata_type(self, comment: str) -> str | None:
        """Extract Teradata type from DML comment like 'CHAR(9) CHARACTER SET LATIN NOT NULL'."""
        if not comment:
            return None
        comment = comment.strip().rstrip("*/").strip()
        # Get just the type part (CHAR(9), INTEGER, DATE, TIMESTAMP(6), etc.)
        type_match = re.match(
            r'(CHAR\(\d+\)|VARCHAR\(\d+\)|INTEGER|BIGINT|DECIMAL\(\d+(?:,\d+)?\)|DATE|TIMESTAMP\(\d+\))',
            comment
        )
        if type_match:
            return type_match.group(1)
        return comment.split()[0] if comment else None


def parse_all_dmls(dml_dir: str | Path) -> list[DMLSchema]:
    """Parse all .dml files in a directory."""
    dml_dir = Path(dml_dir)
    parser = DMLParser()
    schemas = []

    for dml_file in sorted(dml_dir.glob("*.dml")):
        try:
            schema = parser.parse_file(dml_file)
            schemas.append(schema)
        except Exception as e:
            print(f"  Warning: Failed to parse {dml_file.name}: {e}")

    return schemas


if __name__ == "__main__":
    """Quick test — parse all mock DMLs."""
    from config.settings import DML_DIR
    print(f"Parsing DMLs from: {DML_DIR}\n")

    schemas = parse_all_dmls(DML_DIR)
    for s in schemas:
        print(f"  {s.table_name or s.file_path}")
        print(f"    Source: {s.source_table or 'N/A'}")
        print(f"    Type:   {'Typed (' + s.type_name + ')' if s.is_typed else 'Flat Record'}")
        print(f"    Fields: {s.field_count}")
        for f in s.fields[:5]:
            print(f"      - {f.name:<30} {f.display_type:<20} {'NOT NULL' if f.is_not_null else 'NULLABLE'}")
        if s.field_count > 5:
            print(f"      ... and {s.field_count - 5} more fields")
        print()
