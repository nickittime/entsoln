"""AWS S3 / LocalStack Object Storage Client.

Manages WORM-compliant storage for regulatory report archives and batch files.
"""

from typing import Any, Dict, List, Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from src.common.config.settings import get_settings
from src.common.exceptions.base import StorageError
from src.common.logging.logger import get_logger

logger = get_logger("storage.s3")
settings = get_settings()


class S3StorageManager:
    """Encapsulates S3 operations, bucket creation, and regulatory object lifecycle."""

    def __init__(self) -> None:
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.region = settings.AWS_DEFAULT_REGION
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=self.region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_buckets_exist(self) -> None:
        """Idempotently create required platform buckets on startup."""
        buckets = [settings.S3_BUCKET_REPORTS, settings.S3_BUCKET_INGEST]
        for bucket in buckets:
            try:
                self.s3_client.head_bucket(Bucket=bucket)
            except ClientError as err:
                error_code = err.response.get("Error", {}).get("Code")
                if error_code in ("404", "NoSuchBucket"):
                    logger.info("Creating missing S3 bucket", bucket=bucket)
                    kwargs: Dict[str, Any] = {"Bucket": bucket}
                    if self.region != "us-east-1":
                        kwargs["CreateBucketConfiguration"] = {
                            "LocationConstraint": self.region
                        }
                    self.s3_client.create_bucket(**kwargs)
                else:
                    logger.error("Failed inspecting S3 bucket", bucket=bucket, error=str(err))
                    raise StorageError(f"Could not verify S3 bucket {bucket}: {err}") from err

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload raw byte buffer to S3 with content metadata."""
        try:
            extra_args: Dict[str, Any] = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = metadata

            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                **extra_args,
            )
            logger.info("Uploaded object to S3", bucket=bucket, key=key, size=len(data))
            return f"s3://{bucket}/{key}"
        except Exception as exc:
            logger.error("Failed uploading object to S3", bucket=bucket, key=key, error=str(exc))
            raise StorageError(f"Failed uploading to {bucket}/{key}: {exc}") from exc

    def download_bytes(self, bucket: str, key: str) -> bytes:
        """Download object payload as bytes from S3."""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            logger.error("Failed downloading object from S3", bucket=bucket, key=key, error=str(exc))
            raise StorageError(f"Failed downloading from {bucket}/{key}: {exc}") from exc

    def list_objects(self, bucket: str, prefix: str = "") -> List[str]:
        """List object keys under a given bucket prefix."""
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            keys = []
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        except Exception as exc:
            logger.error("Failed listing objects from S3", bucket=bucket, prefix=prefix, error=str(exc))
            raise StorageError(f"Failed listing {bucket}/{prefix}: {exc}") from exc

    def check_health(self) -> bool:
        """Verify S3 service responsiveness."""
        try:
            self.s3_client.list_buckets()
            return True
        except Exception as exc:
            logger.error("S3 health check failed", error=str(exc))
            return False


s3_manager = S3StorageManager()
