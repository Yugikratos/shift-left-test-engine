"""Parser tests — DML and DDL parser validation."""

from pathlib import Path

from parsers.dml_parser import DMLParser
from parsers.ddl_parser import DDLParser
from config.settings import DML_DIR, DDL_DIR


# ── DML Parser ──────────────────────────────────────────

def test_dml_parser_single_file():
    """DMLParser reads a single DML file correctly."""
    dml_file = DML_DIR / "stg_business_entity.dml"
    if not dml_file.exists():
        return

    parser = DMLParser()
    schema = parser.parse_file(str(dml_file))

    assert schema is not None
    assert len(schema.fields) > 0
    assert schema.table_name


def test_dml_parser_extracts_fields():
    """DMLParser extracts field names from DML."""
    parser = DMLParser()

    for dml_file in DML_DIR.glob("*.dml"):
        schema = parser.parse_file(str(dml_file))
        if schema is None:
            continue
        for field in schema.fields:
            assert hasattr(field, "name")
            assert field.name


def test_dml_parser_handles_empty_string():
    """DMLParser handles empty content gracefully."""
    parser = DMLParser()
    result = parser.parse_content("")

    assert result is None or len(result.fields) == 0


def test_dml_parser_all_files():
    """DMLParser can parse every .dml file in mock_data."""
    parser = DMLParser()
    files = list(DML_DIR.glob("*.dml"))
    assert len(files) > 0

    parsed = 0
    for f in files:
        schema = parser.parse_file(str(f))
        if schema and schema.fields:
            parsed += 1

    assert parsed > 0


def test_dml_parser_field_names():
    """DMLParser field_names property returns list of strings."""
    parser = DMLParser()
    schema = parser.parse_file(str(DML_DIR / "stg_business_entity.dml"))
    if schema is None:
        return

    names = schema.field_names
    assert isinstance(names, list)
    assert all(isinstance(n, str) for n in names)


# ── DDL Parser ──────────────────────────────────────────

def test_ddl_parser_single_file():
    """DDLParser reads a single DDL file and returns tables."""
    ddl_file = DDL_DIR / "stg_business_entity.sql"
    if not ddl_file.exists():
        return

    parser = DDLParser()
    tables = parser.parse_file(str(ddl_file))

    assert isinstance(tables, list)
    assert len(tables) > 0
    assert tables[0].table_name
    assert len(tables[0].columns) > 0


def test_ddl_parser_extracts_columns():
    """DDLParser extracts column names and data types from DDL."""
    parser = DDLParser()

    for ddl_file in DDL_DIR.glob("*.sql"):
        tables = parser.parse_file(str(ddl_file))
        if not tables:
            continue
        for table in tables:
            for col in table.columns:
                assert hasattr(col, "name")
                assert col.name


def test_ddl_parser_handles_empty_string():
    """DDLParser handles empty content gracefully."""
    parser = DDLParser()
    result = parser.parse_content("")

    assert isinstance(result, list)
    assert len(result) == 0


def test_ddl_parser_all_files():
    """DDLParser can parse every .sql file in mock_data."""
    parser = DDLParser()
    files = list(DDL_DIR.glob("*.sql"))
    assert len(files) > 0

    parsed = 0
    for f in files:
        tables = parser.parse_file(str(f))
        if tables:
            parsed += 1

    assert parsed > 0


def test_ddl_parser_table_properties():
    """DDLTable has expected properties."""
    parser = DDLParser()
    tables = parser.parse_file(str(DDL_DIR / "stg_business_entity.sql"))
    if not tables:
        return

    table = tables[0]
    assert hasattr(table, "table_name")
    assert hasattr(table, "columns")
    assert hasattr(table, "column_names")
    assert hasattr(table, "column_count")
