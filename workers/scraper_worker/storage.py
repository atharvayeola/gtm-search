"""
MinIO Storage Client

Handles storing raw job payloads to MinIO/S3 and computing content hashes.
"""

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class StorageClient:
    """Client for storing raw job payloads to MinIO/S3."""
    
    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        self._bucket = settings.s3_bucket
    
    def compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()
    
    def _generate_object_key(
        self,
        source_type: str,
        source_key: str,
        source_job_id: str,
        timestamp: datetime | None = None,
    ) -> str:
        """
        Generate object key for raw payload.
        
        Format: raw/{source_type}/{source_key}/{source_job_id}/{timestamp}.json
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        ts_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
        return f"raw/{source_type}/{source_key}/{source_job_id}/{ts_str}.json"
    
    def store_raw_payload(
        self,
        source_type: str,
        source_key: str,
        source_job_id: str,
        payload: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> tuple[str, str]:
        """
        Store raw job payload to MinIO.
        
        Args:
            source_type: 'greenhouse' or 'lever'
            source_key: Board token or site identifier
            source_job_id: Job ID from the source
            payload: Raw JSON payload
            timestamp: Fetch timestamp (defaults to now)
            
        Returns:
            Tuple of (object_key, content_hash)
        """
        # Serialize payload
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        content_hash = self.compute_hash(data)
        
        # Generate object key
        object_key = self._generate_object_key(
            source_type, source_key, source_job_id, timestamp
        )
        
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=io.BytesIO(data),
                ContentType="application/json",
                ContentLength=len(data),
            )
            logger.debug(
                "Stored raw payload",
                object_key=object_key,
                content_hash=content_hash[:16],
                size=len(data),
            )
        except ClientError as e:
            logger.error(
                "Failed to store payload",
                object_key=object_key,
                error=str(e),
            )
            raise
        
        return object_key, content_hash
    
    def get_payload(self, object_key: str) -> dict[str, Any]:
        """
        Retrieve raw payload from MinIO.
        
        Args:
            object_key: Object key in bucket
            
        Returns:
            Parsed JSON payload
        """
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            data = response["Body"].read()
            return json.loads(data)
        except ClientError as e:
            logger.error(
                "Failed to retrieve payload",
                object_key=object_key,
                error=str(e),
            )
            raise
    
    def object_exists(self, object_key: str) -> bool:
        """Check if an object exists in the bucket."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=object_key)
            return True
        except ClientError:
            return False


# Singleton instance
_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """Get or create the storage client singleton."""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
