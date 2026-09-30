"""ClickHouse High-Throughput Columnar OLAP Client.

Handles portfolio-scale batch inserts and aggregation for risk analytics.
"""

from typing import Any, Dict, List, Optional
import clickhouse_connect
from clickhouse_connect.driver.client import Client
from src.common.config.settings import get_settings
from src.common.exceptions.base import ClickHouseExecutionError
from src.common.logging.logger import get_logger

logger = get_logger("database.clickhouse")
settings = get_settings()


class ClickHouseClient:
    """Thread-safe ClickHouse connection manager and batch operations wrapper."""

    def __init__(self) -> None:
        self._client: Optional[Client] = None

    def get_client(self) -> Client:
        """Establish or return an active native ClickHouse client instance."""
        if self._client is None:
            try:
                self._client = clickhouse_connect.get_client(
                    host=settings.CLICKHOUSE_HOST,
                    port=settings.CLICKHOUSE_PORT,
                    username=settings.CLICKHOUSE_USER,
                    password=settings.CLICKHOUSE_PASSWORD,
                    database=settings.CLICKHOUSE_DB,
                    connect_timeout=10,
                    send_receive_timeout=30,
                )
                logger.info(
                    "Connected to ClickHouse",
                    database=settings.CLICKHOUSE_DB,
                    host=settings.CLICKHOUSE_HOST,
                )
            except Exception as exc:
                logger.error("ClickHouse connection initialization failed", error=str(exc))
                raise ClickHouseExecutionError(
                    f"Could not connect to ClickHouse: {exc}",
                    details={"host": settings.CLICKHOUSE_HOST, "port": settings.CLICKHOUSE_PORT},
                ) from exc
        return self._client

    def ping(self) -> bool:
        """Verify client connection to ClickHouse server."""
        try:
            client = self.get_client()
            res = client.command("SELECT 1")
            return res == 1
        except Exception as exc:
            logger.error("ClickHouse ping check failed", error=str(exc))
            return False

    def execute_command(self, query: str) -> Any:
        """Execute a DDL or non-returning SQL command."""
        try:
            client = self.get_client()
            return client.command(query)
        except Exception as exc:
            logger.error("Failed executing ClickHouse command", query=query, error=str(exc))
            raise ClickHouseExecutionError(
                f"Failed executing ClickHouse command: {exc}",
                details={"query": query},
            ) from exc

    def insert_batch(
        self, table: str, data: List[List[Any]], column_names: List[str]
    ) -> None:
        """Perform high-performance streaming batch insertion."""
        if not data:
            return
        try:
            client = self.get_client()
            client.insert(table=table, data=data, column_names=column_names)
            logger.debug(
                "Inserted batch into ClickHouse",
                table=table,
                record_count=len(data),
            )
        except Exception as exc:
            logger.error(
                "ClickHouse batch insert failed",
                table=table,
                row_count=len(data),
                error=str(exc),
            )
            raise ClickHouseExecutionError(
                f"ClickHouse batch insert failed on table {table}: {exc}",
                details={"table": table, "record_count": len(data)},
            ) from exc

    def query_rows(self, query: str) -> List[Dict[str, Any]]:
        """Query ClickHouse and return results as a list of key-value dictionaries."""
        try:
            client = self.get_client()
            result = client.query(query)
            columns = result.column_names
            return [dict(zip(columns, row)) for row in result.result_rows]
        except Exception as exc:
            logger.error("ClickHouse select query failed", query=query, error=str(exc))
            raise ClickHouseExecutionError(
                f"ClickHouse query failed: {exc}",
                details={"query": query},
            ) from exc


clickhouse_manager = ClickHouseClient()
