"""Data Profiling Agent — analyzes DML/DDL metadata to produce a comprehensive profile.

Capabilities:
- Parse DML and DDL files to extract schema information
- Detect PII columns via pattern matching + optional Claude AI analysis
- Infer table relationships via key naming conventions
- Detect SCD-2 patterns (eff_start/end_dt, logc_del_ind)
- Classify fields as business data, PII, control/audit, or metadata
- Recommend subsetting strategy
"""

import json
from pathlib import Path

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from parsers.dml_parser import DMLParser, DMLSchema, parse_all_dmls
from parsers.ddl_parser import DDLParser, DDLTable, parse_all_ddls
from utils.llm_client import llm_client
from config.settings import (
    DML_DIR, DDL_DIR, KNOWLEDGE_BASE_DIR,
    PII_NAME_PATTERNS, PII_ADDRESS_PATTERNS, PII_PHONE_PATTERNS, PII_ID_PATTERNS,
    CONTROL_FIELD_PATTERNS, SCD2_PATTERNS, RELATIONSHIP_KEY_PATTERNS,
)


class ProfilingAgent(BaseAgent):
    """Analyzes source metadata and produces a data profile report."""

    def __init__(self):
        super().__init__("Data Profiling Agent")

    def execute(self, context: dict) -> AgentResult:
        """Execute profiling analysis.

        Expected context keys:
            - dml_dir (optional): Path to DML directory
            - ddl_dir (optional): Path to DDL directory
            - tables (optional): List of specific table names to profile
        """
        dml_dir = Path(context.get("dml_dir", DML_DIR))
        ddl_dir = Path(context.get("ddl_dir", DDL_DIR))
        target_tables = context.get("tables", [])

        # Step 1: Parse all DML and DDL files
        dml_schemas = parse_all_dmls(dml_dir)
        ddl_tables = parse_all_ddls(ddl_dir)

        # Filter to requested tables if specified
        if target_tables:
            target_lower = [t.lower() for t in target_tables]
            dml_schemas = [s for s in dml_schemas if
                           (s.table_name and s.table_name.lower() in target_lower) or
                           Path(s.file_path).stem.lower() in target_lower]
            ddl_tables = [t for t in ddl_tables if
                          (t.table_name and t.table_name.lower() in target_lower)]

        if not dml_schemas and not ddl_tables:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                errors=["No DML or DDL files found to profile"],
                summary="Profiling failed — no metadata files found",
            )

        # Step 2: Profile each table
        profiles = {}
        all_pii_fields = {}
        all_relationships = []
        all_scd2_tables = []

        for schema in dml_schemas:
            table_key = (schema.table_name or Path(schema.file_path).stem).upper()
            profile = self._profile_dml(schema)
            profiles[table_key] = profile

            if profile.get("pii_fields"):
                all_pii_fields[table_key] = profile["pii_fields"]
            if profile.get("is_scd2"):
                all_scd2_tables.append(table_key)

        for ddl_table in ddl_tables:
            table_key = ddl_table.table_name.upper()
            if table_key not in profiles:
                profile = self._profile_ddl(ddl_table)
                profiles[table_key] = profile
                if profile.get("pii_fields"):
                    all_pii_fields[table_key] = profile["pii_fields"]
            else:
                # Merge DDL info (primary index) into existing profile
                profiles[table_key]["primary_index"] = {
                    "columns": ddl_table.primary_index_columns,
                    "is_unique": ddl_table.is_unique_primary_index,
                    "name": ddl_table.primary_index_name,
                }

        # Step 3: Infer cross-table relationships
        all_relationships = self._infer_relationships(profiles)

        # Step 4: AI-enhanced analysis (if Claude API available)
        ai_analysis = self._ai_analyze(profiles, all_relationships)

        # Step 5: Build final profile report
        profile_report = {
            "tables_profiled": len(profiles),
            "total_fields": sum(p.get("field_count", 0) for p in profiles.values()),
            "pii_summary": {
                "tables_with_pii": len(all_pii_fields),
                "total_pii_fields": sum(len(v) for v in all_pii_fields.values()),
                "pii_by_table": all_pii_fields,
            },
            "relationships": all_relationships,
            "scd2_tables": all_scd2_tables,
            "table_profiles": profiles,
            "ai_analysis": ai_analysis,
            "subsetting_strategy": self._recommend_subsetting(profiles, all_relationships),
        }

        # Save to knowledge base
        self._save_profile(profile_report)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data=profile_report,
            summary=(
                f"Profiled {len(profiles)} tables with {profile_report['total_fields']} total fields. "
                f"Found {profile_report['pii_summary']['total_pii_fields']} PII fields across "
                f"{len(all_pii_fields)} tables. "
                f"Detected {len(all_relationships)} cross-table relationships. "
                f"{len(all_scd2_tables)} tables use SCD-2 pattern. "
                f"Mode: {llm_client.mode}"
            ),
        )

    def _profile_dml(self, schema: DMLSchema) -> dict:
        """Profile a single DML schema."""
        fields_info = []
        pii_fields = []
        control_fields = []
        scd2_fields = []
        key_fields = []

        for f in schema.fields:
            classification = self._classify_field(f.name)
            field_info = {
                "name": f.name,
                "type": f.ab_initio_type,
                "max_length": f.maximum_length,
                "teradata_type": f.teradata_type,
                "nullable": f.nullable,
                "not_null": f.is_not_null,
                "classification": classification,
            }
            fields_info.append(field_info)

            if classification == "pii":
                pii_fields.append({
                    "name": f.name,
                    "pii_type": self._detect_pii_type(f.name),
                    "max_length": f.maximum_length,
                })
            elif classification == "control":
                control_fields.append(f.name)
            elif classification == "scd2":
                scd2_fields.append(f.name)
            elif classification == "key":
                key_fields.append(f.name)

        return {
            "source_table": schema.source_table,
            "source_database": schema.source_database,
            "is_typed": schema.is_typed,
            "type_name": schema.type_name,
            "field_count": len(fields_info),
            "fields": fields_info,
            "pii_fields": pii_fields,
            "control_fields": control_fields,
            "scd2_fields": scd2_fields,
            "key_fields": key_fields,
            "is_scd2": len(scd2_fields) >= 2,
            "is_control_table": schema.is_typed or len(control_fields) > len(fields_info) * 0.5,
        }

    def _profile_ddl(self, ddl_table: DDLTable) -> dict:
        """Profile a DDL table definition."""
        fields_info = []
        pii_fields = []

        for c in ddl_table.columns:
            classification = self._classify_field(c.name)
            fields_info.append({
                "name": c.name,
                "type": c.data_type,
                "not_null": c.is_not_null,
                "classification": classification,
            })
            if classification == "pii":
                pii_fields.append({
                    "name": c.name,
                    "pii_type": self._detect_pii_type(c.name),
                    "length": c.length,
                })

        return {
            "source_table": ddl_table.full_name,
            "source_database": ddl_table.database_name,
            "field_count": len(fields_info),
            "fields": fields_info,
            "pii_fields": pii_fields,
            "primary_index": {
                "columns": ddl_table.primary_index_columns,
                "is_unique": ddl_table.is_unique_primary_index,
                "name": ddl_table.primary_index_name,
            },
        }

    def _classify_field(self, name: str) -> str:
        """Classify a field as pii, control, scd2, key, or business."""
        name_lower = name.lower()

        # SCD-2 fields
        for pattern in SCD2_PATTERNS:
            if pattern in name_lower:
                return "scd2"

        # Control/audit fields
        for pattern in CONTROL_FIELD_PATTERNS:
            if pattern in name_lower:
                return "control"

        # PII fields
        for pattern in PII_NAME_PATTERNS + PII_ADDRESS_PATTERNS + PII_PHONE_PATTERNS + PII_ID_PATTERNS:
            if pattern in name_lower:
                return "pii"

        # Key fields
        for pattern in RELATIONSHIP_KEY_PATTERNS:
            if name_lower.endswith(pattern) or name_lower.startswith("business_id"):
                return "key"

        # Filler fields
        if "filler" in name_lower:
            return "filler"

        return "business"

    def _detect_pii_type(self, name: str) -> str:
        """Determine the specific PII category."""
        name_lower = name.lower()

        for p in PII_NAME_PATTERNS:
            if p in name_lower:
                return "PERSON_NAME"
        for p in PII_ADDRESS_PATTERNS:
            if p in name_lower:
                return "ADDRESS"
        for p in PII_PHONE_PATTERNS:
            if p in name_lower:
                return "PHONE"
        for p in PII_ID_PATTERNS:
            if p in name_lower:
                return "IDENTIFIER"

        return "UNKNOWN_PII"

    def _infer_relationships(self, profiles: dict) -> list[dict]:
        """Infer foreign key relationships between tables based on column name matching."""
        relationships = []
        table_keys = {}

        # Collect key-like columns per table
        for table_name, profile in profiles.items():
            keys = []
            for f in profile.get("fields", []):
                f_name = f["name"].lower()
                if any(f_name.endswith(p) for p in ["_id", "_nbr", "_number"]):
                    keys.append(f["name"])
                if f_name == "business_id" or f_name == "bus_nbr":
                    keys.append(f["name"])
            table_keys[table_name] = keys

        # Find matching keys across tables
        table_names = list(table_keys.keys())
        for i in range(len(table_names)):
            for j in range(i + 1, len(table_names)):
                t1, t2 = table_names[i], table_names[j]
                k1, k2 = table_keys[t1], table_keys[t2]

                for key1 in k1:
                    for key2 in k2:
                        # Check if keys match by suffix or are semantically related
                        k1_base = key1.lower().replace("mtch_", "").replace("bus_", "business_")
                        k2_base = key2.lower().replace("mtch_", "").replace("bus_", "business_")

                        if (k1_base == k2_base or
                            key1.lower() == key2.lower() or
                            self._keys_semantically_match(key1, key2)):
                            relationships.append({
                                "table_1": t1,
                                "column_1": key1,
                                "table_2": t2,
                                "column_2": key2,
                                "relationship_type": "inferred_fk",
                                "confidence": "high" if key1.lower() == key2.lower() else "medium",
                            })

        return relationships

    def _keys_semantically_match(self, key1: str, key2: str) -> bool:
        """Check if two key names refer to the same concept."""
        # business_id ↔ bus_nbr ↔ mtch_bus_nbr
        business_keys = {"business_id", "bus_nbr", "mtch_bus_nbr", "mtch_hq_bus_nbr",
                         "ultimate_bus_id", "hq_bus_id", "parent_bus_id"}
        if key1.lower() in business_keys and key2.lower() in business_keys:
            return True

        # etl_cyc_dt + etl_proc_cd (composite key)
        etl_keys = {"etl_cyc_dt", "etl_proc_cd", "etl_cyc_id"}
        if key1.lower() in etl_keys and key2.lower() in etl_keys:
            return True

        return False

    def _recommend_subsetting(self, profiles: dict, relationships: list) -> dict:
        """Generate subsetting strategy recommendations."""
        # Identify anchor table (largest non-control table)
        anchor = None
        max_fields = 0
        for name, profile in profiles.items():
            if not profile.get("is_control_table") and profile.get("field_count", 0) > max_fields:
                max_fields = profile["field_count"]
                anchor = name

        # Build subsetting order based on relationships
        order = [anchor] if anchor else []
        related = set()
        for rel in relationships:
            for tbl in [rel["table_1"], rel["table_2"]]:
                if tbl != anchor and tbl not in related:
                    related.add(tbl)
                    order.append(tbl)

        # Add remaining tables
        for name in profiles:
            if name not in order:
                order.append(name)

        return {
            "anchor_table": anchor,
            "subsetting_order": order,
            "strategy": "referential_subset",
            "description": (
                f"Start with {anchor} as the anchor table. "
                f"Subset by date range and record count, then cascade to related tables "
                f"via foreign key relationships to maintain referential integrity."
            ),
            "join_paths": [
                {"from": r["table_1"], "key": r["column_1"],
                 "to": r["table_2"], "key_to": r["column_2"]}
                for r in relationships
            ],
        }

    def _ai_analyze(self, profiles: dict, relationships: list) -> dict | None:
        """Use Claude API for enhanced analysis (optional)."""
        if not llm_client.enabled:
            return {"mode": "rule_based", "note": "Claude API not configured. Using pattern-based analysis."}

        # Build a concise metadata summary for the LLM
        summary = "Analyze these data warehouse table schemas:\n\n"
        for name, profile in profiles.items():
            summary += f"Table: {name}\n"
            summary += f"  Fields ({profile['field_count']}): "
            field_names = [f["name"] for f in profile.get("fields", [])[:20]]
            summary += ", ".join(field_names)
            if profile["field_count"] > 20:
                summary += f" ... (+{profile['field_count'] - 20} more)"
            summary += "\n"
            if profile.get("pii_fields"):
                summary += f"  Detected PII: {[p['name'] for p in profile['pii_fields']]}\n"
            summary += "\n"

        summary += f"Detected relationships: {json.dumps(relationships, indent=2)}\n"

        system_prompt = """You are a data engineering expert analyzing ETL data warehouse schemas.
Provide analysis in JSON format with these keys:
- data_domain: What business domain this data represents
- table_purposes: Brief description of each table's role
- additional_pii: Any PII fields the rule-based system might have missed
- relationship_notes: Observations about the data model
- subsetting_risks: Potential issues when subsetting this data
- recommendations: Top 3 recommendations for test data generation"""

        result = llm_client.analyze_json(summary, system_prompt)
        if result:
            result["mode"] = "ai_enhanced"
        return result

    def _save_profile(self, profile_report: dict):
        """Save profile report to knowledge base."""
        output_dir = KNOWLEDGE_BASE_DIR / "profiles"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "latest_profile.json"
        with open(output_file, "w") as f:
            json.dump(profile_report, f, indent=2, default=str)
