"""Smart Subsetting Agent — generates referentially-intact data subsets.

Takes the profiling report and produces SQL queries that extract a small
dataset while preserving foreign key relationships across tables.
"""

import re
import pandas as pd
import csv
from pathlib import Path

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from config.settings import BASE_DIR, KNOWLEDGE_BASE_DIR
from sqlalchemy import text, inspect
from utils.database import source_engine


class SubsettingAgent(BaseAgent):
    """Generates and executes subsetting queries to extract test data."""

    def __init__(self):
        super().__init__("Smart Subsetting Agent")

    @staticmethod
    def _sanitize_identifier(name: str) -> str:
        """Validate that a SQL identifier contains only safe characters."""
        if not re.match(r"^\w+$", name):
            raise ValueError(f"Invalid SQL identifier: {name!r}")
        return name

    def execute(self, context: dict) -> AgentResult:
        """Execute subsetting based on profile report.

        Expected context keys:
            - profile_report: Output from ProfilingAgent
            - record_count: Target number of records (default 100)
            - date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} (optional)
            - source_db: Path to source database
        """
        profile = context.get("profile_report", {})
        record_count = context.get("record_count", 100)
        date_range = context.get("date_range", {})
        source_db = context.get("source_db", str(BASE_DIR / "source_data.db"))

        if not profile:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                errors=["No profile report provided"],
            )

        strategy = profile.get("subsetting_strategy", {})
        anchor = strategy.get("anchor_table")
        order = strategy.get("subsetting_order", [])
        relationships = profile.get("relationships", [])

        if not anchor or not order:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                errors=["No subsetting strategy found in profile"],
            )

        # Step 1: Generate SQL queries
        queries = self._generate_queries(anchor, order, relationships, record_count, date_range)

        # Step 2: Execute queries against source DB
        extracted_data = {}
        errors = []
        warnings = []

        try:
            with source_engine.connect() as conn:
                for table_name, query in queries.items():
                    try:
                        # Translate ? parameters to SQLAlchemy named parameters (:p0, :p1, etc.)
                        params_list = query.get("params", [])
                        named_params = {f"p{i}": val for i, val in enumerate(params_list)}
                        
                        sql_text = query["sql"]
                        for i in range(len(params_list)):
                            sql_text = sql_text.replace("?", f":p{i}", 1)

                        df = pd.read_sql(text(sql_text), conn, params=named_params)

                        extracted_data[table_name] = {
                            "columns": df.columns.tolist(),
                            "row_count": len(df),
                            "data": df.fillna("").to_dict(orient="records"),
                            "sql": query["sql"],
                            "query_type": query["type"],
                        }

                        if len(df) == 0:
                            warnings.append(f"{table_name}: No rows returned by subset query")

                    except Exception as e:
                        errors.append(f"{table_name}: Query failed — {str(e)}")

        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                errors=[f"Database connection failed: {str(e)}"],
            )

        # Step 3: Stream extracted data as CSV files to AWS S3
        from utils.storage_client import storage_client
        from config.settings import S3_CSVS_BUCKET
        import io
        import csv
        
        saved_files = {}

        for table_name, table_data in extracted_data.items():
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=table_data["columns"])
            writer.writeheader()
            writer.writerows(table_data["data"])
            
            request_id = context.get("request_id", "local_req")
            object_key = f"{request_id}/{table_name.upper()}_subset.csv"
            storage_client.upload_text(S3_CSVS_BUCKET, object_key, output.getvalue(), "text/csv")
            saved_files[table_name] = f"s3://{S3_CSVS_BUCKET}/{object_key}"

        # Step 4: Validate referential integrity
        integrity_report = self._validate_integrity(extracted_data, relationships)

        result_data = {
            "anchor_table": anchor,
            "tables_extracted": len(extracted_data),
            "total_rows": sum(d["row_count"] for d in extracted_data.values()),
            "extraction_summary": {
                name: {"rows": d["row_count"], "columns": len(d["columns"]), "sql": d["sql"]}
                for name, d in extracted_data.items()
            },
            "saved_files": saved_files,
            "queries": {name: q["sql"] for name, q in queries.items()},
            "integrity_report": integrity_report,
            "extracted_data": extracted_data,
        }

        status = AgentStatus.COMPLETED if not errors else AgentStatus.FAILED
        return AgentResult(
            agent_name=self.name,
            status=status,
            data=result_data,
            errors=errors,
            warnings=warnings,
            summary=(
                f"Extracted {result_data['total_rows']} total rows across "
                f"{len(extracted_data)} tables. "
                f"Anchor: {anchor} ({extracted_data.get(anchor, {}).get('row_count', 0)} rows). "
                f"Integrity: {integrity_report.get('status', 'unknown')}."
            ),
        )

    def _find_date_column(self, table: str, source_db: str) -> str | None:
        """Find a valid date column in the table by checking against known patterns."""
        table = self._sanitize_identifier(table)
        date_candidates = ["bus_cyc_dt", "eff_strt_dt", "eff_sdt", "etl_cyc_dt"]
        try:
            inspector = inspect(source_engine)
            actual_columns = {col["name"].lower() for col in inspector.get_columns(table)}
            for col in date_candidates:
                if col in actual_columns:
                    return col
        except Exception:
            pass
        return None

    def _generate_queries(self, anchor: str, order: list, relationships: list,
                          record_count: int, date_range: dict) -> dict:
        """Generate subsetting SQL queries maintaining referential integrity."""
        queries = {}
        anchor = self._sanitize_identifier(anchor)

        # Anchor table: direct subset with LIMIT
        anchor_where = []
        anchor_params = []

        # Find a valid date column in the anchor table
        source_db = str(BASE_DIR / "source_data.db")
        date_col = self._find_date_column(anchor, source_db)

        if date_col and date_range.get("start"):
            anchor_where.append(f"{self._sanitize_identifier(date_col)} >= ?")
            anchor_params.append(date_range["start"])

        if date_col and date_range.get("end"):
            anchor_where.append(f"{self._sanitize_identifier(date_col)} <= ?")
            anchor_params.append(date_range["end"])

        where_clause = f" WHERE {' AND '.join(anchor_where)}" if anchor_where else ""
        queries[anchor] = {
            "sql": f"SELECT * FROM {anchor}{where_clause} LIMIT {record_count}",
            "params": anchor_params,
            "type": "anchor_subset",
        }

        # Related tables: join back to anchor's key values
        for table_name in order[1:]:
            table_name = self._sanitize_identifier(table_name)
            rel = self._find_relationship(table_name, anchor, relationships)
            if rel:
                # Subset via IN (subquery)
                from_table = rel["from_table"]
                from_col = self._sanitize_identifier(rel["from_col"])
                to_col = self._sanitize_identifier(rel["to_col"])

                queries[table_name] = {
                    "sql": (
                        f"SELECT * FROM {table_name} "
                        f"WHERE {to_col} IN "
                        f"(SELECT {from_col} FROM {anchor}{where_clause} LIMIT {record_count})"
                    ),
                    "params": anchor_params,
                    "type": "referential_subset",
                }
            else:
                # No relationship found — take a simple sample
                queries[table_name] = {
                    "sql": f"SELECT * FROM {table_name} LIMIT {record_count}",
                    "params": [],
                    "type": "independent_sample",
                }

        return queries

    def _find_relationship(self, table: str, anchor: str, relationships: list) -> dict | None:
        """Find a relationship between a table and the anchor."""
        for rel in relationships:
            t1, t2 = rel["table_1"], rel["table_2"]
            c1, c2 = rel["column_1"], rel["column_2"]

            if t1 == anchor and t2 == table:
                return {"from_table": t1, "from_col": c1, "to_table": t2, "to_col": c2}
            if t2 == anchor and t1 == table:
                return {"from_table": t2, "from_col": c2, "to_table": t1, "to_col": c1}

        return None

    def _validate_integrity(self, extracted_data: dict, relationships: list) -> dict:
        """Validate referential integrity across extracted subsets."""
        checks = []
        all_passed = True

        for rel in relationships:
            t1, c1 = rel["table_1"], rel["column_1"]
            t2, c2 = rel["table_2"], rel["column_2"]

            if t1 in extracted_data and t2 in extracted_data:
                keys_1 = set(str(r.get(c1, "")) for r in extracted_data[t1]["data"] if r.get(c1))
                keys_2 = set(str(r.get(c2, "")) for r in extracted_data[t2]["data"] if r.get(c2))

                orphans_in_t2 = keys_2 - keys_1
                overlap = keys_1 & keys_2

                passed = len(orphans_in_t2) == 0 or len(overlap) > 0
                if not passed:
                    all_passed = False

                checks.append({
                    "relationship": f"{t1}.{c1} → {t2}.{c2}",
                    "keys_in_t1": len(keys_1),
                    "keys_in_t2": len(keys_2),
                    "overlap": len(overlap),
                    "orphans_in_t2": len(orphans_in_t2),
                    "passed": passed,
                })

        return {
            "status": "passed" if all_passed else "warnings",
            "checks": checks,
            "total_checks": len(checks),
            "passed": sum(1 for c in checks if c["passed"]),
            "failed": sum(1 for c in checks if not c["passed"]),
        }
