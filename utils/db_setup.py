"""Database initialization — creates SQLite tables mirroring Teradata schemas and seeds with Faker data."""

import sqlite3
import random
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from faker import Faker
    fake = Faker()
except ImportError:
    fake = None

from config.settings import BASE_DIR


SOURCE_DB_PATH = BASE_DIR / "source_data.db"
TARGET_DB_PATH = BASE_DIR / "target_test.db"


# ── Schema Definitions (SQLite equivalents of Teradata tables) ──────────

SCHEMAS = {
    "stg_business_entity": """
        CREATE TABLE IF NOT EXISTS stg_business_entity (
            bus_cyc_dt TEXT NOT NULL,
            rec_seq_nbr INTEGER NOT NULL,
            dw_load_publ_id INTEGER NOT NULL,
            business_id TEXT NOT NULL,
            bus_short_name TEXT,
            trade_short_name TEXT,
            phys_street_addr TEXT,
            phys_city TEXT,
            phys_state_abbr TEXT,
            phys_zip_cd TEXT,
            phys_zip4_cd TEXT,
            mail_addr_line TEXT,
            mail_city TEXT,
            mail_state_abbr TEXT,
            mail_zip_cd TEXT,
            mail_zip4_cd TEXT,
            carrier_rte_cd TEXT,
            delivery_pt_cd TEXT,
            geo_natl_cd INTEGER,
            geo_state_cd TEXT,
            geo_cnty_cd TEXT,
            geo_city_cd TEXT,
            geo_smsa_cd INTEGER,
            fips_state_cd TEXT,
            fips_cnty_cd TEXT,
            fips_msa_cd INTEGER,
            bus_area_cd TEXT,
            bus_exchng_nbr TEXT,
            bus_ext_nbr TEXT,
            exec_first_nm TEXT,
            exec_mid_init TEXT,
            exec_last_nm TEXT,
            exec_suffix TEXT,
            exec_prefix TEXT,
            exec_title TEXT,
            exec_mrc TEXT,
            annual_sales_volume INTEGER,
            sales_vol_ind TEXT,
            employee_cnt INTEGER,
            emp_est_ind TEXT,
            employees_here_cnt INTEGER,
            emp_here_est_ind TEXT,
            bus_year_started INTEGER,
            bus_status_ind TEXT,
            bus_subsid_ind TEXT,
            mnfctr_ind TEXT,
            ultimate_bus_id TEXT,
            hq_bus_id TEXT,
            parent_bus_id TEXT,
            hqp_city TEXT,
            hqp_state_abbr TEXT,
            hier_cd TEXT,
            dias_cd TEXT,
            population_cd TEXT,
            trans_cd TEXT,
            report_date TEXT,
            orphan_br_ind TEXT,
            rec_class_type TEXT,
            bus_type TEXT,
            dw_updt_publ_id INTEGER
        )
    """,

    "business_credit_score": """
        CREATE TABLE IF NOT EXISTS business_credit_score (
            bus_nbr TEXT NOT NULL,
            eff_strt_dt TEXT NOT NULL,
            row_typ_cd TEXT NOT NULL,
            row_ver_nbr TEXT NOT NULL,
            eff_end_dt TEXT,
            cr_scor_risk_clss_cd TEXT,
            cr_risk_pct INTEGER,
            cr_risk_pt_val TEXT,
            finc_strss_scor_cd TEXT,
            finc_pct INTEGER,
            finc_strss_raw_scor TEXT,
            logc_del_ind TEXT,
            dw_load_publ_id INTEGER,
            dw_updt_publ_id INTEGER,
            viabl_rt TEXT
        )
    """,

    "business_address_match": """
        CREATE TABLE IF NOT EXISTS business_address_match (
            addr_match_nbr TEXT NOT NULL,
            eff_sdt TEXT NOT NULL,
            eff_edt TEXT,
            acct_nm TEXT,
            acct_str_addr TEXT,
            acct_cty_nm TEXT,
            acct_st_abbr TEXT,
            mtch_zip_9_cd TEXT,
            wh_ind TEXT,
            mtch_bus_nbr TEXT,
            mtch_hq_bus_nbr TEXT,
            mtch_confid_cd TEXT,
            accrcy_pct_amt TEXT,
            pri_addr TEXT,
            sec_addr TEXT,
            mtch_sts_ind TEXT,
            dw_load_publ_id INTEGER,
            dw_updt_publ_id INTEGER
        )
    """,

    "etl_cyc_ctl": """
        CREATE TABLE IF NOT EXISTS etl_cyc_ctl (
            etl_cyc_dt TEXT NOT NULL,
            etl_proc_cd TEXT NOT NULL,
            etl_cyc_strt_ts TEXT,
            etl_cyc_end_ts TEXT,
            etl_cyc_freq_cd TEXT,
            etl_cyc_sts_cd TEXT,
            etl_cyc_id INTEGER
        )
    """,

    "etl_src_ctl": """
        CREATE TABLE IF NOT EXISTS etl_src_ctl (
            etl_cyc_dt TEXT NOT NULL,
            etl_proc_cd TEXT NOT NULL,
            src_cd TEXT NOT NULL,
            etl_rec_cnt INTEGER,
            ctl_rec_cnt INTEGER,
            etl_src_strt_ts TEXT,
            etl_src_end_ts TEXT,
            etl_src_sts_cd TEXT,
            etl_src_sts_rsn_cd TEXT,
            etl_src_file_chkum_txt TEXT,
            src_cyc_dt TEXT,
            src_file_nm TEXT,
            src_ctl_file_nm TEXT,
            dw_pubtn_src_cd TEXT NOT NULL,
            etl_cyc_id INTEGER
        )
    """,
}


STATES = ["NY", "CA", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI",
          "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI"]

BUS_TITLES = ["CEO", "CFO", "COO", "CTO", "VP", "Director", "President", "Manager"]


def generate_business_id() -> str:
    return f"{random.randint(100000000, 999999999)}"


def seed_source_data(db_path: Path, num_businesses: int = 200):
    """Seed the source database with realistic fake data."""
    if not fake:
        print("  Faker not installed. Run: pip install faker")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create tables
    for table_name, ddl in SCHEMAS.items():
        cursor.execute(ddl)

    # Generate business IDs for relational integrity
    bus_ids = [generate_business_id() for _ in range(num_businesses)]

    # Create hierarchies (ultimate → parent → subsidiary)
    ultimate_ids = bus_ids[:20]
    parent_ids = bus_ids[:50]

    cyc_dt = "2024-11-20"
    publ_id = 200102348

    # ── Seed stg_business_entity ──
    print(f"  Seeding stg_business_entity with {num_businesses} records...")
    for i, bid in enumerate(bus_ids):
        state = random.choice(STATES)
        cursor.execute("""
            INSERT INTO stg_business_entity VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            cyc_dt, i + 1, publ_id, bid,
            fake.company()[:30], fake.company_suffix()[:30],
            fake.street_address()[:25], fake.city()[:20], state,
            fake.zipcode()[:5], fake.zipcode()[:4],
            fake.street_address()[:25], fake.city()[:20], state,
            fake.zipcode()[:5], fake.zipcode()[:4],
            f"R{random.randint(1,99):03d}", str(random.randint(10, 99)),
            random.randint(1, 840), state[:2], str(random.randint(1, 200)).zfill(3),
            str(random.randint(1, 9999)).zfill(4), random.randint(1, 400),
            state[:2], str(random.randint(1, 200)).zfill(3), random.randint(1000, 9999),
            str(random.randint(200, 999)), str(random.randint(200, 999)),
            str(random.randint(1000, 9999)),
            fake.first_name()[:13], fake.random_letter().upper(),
            fake.last_name()[:15],
            random.choice(["Jr", "Sr", "III", ""]),
            random.choice(["Mr", "Mrs", "Ms", "Dr", ""]),
            random.choice(BUS_TITLES)[:30],
            str(random.randint(1000, 9999)),
            random.randint(100000, 999999999),
            random.choice(["A", "E", ""]),
            random.randint(1, 50000),
            random.choice(["A", "E", ""]),
            random.randint(1, 5000),
            random.choice(["A", "E", ""]),
            random.randint(1900, 2024),
            random.choice(["1", "2", "3"]),
            random.choice(["Y", "N"]),
            random.choice(["Y", "N"]),
            random.choice(ultimate_ids),
            random.choice(parent_ids[:30]),
            random.choice(parent_ids),
            fake.city()[:20], random.choice(STATES),
            random.choice(["0", "1", "2", "3"]),
            str(random.randint(100000000, 999999999)),
            random.choice(["A", "B", "C"]),
            random.choice(["A", "B", ""]),
            "202411", random.choice(["Y", "N", ""]),
            random.choice(["1", "2", "3"]),
            random.choice(["C", "S", "P"]),
            publ_id,
        ))

    # ── Seed business_credit_score ──
    print(f"  Seeding business_credit_score...")
    for bid in bus_ids:
        start_dt = fake.date_between(start_date="-3y", end_date="-1y")
        cursor.execute("""
            INSERT INTO business_credit_score VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bid, start_dt.isoformat(), "A", "001", "9999-12-31",
            random.choice(["1", "2", "3", "4", "5"]),
            random.randint(1, 100), str(random.randint(100, 999)),
            random.choice(["A", "B", "C", "D"]),
            random.randint(1, 100), str(random.randint(1000, 9999)),
            "N", publ_id, publ_id,
            str(random.randint(10, 99)) + "." + str(random.randint(0, 9)),
        ))

    # ── Seed business_address_match ──
    print(f"  Seeding business_address_match...")
    addr_nbr = 100000000
    for bid in bus_ids:
        addr_nbr += 1
        start_dt = fake.date_between(start_date="-2y", end_date="-6m")
        state = random.choice(STATES)
        cursor.execute("""
            INSERT INTO business_address_match VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            str(addr_nbr), start_dt.isoformat(), "9999-12-31",
            fake.company()[:30], fake.street_address()[:30],
            fake.city()[:30], state,
            fake.zipcode()[:9],
            random.choice(["W", "R", ""]),
            bid,
            random.choice(parent_ids[:30]),
            random.choice(["A", "B", "C"]),
            str(random.randint(80, 99)),
            fake.street_address()[:46],
            fake.secondary_address()[:12] if random.random() > 0.5 else "",
            random.choice(["A", "M", ""]),
            publ_id, publ_id,
        ))

    # ── Seed ETL control tables ──
    print(f"  Seeding ETL control tables...")
    proc_codes = ["BUSENT_DLY", "CRSCOR_DLY", "ADDRMTCH_W"]
    src_codes = ["MAINFRAME", "BUREAU_FL", "ADDR_VEND"]

    for i in range(30):
        cyc_date = (date(2024, 10, 1) + timedelta(days=i)).isoformat()
        for j, proc_cd in enumerate(proc_codes):
            strt = datetime(2024, 10, 1 + i, 6, 0, 0)
            end = strt + timedelta(hours=random.randint(1, 4), minutes=random.randint(0, 59))
            cyc_id = 1000 + i * 3 + j

            cursor.execute("""
                INSERT INTO etl_cyc_ctl VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                cyc_date, proc_cd,
                strt.isoformat(), end.isoformat(),
                random.choice(["DAILY", "WEEKLY"]),
                random.choice(["COMPLETED", "COMPLETED", "COMPLETED", "FAILED"]),
                cyc_id,
            ))

            cursor.execute("""
                INSERT INTO etl_src_ctl VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cyc_date, proc_cd, src_codes[j],
                random.randint(100, 50000),
                random.randint(100, 50000),
                strt.isoformat(),
                end.isoformat(),
                random.choice(["SUCC", "SUCC", "SUCC", "FAIL"]),
                "" if random.random() > 0.1 else "RECORD_COUNT_MISMATCH",
                f"CHK{random.randint(100000, 999999)}",
                cyc_date,
                f"/data/inbound/{proc_cd.lower()}_{cyc_date}.dat",
                f"/data/inbound/{proc_cd.lower()}_{cyc_date}.ctl",
                "US",
                cyc_id,
            ))

    conn.commit()
    conn.close()
    print(f"  Source database created: {db_path}")
    print(f"  Total records: ~{num_businesses * 3 + 90}")


def create_target_db(db_path: Path):
    """Create empty target database with same schemas (for provisioning agent)."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    for table_name, ddl in SCHEMAS.items():
        cursor.execute(ddl)
    conn.commit()
    conn.close()
    print(f"  Target database created: {db_path}")


def setup_all():
    """Full database setup."""
    print("\n=== Database Setup ===\n")

    # Create logs directory
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    # Source DB with seed data
    if SOURCE_DB_PATH.exists():
        SOURCE_DB_PATH.unlink()
    seed_source_data(SOURCE_DB_PATH)

    # Empty target DB
    if TARGET_DB_PATH.exists():
        TARGET_DB_PATH.unlink()
    create_target_db(TARGET_DB_PATH)

    print("\n=== Setup Complete ===\n")


if __name__ == "__main__":
    setup_all()
