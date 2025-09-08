"""Lambda-optimized caching strategies."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

import boto3


class LambdaCacheManager:
    """Multi-tier caching optimized for AWS Lambda."""

    def __init__(self, config):
        self.config = config
        self.s3_client = boto3.client("s3") if config.s3_cache_bucket else None

    def get(self, key: str) -> Optional[Any]:
        """Multi-tier cache lookup: Memory → /tmp → S3 → ElastiCache."""

        # Tier 1: In-memory cache (fastest, but lost on cold start)
        if hasattr(self, "_memory_cache"):
            if key in self._memory_cache:
                return self._memory_cache[key]

        # Tier 2: Lambda /tmp cache (survives within execution)
        local_data = self._get_from_local(key)
        if local_data:
            return local_data

        # Tier 3: S3 cache (survives across invocations)
        if self.config.cache_backend == "s3":
            s3_data = self._get_from_s3(key)
            if s3_data:
                # Cache locally for this execution
                self._set_to_local(key, s3_data)
                return s3_data

        # Tier 4: ElastiCache (fastest cross-invocation)
        if self.config.cache_backend == "elasticache":
            return self._get_from_elasticache(key)

        return None

    def set(self, key: str, data: Any) -> bool:
        """Multi-tier cache storage."""

        # Always cache locally for this execution
        self._set_to_local(key, data)
        self._set_to_memory(key, data)

        # Persist based on backend strategy
        if self.config.cache_backend == "s3":
            return self._set_to_s3(key, data)
        elif self.config.cache_backend == "elasticache":
            return self._set_to_elasticache(key, data)

        return True

    def _get_from_local(self, key: str) -> Optional[Any]:
        """Get from Lambda /tmp directory."""
        import pickle
        from pathlib import Path

        cache_file = Path(self.config.cache_dir) / f"{key}.pkl"

        if cache_file.exists():
            # Check TTL
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=24):
                try:
                    with open(cache_file, "rb") as f:
                        return pickle.load(f)
                except Exception:
                    cache_file.unlink(missing_ok=True)

        return None

    def _set_to_local(self, key: str, data: Any) -> bool:
        """Set to Lambda /tmp directory."""
        import pickle
        from pathlib import Path

        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(exist_ok=True)

        cache_file = cache_dir / f"{key}.pkl"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)
            return True
        except Exception:
            return False

    def _get_from_s3(self, key: str) -> Optional[Any]:
        """Get from S3 cache bucket."""
        if not self.s3_client or not self.config.s3_cache_bucket:
            return None

        try:
            response = self.s3_client.get_object(
                Bucket=self.config.s3_cache_bucket, Key=f"cache/{key}.json"
            )

            # Check TTL metadata
            last_modified = response["LastModified"].replace(tzinfo=None)
            if datetime.utcnow() - last_modified > timedelta(hours=24):
                return None

            data = json.loads(response["Body"].read())
            return data

        except Exception:
            return None

    def _set_to_s3(self, key: str, data: Any) -> bool:
        """Set to S3 cache bucket."""
        if not self.s3_client or not self.config.s3_cache_bucket:
            return False

        try:
            self.s3_client.put_object(
                Bucket=self.config.s3_cache_bucket,
                Key=f"cache/{key}.json",
                Body=json.dumps(data, default=str),
                Metadata={
                    "cached_at": datetime.utcnow().isoformat(),
                    "ttl_hours": "24",
                },
            )
            return True
        except Exception:
            return False

    def _set_to_memory(self, key: str, data: Any):
        """Set to in-memory cache."""
        if not hasattr(self, "_memory_cache"):
            self._memory_cache = {}
        self._memory_cache[key] = data
