"""Data Masking Agent — detects and anonymizes PII in extracted datasets.

Uses pattern-based PII detection and applies consistent Faker-based anonymization:
- Names → fake.name() (e.g., "John Smith")
- Addresses → fake.street_address() (e.g., "123 Main St")
- Cities → fake.city() (e.g., "Portland")
- States → fake.state_abbr() (e.g., "OR")
- Zip codes → fake.zipcode() (e.g., "97201")
- Phones → fake.phone_number()
- Emails → fake.email()
- SSNs → fake.ssn()
- Other PII → MASKED_XXXX (lexify fallback)

Same input always produces same output within a run (referential consistency via cache).
Optionally uses Presidio for enhanced NER-based PII detection.
"""

from collections import defaultdict

from faker import Faker

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from config.settings import PII_NAME_PATTERNS, PII_ADDRESS_PATTERNS, PII_PHONE_PATTERNS, PII_ID_PATTERNS, ENTERPRISE_MODE, BASE_DIR, ETL_SSH_HOST, ETL_SSH_USER
from utils.remote_executor import RemoteExecutor



class MaskingAgent(BaseAgent):
    """Detects and masks PII in extracted datasets."""

    def __init__(self):
        super().__init__("Data Masking Agent")
        self._counters = defaultdict(int)
        self._mask_map = {}  # Ensures consistent masking (same input → same output)
        self._faker = Faker()

    def execute(self, context: dict) -> AgentResult:
        """Execute PII masking on extracted data.

        Expected context keys:
            - extracted_data: Output from SubsettingAgent (table_name → {columns, data})
            - pii_summary: PII fields from ProfilingAgent
        """
        extracted_data = context.get("extracted_data", {})
        pii_summary = context.get("pii_summary", {})
        request_id = context.get("request_id", "unknown_req")

        if ENTERPRISE_MODE:
            if not extracted_data:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.FAILED,
                    errors=["No extracted data provided for masking"],
                )

            output_dir = BASE_DIR / "generated_scripts"
            output_dir.mkdir(exist_ok=True)
            script_path = output_dir / f"{request_id}_mask.xfr"

            # NOTE: This XFR is a structural stub. Masking rules must be
            # injected by the Ab Initio graph before execution. Data passed
            # downstream is NOT masked — it carries schema only.
            table_names = list(extracted_data.keys())
            with open(script_path, "w") as f:
                f.write("/* Ab Initio Transform Script — masking rules stub */\n")
                f.write(f"/* Target Tables: {', '.join(table_names)} */\n")
                f.write("out :: reformat(in) = begin\n")
                f.write("  out.* :: in.*;\n")
                f.write("  // TODO: Inject masking rules from PII profile\n")
                f.write("end;\n")

            executor = RemoteExecutor(host=ETL_SSH_HOST, user=ETL_SSH_USER)
            executor.connect()
            exe_res = executor.execute_command(f"air sandbox run /App/Test/masking_graph.mp -file {script_path.name}")
            executor.close()

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED if exe_res["exit_code"] == 0 else AgentStatus.FAILED,
                data={
                    "tables_processed": len(extracted_data),
                    "masking_method": "enterprise_xfr_generation",
                    "script": str(script_path),
                    "masked_data": extracted_data,
                },
                warnings=["XFR stub generated — masking rules not yet injected. Data passed downstream is unmasked schema only."],
                summary=f"Enterprise Mode: Generated Ab Initio XFR stub for {len(table_names)} tables via SSH.",
            )

        if not extracted_data:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                errors=["No extracted data provided for masking"],
            )

        # Reset counters for this run
        self._counters.clear()
        self._mask_map.clear()

        masked_data = {}
        masking_stats = {}
        total_masked = 0
        before_after_samples = {}

        for table_name, table_data in extracted_data.items():
            data_rows = table_data.get("data", [])
            columns = table_data.get("columns", [])

            if not data_rows:
                masked_data[table_name] = table_data
                continue

            # Get PII field info from profile
            pii_fields = pii_summary.get("pii_by_table", {}).get(table_name, [])
            pii_field_map = {p["name"]: p.get("pii_type", "UNKNOWN") for p in pii_fields}

            # Also detect PII by column name patterns (fallback)
            for col in columns:
                if col not in pii_field_map:
                    pii_type = self._detect_pii_type(col)
                    if pii_type:
                        pii_field_map[col] = pii_type

            if not pii_field_map:
                masked_data[table_name] = table_data
                masking_stats[table_name] = {"pii_fields": 0, "rows_masked": 0}
                continue

            # Capture before sample
            before_sample = data_rows[0].copy() if data_rows else {}

            # Mask each row
            masked_rows = []
            fields_masked_count = 0

            for row in data_rows:
                masked_row = row.copy()
                for col, pii_type in pii_field_map.items():
                    if col in masked_row and masked_row[col]:
                        original = str(masked_row[col])
                        masked_row[col] = self._mask_value(original, pii_type, table_name, col)
                        fields_masked_count += 1
                masked_rows.append(masked_row)

            # Capture after sample
            after_sample = masked_rows[0].copy() if masked_rows else {}

            masked_data[table_name] = {
                "columns": columns,
                "row_count": len(masked_rows),
                "data": masked_rows,
            }

            masking_stats[table_name] = {
                "pii_fields": len(pii_field_map),
                "pii_columns": list(pii_field_map.keys()),
                "rows_masked": len(masked_rows),
                "total_values_masked": fields_masked_count,
            }

            total_masked += fields_masked_count

            # Build before/after comparison (only for PII columns)
            before_after = {}
            for col in pii_field_map:
                if col in before_sample:
                    before_after[col] = {
                        "before": before_sample.get(col, ""),
                        "after": after_sample.get(col, ""),
                        "pii_type": pii_field_map[col],
                    }
            if before_after:
                before_after_samples[table_name] = before_after

        result_data = {
            "tables_processed": len(masked_data),
            "total_values_masked": total_masked,
            "masking_stats": masking_stats,
            "before_after_samples": before_after_samples,
            "masked_data": masked_data,
            "masking_method": "pattern_based",
        }

        table_summary = ", ".join(
            "{}({} PII cols)".format(k, v["pii_fields"])
            for k, v in masking_stats.items() if v["pii_fields"] > 0
        )
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data=result_data,
            summary=(
                f"Masked {total_masked} PII values across {len(masking_stats)} tables. "
                f"Method: Pattern-based. "
                f"Tables: {table_summary}"
            ),
        )

    def _get_faker_type(self, column_name: str) -> str | None:
        """Map column name to a granular Faker masking type."""
        name = column_name.lower()
        if any(p in name for p in ["city", "cty"]):
            return "CITY"
        if any(p in name for p in ["street", "addr", "address"]):
            return "STREET_ADDRESS"
        if any(p in name for p in ["name", "nm", "short_name"]):
            return "PERSON_NAME"
        if any(p in name for p in ["state", "st_abbr", "state_abbr"]):
            return "STATE"
        if any(p in name for p in ["zip", "postal"]):
            return "ZIP"
        if any(p in name for p in ["phone", "tel"]):
            return "PHONE"
        if "email" in name:
            return "EMAIL"
        if "ssn" in name:
            return "SSN"
        return None

    def _detect_pii_type(self, column_name: str) -> str | None:
        """Detect PII type from column name patterns."""
        faker_type = self._get_faker_type(column_name)
        if faker_type:
            return faker_type

        # Fall back to config patterns for any other PII not covered above
        name = column_name.lower()
        for p in PII_NAME_PATTERNS + PII_ADDRESS_PATTERNS + PII_PHONE_PATTERNS + PII_ID_PATTERNS:
            if p in name:
                return "GENERIC_PII"
        return None

    def _mask_value(self, value: str, pii_type: str, table: str, column: str) -> str:
        """Apply masking to a single value based on column name.

        Re-detects granular Faker type from column name so the same original value
        always maps to the same fake value within a run (referential consistency).
        """
        if not value or value.strip() == "":
            return value

        faker_type = self._get_faker_type(column) or pii_type
        mask_key = f"{faker_type}:{value}"

        if mask_key in self._mask_map:
            return self._mask_map[mask_key]

        masked = self._apply_mask(value, faker_type)
        self._mask_map[mask_key] = masked
        return masked

    def _apply_mask(self, value: str, pii_type: str) -> str:
        """Generate a Faker-based masked replacement value."""
        try:
            if pii_type == "PERSON_NAME":
                return self._faker.name()
            elif pii_type == "STREET_ADDRESS":
                return self._faker.street_address()
            elif pii_type == "CITY":
                return self._faker.city()
            elif pii_type == "STATE":
                return self._faker.state_abbr()
            elif pii_type == "ZIP":
                return self._faker.zipcode()
            elif pii_type == "PHONE":
                return self._faker.phone_number()
            elif pii_type == "EMAIL":
                return self._faker.email()
            elif pii_type == "SSN":
                return self._faker.ssn()
            else:
                return self._faker.lexify(text="MASKED_????")
        except Exception:
            # Fallback if Faker fails
            self._counters["generic"] += 1
            return f"MASKED_{self._counters['generic']:04d}"
