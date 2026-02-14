import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ScreenshotStorage:
    """Service for uploading screenshots to MinIO S3-compatible storage."""

    _instance = None

    def __init__(self):
        # Parse endpoint URL
        endpoint = settings.minio_endpoint

        self.bucket = settings.minio_bucket

        # Configure boto3 client for MinIO
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            region_name='us-east-1'
        )

        self._ensure_bucket_exists()

    @classmethod
    def get_instance(cls) -> 'ScreenshotStorage':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = ScreenshotStorage()
        return cls._instance

    def _ensure_bucket_exists(self):
        """Create the bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('404', 'NoSuchBucket'):
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Created MinIO bucket: {self.bucket}")
                except ClientError as create_error:
                    logger.warning(f"Failed to create MinIO bucket: {create_error}")
            else:
                logger.warning(f"Failed to check MinIO bucket: {e}")

    def upload_screenshot(self, local_path: str, user_id: str, execution_id: str) -> tuple[str, int]:
        """
        Upload a screenshot to MinIO.

        Args:
            local_path: Local filesystem path to the screenshot file
            user_id: User ID for key organization
            execution_id: Execution ID for key naming

        Returns:
            Tuple of (MinIO key, file size in bytes)
        """
        key = f"{user_id}/{execution_id}_final.png"

        # Get file size
        file_size = os.path.getsize(local_path)

        try:
            self.client.upload_file(
                local_path,
                self.bucket,
                key,
                ExtraArgs={
                    'ContentType': 'image/png'
                }
            )
            logger.info(f"Uploaded screenshot to MinIO: {key} ({file_size} bytes)")
            return key, file_size
        except ClientError as e:
            logger.error(f"Failed to upload screenshot to MinIO: {e}")
            raise

    def delete_screenshot(self, key: str) -> bool:
        """Delete a screenshot from MinIO."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Deleted screenshot from MinIO: {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete screenshot from MinIO: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a screenshot exists in MinIO."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
