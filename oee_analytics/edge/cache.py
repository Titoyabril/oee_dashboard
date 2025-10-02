"""
Edge Cache Implementation
Local caching with Redis and RocksDB for store-and-forward reliability
Supports sub-250ms latency requirements and offline resilience
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import struct
import pickle

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import rocksdb
    ROCKSDB_AVAILABLE = True
except ImportError:
    ROCKSDB_AVAILABLE = False

from prometheus_client import Counter, Histogram, Gauge


# Prometheus metrics
CACHE_HITS = Counter('edge_cache_hits_total', 'Cache hit count', ['cache_type', 'operation'])
CACHE_MISSES = Counter('edge_cache_misses_total', 'Cache miss count', ['cache_type', 'operation'])
CACHE_OPERATIONS = Histogram('edge_cache_operation_seconds', 'Cache operation time', ['cache_type', 'operation'])
CACHE_SIZE = Gauge('edge_cache_size_bytes', 'Cache size in bytes', ['cache_type'])
QUEUE_SIZE = Gauge('edge_queue_size_total', 'Queue size for store-and-forward', ['cache_type'])


@dataclass
class CacheConfig:
    """Configuration for edge cache"""
    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_enabled: bool = True

    # RocksDB configuration
    rocksdb_path: str = "./data/edge_cache"
    rocksdb_enabled: bool = True

    # Cache settings
    default_ttl: int = 3600  # 1 hour
    max_memory_usage: int = 100 * 1024 * 1024  # 100MB

    # Store-and-forward settings
    max_queue_size: int = 10000
    batch_size: int = 100
    flush_interval: float = 1.0  # seconds


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    timestamp: float
    ttl: Optional[int] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl is None:
            return False
        return time.time() > (self.timestamp + self.ttl)

    def to_bytes(self) -> bytes:
        """Serialize entry to bytes"""
        return pickle.dumps(asdict(self))

    @classmethod
    def from_bytes(cls, data: bytes) -> 'CacheEntry':
        """Deserialize entry from bytes"""
        entry_dict = pickle.loads(data)
        return cls(**entry_dict)


class BaseCacheBackend(ABC):
    """Abstract base class for cache backends"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        """Set value in cache"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass

    @abstractmethod
    async def flush(self) -> bool:
        """Flush all cache entries"""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        pass


class RedisBackend(BaseCacheBackend):
    """Redis cache backend for high-performance caching"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self.client: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            self.logger.error("Redis not available - install redis package")
            return False

        try:
            self.client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False  # We handle bytes
            )

            # Test connection
            await self.client.ping()
            self._connected = True
            self.logger.info(f"Connected to Redis at {self.config.redis_host}:{self.config.redis_port}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            self._connected = False

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get value from Redis cache"""
        if not self._connected:
            return None

        with CACHE_OPERATIONS.labels(cache_type='redis', operation='get').time():
            try:
                data = await self.client.get(f"edge:{key}")
                if data:
                    entry = CacheEntry.from_bytes(data)
                    if not entry.is_expired():
                        CACHE_HITS.labels(cache_type='redis', operation='get').inc()
                        return entry
                    else:
                        # Remove expired entry
                        await self.delete(key)

                CACHE_MISSES.labels(cache_type='redis', operation='get').inc()
                return None

            except Exception as e:
                self.logger.error(f"Redis get error for key {key}: {e}")
                return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        """Set value in Redis cache"""
        if not self._connected:
            return False

        with CACHE_OPERATIONS.labels(cache_type='redis', operation='set').time():
            try:
                entry = CacheEntry(
                    key=key,
                    value=value,
                    timestamp=time.time(),
                    ttl=ttl or self.config.default_ttl,
                    tags=tags or []
                )

                data = entry.to_bytes()
                redis_key = f"edge:{key}"

                if ttl:
                    await self.client.setex(redis_key, ttl, data)
                else:
                    await self.client.set(redis_key, data)

                # Update size metric
                size = await self.client.memory_usage(redis_key)
                if size:
                    CACHE_SIZE.labels(cache_type='redis').set(size)

                return True

            except Exception as e:
                self.logger.error(f"Redis set error for key {key}: {e}")
                return False

    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache"""
        if not self._connected:
            return False

        try:
            result = await self.client.delete(f"edge:{key}")
            return result > 0
        except Exception as e:
            self.logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self._connected:
            return False

        try:
            result = await self.client.exists(f"edge:{key}")
            return result > 0
        except Exception as e:
            self.logger.error(f"Redis exists error for key {key}: {e}")
            return False

    async def flush(self) -> bool:
        """Flush Redis cache"""
        if not self._connected:
            return False

        try:
            await self.client.flushdb()
            return True
        except Exception as e:
            self.logger.error(f"Redis flush error: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        if not self._connected:
            return {}

        try:
            info = await self.client.info('memory')
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'connected_clients': info.get('connected_clients', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0)
            }
        except Exception as e:
            self.logger.error(f"Redis stats error: {e}")
            return {}


class RocksDBBackend(BaseCacheBackend):
    """RocksDB backend for persistent store-and-forward cache"""

    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self.db: Optional[rocksdb.DB] = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to RocksDB"""
        if not ROCKSDB_AVAILABLE:
            self.logger.error("RocksDB not available - install python-rocksdb package")
            return False

        try:
            # Create directory if it doesn't exist
            db_path = Path(self.config.rocksdb_path)
            db_path.mkdir(parents=True, exist_ok=True)

            # Configure RocksDB options
            opts = rocksdb.Options()
            opts.create_if_missing = True
            opts.max_open_files = 300000
            opts.write_buffer_size = 67108864  # 64MB
            opts.max_write_buffer_number = 3
            opts.target_file_size_base = 67108864  # 64MB

            # Configure block cache for performance
            opts.table_factory = rocksdb.BlockBasedTableFactory(
                filter_policy=rocksdb.BloomFilterPolicy(10),
                block_cache=rocksdb.LRUCache(2 * (1024 ** 3)),  # 2GB
                block_cache_compressed=rocksdb.LRUCache(500 * (1024 ** 2))  # 500MB
            )

            self.db = rocksdb.DB(str(db_path), opts)
            self._connected = True
            self.logger.info(f"Connected to RocksDB at {db_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to RocksDB: {e}")
            return False

    async def disconnect(self):
        """Disconnect from RocksDB"""
        if self.db:
            # RocksDB auto-closes
            self._connected = False

    def _make_key(self, key: str) -> bytes:
        """Create RocksDB key with prefix"""
        return f"edge:{key}".encode('utf-8')

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get value from RocksDB cache"""
        if not self._connected:
            return None

        with CACHE_OPERATIONS.labels(cache_type='rocksdb', operation='get').time():
            try:
                data = self.db.get(self._make_key(key))
                if data:
                    entry = CacheEntry.from_bytes(data)
                    if not entry.is_expired():
                        CACHE_HITS.labels(cache_type='rocksdb', operation='get').inc()
                        return entry
                    else:
                        # Remove expired entry
                        await self.delete(key)

                CACHE_MISSES.labels(cache_type='rocksdb', operation='get').inc()
                return None

            except Exception as e:
                self.logger.error(f"RocksDB get error for key {key}: {e}")
                return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        """Set value in RocksDB cache"""
        if not self._connected:
            return False

        with CACHE_OPERATIONS.labels(cache_type='rocksdb', operation='set').time():
            try:
                entry = CacheEntry(
                    key=key,
                    value=value,
                    timestamp=time.time(),
                    ttl=ttl,
                    tags=tags or []
                )

                data = entry.to_bytes()
                self.db.put(self._make_key(key), data)

                # Update size metric (approximate)
                CACHE_SIZE.labels(cache_type='rocksdb').inc(len(data))

                return True

            except Exception as e:
                self.logger.error(f"RocksDB set error for key {key}: {e}")
                return False

    async def delete(self, key: str) -> bool:
        """Delete value from RocksDB cache"""
        if not self._connected:
            return False

        try:
            self.db.delete(self._make_key(key))
            return True
        except Exception as e:
            self.logger.error(f"RocksDB delete error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in RocksDB"""
        if not self._connected:
            return False

        try:
            data = self.db.get(self._make_key(key))
            return data is not None
        except Exception as e:
            self.logger.error(f"RocksDB exists error for key {key}: {e}")
            return False

    async def flush(self) -> bool:
        """Flush RocksDB cache (delete all keys)"""
        if not self._connected:
            return False

        try:
            # Delete all keys with edge: prefix
            it = self.db.iterkeys()
            it.seek(b"edge:")

            keys_to_delete = []
            for key in it:
                if key.startswith(b"edge:"):
                    keys_to_delete.append(key)
                else:
                    break

            for key in keys_to_delete:
                self.db.delete(key)

            return True
        except Exception as e:
            self.logger.error(f"RocksDB flush error: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get RocksDB statistics"""
        if not self._connected:
            return {}

        try:
            # Get approximate sizes
            opts = rocksdb.Options()
            size_range = self.db.get_property(b"rocksdb.estimate-live-data-size")
            num_keys = self.db.get_property(b"rocksdb.estimate-num-keys")

            return {
                'estimated_size_bytes': int(size_range.decode()) if size_range else 0,
                'estimated_num_keys': int(num_keys.decode()) if num_keys else 0,
                'db_path': self.config.rocksdb_path
            }
        except Exception as e:
            self.logger.error(f"RocksDB stats error: {e}")
            return {}


class EdgeCache:
    """Multi-tier edge cache with Redis (L1) and RocksDB (L2)"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize backends
        self.redis_backend: Optional[RedisBackend] = None
        self.rocksdb_backend: Optional[RocksDBBackend] = None

        if config.redis_enabled:
            self.redis_backend = RedisBackend(config)

        if config.rocksdb_enabled:
            self.rocksdb_backend = RocksDBBackend(config)

        # Store-and-forward queue
        self._pending_queue: List[Dict[str, Any]] = []
        self._queue_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Connect to all available backends"""
        success = True

        if self.redis_backend:
            if not await self.redis_backend.connect():
                self.logger.warning("Redis backend failed to connect")
                success = False

        if self.rocksdb_backend:
            if not await self.rocksdb_backend.connect():
                self.logger.warning("RocksDB backend failed to connect")
                success = False

        # Start store-and-forward flush task
        if success:
            self._flush_task = asyncio.create_task(self._flush_pending_data())

        return success

    async def disconnect(self):
        """Disconnect from all backends"""
        if self._flush_task:
            self._flush_task.cancel()

        if self.redis_backend:
            await self.redis_backend.disconnect()

        if self.rocksdb_backend:
            await self.rocksdb_backend.disconnect()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (L1 then L2)"""
        # Try Redis first (L1)
        if self.redis_backend:
            entry = await self.redis_backend.get(key)
            if entry:
                return entry.value

        # Try RocksDB (L2)
        if self.rocksdb_backend:
            entry = await self.rocksdb_backend.get(key)
            if entry:
                # Promote to L1 cache
                if self.redis_backend:
                    await self.redis_backend.set(key, entry.value, ttl=300)  # 5min in L1
                return entry.value

        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: List[str] = None) -> bool:
        """Set value in cache (both L1 and L2)"""
        success = True

        # Set in Redis (L1) - shorter TTL
        if self.redis_backend:
            l1_ttl = min(ttl or 300, 300)  # Max 5 minutes in L1
            if not await self.redis_backend.set(key, value, l1_ttl, tags):
                success = False

        # Set in RocksDB (L2) - longer TTL
        if self.rocksdb_backend:
            if not await self.rocksdb_backend.set(key, value, ttl, tags):
                success = False

        return success

    async def delete(self, key: str) -> bool:
        """Delete value from both cache layers"""
        success = True

        if self.redis_backend:
            if not await self.redis_backend.delete(key):
                success = False

        if self.rocksdb_backend:
            if not await self.rocksdb_backend.delete(key):
                success = False

        return success

    async def queue_for_forward(self, data: Dict[str, Any]) -> bool:
        """Queue data for store-and-forward"""
        async with self._queue_lock:
            if len(self._pending_queue) >= self.config.max_queue_size:
                # Remove oldest entry
                self._pending_queue.pop(0)
                self.logger.warning("Queue full, dropped oldest entry")

            # Add timestamp
            data['queued_at'] = time.time()
            self._pending_queue.append(data)

            QUEUE_SIZE.labels(cache_type='store_and_forward').set(len(self._pending_queue))

            return True

    async def get_pending_data(self, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get pending data for processing"""
        async with self._queue_lock:
            if max_items:
                items = self._pending_queue[:max_items]
                self._pending_queue = self._pending_queue[max_items:]
            else:
                items = self._pending_queue.copy()
                self._pending_queue.clear()

            QUEUE_SIZE.labels(cache_type='store_and_forward').set(len(self._pending_queue))
            return items

    async def _flush_pending_data(self):
        """Background task to flush pending data"""
        while True:
            try:
                await asyncio.sleep(self.config.flush_interval)

                # Get batch of pending data
                pending = await self.get_pending_data(self.config.batch_size)

                if pending:
                    self.logger.debug(f"Processing {len(pending)} pending items")

                    # Store in persistent cache
                    for item in pending:
                        cache_key = f"pending:{item.get('timestamp', time.time())}"
                        await self.set(cache_key, item, ttl=86400)  # 24 hours

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in flush task: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = {
            'queue_size': len(self._pending_queue),
            'backends': {}
        }

        if self.redis_backend:
            stats['backends']['redis'] = await self.redis_backend.get_stats()

        if self.rocksdb_backend:
            stats['backends']['rocksdb'] = await self.rocksdb_backend.get_stats()

        return stats

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all cache backends"""
        health = {}

        if self.redis_backend:
            try:
                await self.redis_backend.set("health_check", "ok", ttl=60)
                result = await self.redis_backend.get("health_check")
                health['redis'] = result is not None
            except:
                health['redis'] = False

        if self.rocksdb_backend:
            try:
                await self.rocksdb_backend.set("health_check", "ok", ttl=60)
                result = await self.rocksdb_backend.get("health_check")
                health['rocksdb'] = result is not None
            except:
                health['rocksdb'] = False

        return health


# Example usage
async def main():
    """Example usage of EdgeCache"""
    config = CacheConfig(
        redis_host="localhost",
        redis_enabled=True,
        rocksdb_path="./cache_data",
        rocksdb_enabled=True
    )

    cache = EdgeCache(config)

    try:
        # Connect
        await cache.connect()

        # Store some data
        await cache.set("temperature:line1", 75.5, ttl=300, tags=["sensor", "temperature"])
        await cache.set("pressure:line1", 2.1, ttl=300, tags=["sensor", "pressure"])

        # Retrieve data
        temp = await cache.get("temperature:line1")
        print(f"Temperature: {temp}")

        # Queue data for store-and-forward
        await cache.queue_for_forward({
            "metric": "production_count",
            "value": 100,
            "timestamp": time.time()
        })

        # Get stats
        stats = await cache.get_stats()
        print(f"Cache stats: {stats}")

        # Health check
        health = await cache.health_check()
        print(f"Health: {health}")

    finally:
        await cache.disconnect()


if __name__ == "__main__":
    asyncio.run(main())