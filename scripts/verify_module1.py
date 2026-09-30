"""End-to-End Verification Script for Module 1.

Runs live validation against PostgreSQL, ClickHouse, Redis, S3, and SFTP.
Executed inside the container network to ensure zero networking ambiguity.
"""

import asyncio
import sys
import uuid

from src.common.config.settings import get_settings
from src.common.database.clickhouse import clickhouse_manager
from src.common.database.postgres import check_postgres_health, get_db_context
from src.common.database.redis_client import acquire_distributed_lock, check_redis_health, get_redis_client
from src.common.logging.logger import get_logger, setup_logging
from src.common.storage.s3_client import s3_manager
from src.ingestion.connectors.sftp_connector import sftp_connector
from sqlalchemy import text

setup_logging()
logger = get_logger("verification.module1")
settings = get_settings()


async def run_verification() -> bool:
    print("\n" + "=" * 80)
    print(" ZERMP MODULE 1: COMPREHENSIVE DATA LAYER & INGESTION VERIFICATION")
    print("=" * 80)
    all_passed = True

    # 1. PostgreSQL Check & Transaction Validation
    print("\n[1/5] Testing PostgreSQL Connection & Async Transaction...")
    try:
        pg_healthy = await check_postgres_health()
        assert pg_healthy, "PostgreSQL ping query did not return 1"
        async with get_db_context() as session:
            await session.execute(text("CREATE TABLE IF NOT EXISTS _test_module1 (id INT PRIMARY KEY);"))
            await session.execute(text("INSERT INTO _test_module1 (id) VALUES (42) ON CONFLICT DO NOTHING;"))
            res = await session.execute(text("SELECT id FROM _test_module1 WHERE id = 42;"))
            val = res.scalar()
            assert val == 42, "Value inserted into PostgreSQL does not match"
            await session.execute(text("DROP TABLE _test_module1;"))
        print("  [✓] PostgreSQL: Connected, DDL executed, transaction committed, and cleaned up.")
    except Exception as exc:
        print(f"  [✗] PostgreSQL Failed: {exc}")
        all_passed = False

    # 2. ClickHouse Check & Bulk Analytics Insert
    print("\n[2/5] Testing ClickHouse OLAP Engine & Batch Insert...")
    try:
        ch_ping = clickhouse_manager.ping()
        assert ch_ping, "ClickHouse ping failed"
        clickhouse_manager.execute_command(
            "CREATE TABLE IF NOT EXISTS default._test_batch (account_id String, dpd UInt32) ENGINE = Memory"
        )
        sample_rows = [[f"ACC_{i}", i * 10] for i in range(5)]
        clickhouse_manager.insert_batch("default._test_batch", sample_rows, ["account_id", "dpd"])
        queried = clickhouse_manager.query_rows("SELECT count() as cnt FROM default._test_batch")
        assert queried[0]["cnt"] == 5, "ClickHouse record count mismatch"
        clickhouse_manager.execute_command("DROP TABLE default._test_batch")
        print("  [✓] ClickHouse: Connected, batch memory table created, 5 records inserted and verified.")
    except Exception as exc:
        print(f"  [✗] ClickHouse Failed: {exc}")
        all_passed = False

    # 3. Redis Distributed Lock & Cache
    print("\n[3/5] Testing Redis Cache & Distributed Mutex Lock...")
    try:
        redis_ok = await check_redis_health()
        assert redis_ok, "Redis ping failed"
        client = get_redis_client()
        await client.set("test:module1:key", "enterprise_ready", ex=30)
        retrieved = await client.get("test:module1:key")
        assert retrieved == "enterprise_ready", "Redis cache get mismatch"
        async with acquire_distributed_lock("etl_finnone_batch", timeout_seconds=5) as locked:
            assert locked, "Could not acquire distributed lock"
        await client.delete("test:module1:key")
        await client.aclose()
        print("  [✓] Redis: Ping verified, key-value stored with TTL, distributed mutex acquired & released.")
    except Exception as exc:
        print(f"  [✗] Redis Failed: {exc}")
        all_passed = False

    # 4. AWS S3 / LocalStack Storage & WORM Bucket Validation
    print("\n[4/5] Testing S3 / LocalStack WORM Buckets & Object Operations...")
    try:
        s3_manager.ensure_buckets_exist()
        test_key = f"audit_reports/test_report_{uuid.uuid4().hex[:8]}.pdf"
        test_content = b"%PDF-1.4 Mock Regulatory RBI NBS-7 Content"
        s3_uri = s3_manager.upload_bytes(
            bucket=settings.S3_BUCKET_REPORTS,
            key=test_key,
            data=test_content,
            content_type="application/pdf",
            metadata={"institution": "Vridhi-NBFC", "regulatory_return": "NBS-7"},
        )
        downloaded = s3_manager.download_bytes(settings.S3_BUCKET_REPORTS, test_key)
        assert downloaded == test_content, "Downloaded S3 payload mismatch"
        print(f"  [✓] S3 / LocalStack: Buckets auto-initialized, test object uploaded to {s3_uri} and verified.")
    except Exception as exc:
        print(f"  [✗] S3 Failed: {exc}")
        all_passed = False

    # 5. SFTP FinnOne Core Banking Batch Poller (DS-01)
    print("\n[5/5] Testing SFTP Batch Connector (FinnOne Core Drops)...")
    try:
        filename = f"finnone_daily_extract_{uuid.uuid4().hex[:6]}.csv"
        drop_payload = b"account_id,cust_name,sanctioned_amount,dpd\nACC1001,Rajesh Sharma,1500000.00,12\n"
        sftp_connector.upload_test_drop(filename, drop_payload)
        pending = sftp_connector.list_pending_files()
        assert filename in pending, f"{filename} not found in SFTP listing"
        fetched_bytes = sftp_connector.read_file_bytes(filename)
        assert fetched_bytes == drop_payload, "SFTP downloaded payload mismatch"
        sftp_connector.delete_remote_file(filename)
        print("  [✓] SFTP Connector: Simulated drop uploaded, listed via remote directory, read, and cleaned.")
    except Exception as exc:
        print(f"  [✗] SFTP Connector Failed: {exc}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print(" RESULT: ALL 5 DATA ACCESS LAYERS & INGESTION CONNECTORS OPERATIONAL [PASS]")
        print("=" * 80 + "\n")
        return True
    else:
        print(" RESULT: ONE OR MORE CONNECTORS FAILED VERIFICATION [FAIL]")
        print("=" * 80 + "\n")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)
