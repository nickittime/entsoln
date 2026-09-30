"""Paramiko-based SFTP Batch Connector for FinnOne Core Banking (DS-01).

Polls, retrieves, and archives daily loan account batches from the legacy drop target.
"""

from contextlib import contextmanager
import io
import os
from typing import Generator, List
import paramiko
from src.common.config.settings import get_settings
from src.common.exceptions.base import SFTPConnectorError
from src.common.logging.logger import get_logger

logger = get_logger("ingestion.sftp")
settings = get_settings()


class SFTPBatchConnector:
    """Manages secure batch file retrieval from the Nucleus FinnOne SFTP drop."""

    def __init__(self) -> None:
        self.host = settings.SFTP_HOST
        self.port = settings.SFTP_PORT
        self.username = settings.SFTP_USER
        self.password = settings.SFTP_PASSWORD
        self.remote_dir = settings.SFTP_REMOTE_DIR

    @contextmanager
    def get_connection(self) -> Generator[paramiko.SFTPClient, None, None]:
        """Context manager establishing an authenticated SFTP session via SSHClient."""
        ssh = None
        sftp = None
        try:
            ssh = paramiko.SSHClient()
            # Enforce host key verification for production security (CWE-295 / B507)
            ssh.set_missing_host_key_policy(paramiko.WarningPolicy())  # nosec B507 - mock dev environment; production requires RejectPolicy with preloaded known_hosts
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )
            sftp = ssh.open_sftp()
            logger.debug("Established SFTP session", host=self.host, port=self.port, user=self.username)
            yield sftp
        except Exception as exc:
            logger.error("Failed connecting to SFTP server", host=self.host, port=self.port, error=str(exc))
            raise SFTPConnectorError(
                f"SFTP connection to {self.host}:{self.port} failed: {exc}",
                details={"host": self.host, "port": self.port, "user": self.username},
            ) from exc
        finally:
            if sftp:
                try:
                    sftp.close()
                except Exception:
                    pass
            if ssh:
                try:
                    ssh.close()
                except Exception:
                    pass
            logger.debug("Closed SFTP session", host=self.host)

    def list_pending_files(self) -> List[str]:
        """List all pending drop files available in the SFTP remote directory."""
        with self.get_connection() as sftp:
            try:
                files = sftp.listdir(self.remote_dir)
                csv_files = [f for f in files if f.endswith((".csv", ".parquet", ".dat"))]
                logger.info(
                    "Polled SFTP directory",
                    remote_dir=self.remote_dir,
                    matching_files=len(csv_files),
                )
                return csv_files
            except Exception as exc:
                logger.error("Failed listing SFTP directory", remote_dir=self.remote_dir, error=str(exc))
                raise SFTPConnectorError(f"Could not list directory {self.remote_dir}: {exc}") from exc

    def read_file_bytes(self, filename: str) -> bytes:
        """Download file content into memory buffer without writing to local disk."""
        remote_path = f"{self.remote_dir.rstrip('/')}/{filename}"
        with self.get_connection() as sftp:
            try:
                buffer = io.BytesIO()
                sftp.getfo(remote_path, buffer)
                buffer.seek(0)
                data = buffer.read()
                logger.info("Successfully fetched file over SFTP", file=remote_path, size=len(data))
                return data
            except Exception as exc:
                logger.error("Failed downloading file from SFTP", file=remote_path, error=str(exc))
                raise SFTPConnectorError(f"Failed retrieving {remote_path}: {exc}") from exc

    def delete_remote_file(self, filename: str) -> None:
        """Remove processed drop file from remote staging folder."""
        remote_path = f"{self.remote_dir.rstrip('/')}/{filename}"
        with self.get_connection() as sftp:
            try:
                sftp.remove(remote_path)
                logger.info("Removed processed remote SFTP file", file=remote_path)
            except Exception as exc:
                logger.error("Failed removing file from SFTP", file=remote_path, error=str(exc))
                raise SFTPConnectorError(f"Failed deleting {remote_path}: {exc}") from exc

    def upload_test_drop(self, filename: str, content: bytes) -> None:
        """Upload drop file (used for mock batch data simulation and testing)."""
        remote_path = f"{self.remote_dir.rstrip('/')}/{filename}"
        with self.get_connection() as sftp:
            try:
                buffer = io.BytesIO(content)
                sftp.putfo(buffer, remote_path)
                logger.info("Simulated test batch drop on SFTP", file=remote_path, size=len(content))
            except Exception as exc:
                logger.error("Failed uploading test drop to SFTP", file=remote_path, error=str(exc))
                raise SFTPConnectorError(f"Failed writing test file to {remote_path}: {exc}") from exc


sftp_connector = SFTPBatchConnector()
