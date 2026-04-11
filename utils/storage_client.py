"""AWS S3 Storage Client — replaces local disk persistence with strict AWS object storage."""

import json
import boto3
from botocore.exceptions import ClientError

from config.settings import S3_REPORTS_BUCKET, S3_CSVS_BUCKET, S3_SCRIPTS_BUCKET
from utils.logger import get_logger

log = get_logger("storage")


class S3StorageClient:
    """Handles object persistence natively utilizing AWS Boto3 Core."""

    def __init__(self):
        # Strict AWS Connection — relies on ambient Enterprise IAM Roles or local ~/.aws/credentials
        # Option B constraints: No mocks, pure AWS SDK routing.
        self.s3 = boto3.client("s3")

    def upload_json(self, bucket: str, object_key: str, data: dict) -> bool:
        """Upload a Python dictionary as a JSON object to S3."""
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=json.dumps(data, indent=2, default=str),
                ContentType="application/json"
            )
            log.info(f"S3 Upload Success: s3://{bucket}/{object_key}")
            return True
        except ClientError as e:
            log.error(f"S3 JSON Upload Failed ({bucket}/{object_key}): {e}")
            return False

    def upload_text(self, bucket: str, object_key: str, text_data: str, content_type: str = "text/plain") -> bool:
        """Upload raw text (CSV, BTEQ, XFR) directly to S3."""
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=text_data.encode("utf-8"),
                ContentType=content_type
            )
            log.info(f"S3 Upload Success: s3://{bucket}/{object_key}")
            return True
        except ClientError as e:
            log.error(f"S3 Text Upload Failed ({bucket}/{object_key}): {e}")
            return False

    def download_json(self, bucket: str, object_key: str) -> dict | None:
        """Download and parse a JSON object from S3."""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=object_key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            # Check for 404 (NoSuchKey)
            if e.response["Error"]["Code"] == "NoSuchKey":
                log.info(f"S3 JSON Object Not Found: s3://{bucket}/{object_key}")
            else:
                log.error(f"S3 JSON Download Failed ({bucket}/{object_key}): {e}")
            return None


storage_client = S3StorageClient()
