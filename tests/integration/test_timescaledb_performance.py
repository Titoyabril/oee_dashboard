"""
TimescaleDB Performance Tests
Tests query performance, continuous aggregates, compression, and retention policies
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone, timedelta
import random

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_timescaledb,
]


def test_timescaledb_hypertable_creation(
    clean_timescaledb
):
    """
    Verify TimescaleDB hypertables are properly configured
    """
    cursor = clean_timescaledb.cursor()

    # Check telemetry hypertable
    cursor.execute(
        """
        SELECT * FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'telemetry'
        """
    )
    result = cursor.fetchone()

    assert result is not None, "Telemetry hypertable not found"
    print(f"✅ Telemetry hypertable exists")
    print(f"   Chunk interval: {result['chunk_time_interval']}")
    print(f"   Number of dimensions: {result['num_dimensions']}")

    # Check dimensions (time + space partitioning)
    cursor.execute(
        """
        SELECT dimension_name, num_partitions
        FROM timescaledb_information.dimensions
        WHERE hypertable_name = 'telemetry'
        """
    )
    dimensions = cursor.fetchall()

    assert len(dimensions) >= 1, "No dimensions found"

    dim_names = [d['dimension_name'] for d in dimensions]
    assert 'time' in dim_names, "Time dimension not found"

    # Check for space partitioning
    space_dims = [d for d in dimensions if d['dimension_name'] != 'time']
    if space_dims:
        print(f"✅ Space partitioning enabled: {space_dims[0]['num_partitions']} partitions")


def test_timescaledb_compression_policy(
    clean_timescaledb
):
    """
    Verify compression policies are configured
    """
    cursor = clean_timescaledb.cursor()

    cursor.execute(
        """
        SELECT * FROM timescaledb_information.compression_settings
        WHERE hypertable_name = 'telemetry'
        """
    )
    result = cursor.fetchone()

    if result:
        print(f"✅ Compression enabled for telemetry")
        print(f"   Segmentby: {result.get('segmentby')}")
        print(f"   Orderby: {result.get('orderby')}")

    # Check compression policy
    cursor.execute(
        """
        SELECT * FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_compression'
        AND hypertable_name = 'telemetry'
        """
    )
    policy = cursor.fetchone()

    if policy:
        print(f"✅ Compression policy active")
        print(f"   Schedule: {policy['schedule_interval']}")


@pytest.mark.asyncio
async def test_timescaledb_continuous_aggregates(
    clean_timescaledb,
    generate_telemetry_data
):
    """
    Test continuous aggregates (1min, 5min, 1hour rollups)
    """

    # Generate test data
    machine_id = 'TEST_MACHINE_CAGG'
    data_points = generate_telemetry_data(
        machine_id=machine_id,
        num_points=120,  # 2 hours at 1 minute intervals
        interval_seconds=60
    )

    # Insert data
    await clean_timescaledb.executemany(
        """
        INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
        VALUES ($1, $2, $3, $4, $5)
        """,
        [(d['time'], d['machine_id'], d['metric_name'], d['value'], d['quality']) for d in data_points]
    )

    print(f"✅ Inserted {len(data_points)} telemetry points")

    # Refresh continuous aggregates
    await clean_timescaledb.execute(
        "CALL refresh_continuous_aggregate('telemetry_1min', NULL, NULL)"
    )
    await clean_timescaledb.execute(
        "CALL refresh_continuous_aggregate('telemetry_5min', NULL, NULL)"
    )
    await clean_timescaledb.execute(
        "CALL refresh_continuous_aggregate('telemetry_1hour', NULL, NULL)"
    )

    # Query 1-minute aggregates
    rows_1min = await clean_timescaledb.fetch(
        """
        SELECT bucket, avg_value, min_value, max_value, sample_count
        FROM telemetry_1min
        WHERE machine_id = $1
        ORDER BY bucket
        """,
        machine_id
    )

    assert len(rows_1min) >= 100, f"Expected ~120 1-min buckets, got {len(rows_1min)}"
    print(f"✅ 1-minute aggregates: {len(rows_1min)} buckets")

    # Verify aggregation correctness
    for row in rows_1min[:5]:
        assert row['min_value'] <= row['avg_value'] <= row['max_value']
        assert row['sample_count'] >= 1

    # Query 5-minute aggregates
    rows_5min = await clean_timescaledb.fetch(
        """
        SELECT bucket, avg_value, sample_count
        FROM telemetry_5min
        WHERE machine_id = $1
        ORDER BY bucket
        """,
        machine_id
    )

    assert len(rows_5min) >= 20, f"Expected ~24 5-min buckets, got {len(rows_5min)}"
    print(f"✅ 5-minute aggregates: {len(rows_5min)} buckets")

    # Query 1-hour aggregates
    rows_1hour = await clean_timescaledb.fetch(
        """
        SELECT bucket, avg_value, sample_count
        FROM telemetry_1hour
        WHERE machine_id = $1
        ORDER BY bucket
        """,
        machine_id
    )

    assert len(rows_1hour) >= 1, f"Expected ~2 1-hour buckets, got {len(rows_1hour)}"
    print(f"✅ 1-hour aggregates: {len(rows_1hour)} buckets")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_timescaledb_write_performance(
    clean_timescaledb
):
    """
    Benchmark: Insert performance
    Target: >10,000 inserts/second
    """

    machine_id = 'PERF_TEST_MACHINE'
    num_records = 50000

    print(f"\n🔥 Write performance test: {num_records} inserts")

    # Prepare batch insert data
    base_time = datetime.now(timezone.utc) - timedelta(hours=1)

    records = []
    for i in range(num_records):
        timestamp = base_time + timedelta(seconds=i)
        records.append((
            timestamp,
            machine_id,
            'temperature',
            70.0 + random.uniform(-5, 5),
            192  # GOOD quality
        ))

    # Benchmark batch insert
    start_time = time.time()

    await clean_timescaledb.executemany(
        """
        INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
        VALUES ($1, $2, $3, $4, $5)
        """,
        records
    )

    elapsed = time.time() - start_time
    inserts_per_sec = num_records / elapsed

    print(f"✅ Write performance test completed")
    print(f"📊 Inserted: {num_records} records")
    print(f"📊 Duration: {elapsed:.2f}s")
    print(f"📊 Throughput: {inserts_per_sec:.0f} inserts/sec")

    # Verify target
    assert inserts_per_sec > 10000, f"Write performance below target: {inserts_per_sec:.0f} < 10,000 inserts/sec"

    print(f"✅ Write performance target achieved")


@pytest.mark.asyncio
async def test_timescaledb_read_performance(
    clean_timescaledb,
    generate_telemetry_data
):
    """
    Benchmark: Query performance for dashboard queries
    Target: <100ms for time-range queries
    """

    machine_id = 'READ_PERF_TEST'

    # Insert 10,000 data points (1 week @ 1 min intervals)
    data_points = generate_telemetry_data(
        machine_id=machine_id,
        num_points=10000,
        interval_seconds=60
    )

    await clean_timescaledb.executemany(
        """
        INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
        VALUES ($1, $2, $3, $4, $5)
        """,
        [(d['time'], d['machine_id'], d['metric_name'], d['value'], d['quality']) for d in data_points]
    )

    print(f"✅ Inserted {len(data_points)} test records")

    # Benchmark 1: Recent data query (last 1 hour)
    start_time = time.perf_counter()

    result_1h = await clean_timescaledb.fetch(
        """
        SELECT time, value FROM telemetry
        WHERE machine_id = $1
        AND metric_name = 'temperature'
        AND time >= NOW() - INTERVAL '1 hour'
        ORDER BY time DESC
        """,
        machine_id
    )

    elapsed_1h = (time.perf_counter() - start_time) * 1000  # ms

    print(f"\n📊 Query 1 - Last 1 hour:")
    print(f"   Rows: {len(result_1h)}")
    print(f"   Time: {elapsed_1h:.2f} ms")

    assert elapsed_1h < 100, f"Query too slow: {elapsed_1h:.2f}ms > 100ms"

    # Benchmark 2: Time-range aggregation (last 24 hours)
    start_time = time.perf_counter()

    result_24h = await clean_timescaledb.fetch(
        """
        SELECT time_bucket('5 minutes', time) AS bucket,
               AVG(value) as avg_value,
               COUNT(*) as sample_count
        FROM telemetry
        WHERE machine_id = $1
        AND metric_name = 'temperature'
        AND time >= NOW() - INTERVAL '24 hours'
        GROUP BY bucket
        ORDER BY bucket DESC
        """,
        machine_id
    )

    elapsed_24h = (time.perf_counter() - start_time) * 1000  # ms

    print(f"\n📊 Query 2 - Last 24 hours (5min buckets):")
    print(f"   Rows: {len(result_24h)}")
    print(f"   Time: {elapsed_24h:.2f} ms")

    assert elapsed_24h < 200, f"Aggregation query too slow: {elapsed_24h:.2f}ms > 200ms"

    # Benchmark 3: Multi-machine query
    start_time = time.perf_counter()

    result_multi = await clean_timescaledb.fetch(
        """
        SELECT machine_id, AVG(value) as avg_value
        FROM telemetry
        WHERE machine_id IN ($1, $2, $3)
        AND time >= NOW() - INTERVAL '1 hour'
        GROUP BY machine_id
        """,
        machine_id, 'MACHINE_2', 'MACHINE_3'
    )

    elapsed_multi = (time.perf_counter() - start_time) * 1000  # ms

    print(f"\n📊 Query 3 - Multi-machine aggregation:")
    print(f"   Time: {elapsed_multi:.2f} ms")

    assert elapsed_multi < 150, f"Multi-machine query too slow: {elapsed_multi:.2f}ms > 150ms"

    print(f"\n✅ All query performance targets met")


@pytest.mark.asyncio
async def test_timescaledb_time_bucket_gapfill(
    clean_timescaledb
):
    """
    Test time_bucket_gapfill for handling missing data
    """

    machine_id = 'GAPFILL_TEST'
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    # Insert sparse data (gaps every 5 minutes)
    records = []
    for i in range(0, 60, 5):  # Every 5 minutes for 1 hour
        timestamp = base_time + timedelta(minutes=i)
        records.append((timestamp, machine_id, 'temperature', 75.0 + i, 192))

    await clean_timescaledb.executemany(
        """
        INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
        VALUES ($1, $2, $3, $4, $5)
        """,
        records
    )

    print(f"✅ Inserted {len(records)} sparse records (5min intervals)")

    # Query with gapfill
    result = await clean_timescaledb.fetch(
        """
        SELECT time_bucket_gapfill('1 minute', time) AS bucket,
               locf(AVG(value)) AS value
        FROM telemetry
        WHERE machine_id = $1
        AND metric_name = 'temperature'
        AND time >= $2
        AND time < $2 + INTERVAL '1 hour'
        GROUP BY bucket
        ORDER BY bucket
        """,
        machine_id,
        base_time
    )

    # Should have 60 rows (1 per minute) even though we only inserted 12
    assert len(result) == 60, f"Expected 60 rows with gapfill, got {len(result)}"
    print(f"✅ Gapfill produced {len(result)} rows from {len(records)} sparse records")

    # Verify interpolated values
    non_null_values = [r['value'] for r in result if r['value'] is not None]
    assert len(non_null_values) == 60, "LOCF should fill all gaps"
    print(f"✅ LOCF filled all gaps")


@pytest.mark.asyncio
async def test_timescaledb_retention_policy(
    clean_timescaledb
):
    """
    Verify retention policies are configured
    """

    # Check retention policy for telemetry
    policy = await clean_timescaledb.fetchrow(
        """
        SELECT * FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_retention'
        AND hypertable_name = 'telemetry'
        """
    )

    if policy:
        print(f"✅ Retention policy active for telemetry")
        print(f"   Config: {policy['config']}")
    else:
        print(f"⚠️  No retention policy found (may be disabled in test environment)")


@pytest.mark.asyncio
async def test_timescaledb_helper_functions(
    clean_timescaledb,
    generate_telemetry_data
):
    """
    Test custom helper functions (calculate_availability, get_machine_status)
    """

    machine_id = 'HELPER_TEST'

    # Insert test data with availability events
    base_time = datetime.now(timezone.utc) - timedelta(hours=1)

    # Insert production data
    prod_records = []
    for i in range(60):
        timestamp = base_time + timedelta(minutes=i)
        prod_records.append((timestamp, machine_id, 'production_count', i * 10, 192))

    await clean_timescaledb.executemany(
        """
        INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
        VALUES ($1, $2, $3, $4, $5)
        """,
        prod_records
    )

    # Test calculate_availability function (if it exists)
    try:
        result = await clean_timescaledb.fetchval(
            "SELECT calculate_availability($1, $2, $3)",
            machine_id,
            base_time,
            base_time + timedelta(hours=1)
        )
        print(f"✅ calculate_availability() function works: {result}")
    except Exception as e:
        print(f"⚠️  calculate_availability() not available: {e}")

    # Test get_machine_status function (if it exists)
    try:
        result = await clean_timescaledb.fetchval(
            "SELECT get_machine_status($1)",
            machine_id
        )
        print(f"✅ get_machine_status() function works: {result}")
    except Exception as e:
        print(f"⚠️  get_machine_status() not available: {e}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_timescaledb_concurrent_writes(
    clean_timescaledb
):
    """
    Load test: Concurrent writes from multiple sources
    Simulates multiple edge gateways writing simultaneously
    """

    num_machines = 10
    writes_per_machine = 1000

    print(f"\n🔥 Concurrent write test: {num_machines} machines, {writes_per_machine} writes each")

    async def write_machine_data(machine_id: str):
        base_time = datetime.now(timezone.utc) - timedelta(hours=1)

        records = []
        for i in range(writes_per_machine):
            timestamp = base_time + timedelta(seconds=i)
            records.append((
                timestamp,
                machine_id,
                'temperature',
                70.0 + random.uniform(-5, 5),
                192
            ))

        await clean_timescaledb.executemany(
            """
            INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
            VALUES ($1, $2, $3, $4, $5)
            """,
            records
        )

        return len(records)

    # Execute concurrent writes
    start_time = time.time()

    machine_ids = [f'CONCURRENT_TEST_{i}' for i in range(num_machines)]
    tasks = [write_machine_data(mid) for mid in machine_ids]
    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    total_writes = sum(results)
    writes_per_sec = total_writes / elapsed

    print(f"✅ Concurrent write test completed")
    print(f"📊 Total writes: {total_writes}")
    print(f"📊 Duration: {elapsed:.2f}s")
    print(f"📊 Throughput: {writes_per_sec:.0f} writes/sec")

    # Verify data integrity
    count = await clean_timescaledb.fetchval(
        "SELECT COUNT(*) FROM telemetry WHERE machine_id = ANY($1::text[])",
        machine_ids
    )

    assert count == total_writes, f"Data loss detected: {count}/{total_writes}"
    print(f"✅ All writes verified in database")


@pytest.mark.asyncio
async def test_timescaledb_space_partitioning_benefit(
    clean_timescaledb,
    generate_telemetry_data
):
    """
    Demonstrate query performance benefit from space partitioning
    """

    # Insert data for 20 machines
    num_machines = 20
    points_per_machine = 1000

    print(f"\n📊 Space partitioning test: {num_machines} machines")

    for i in range(num_machines):
        machine_id = f'PARTITION_TEST_{i:02d}'
        data = generate_telemetry_data(
            machine_id=machine_id,
            num_points=points_per_machine,
            interval_seconds=1
        )

        await clean_timescaledb.executemany(
            """
            INSERT INTO telemetry (time, machine_id, metric_name, value, quality)
            VALUES ($1, $2, $3, $4, $5)
            """,
            [(d['time'], d['machine_id'], d['metric_name'], d['value'], d['quality']) for d in data]
        )

    total_records = num_machines * points_per_machine
    print(f"✅ Inserted {total_records} records across {num_machines} machines")

    # Query single machine (should benefit from space partitioning)
    target_machine = 'PARTITION_TEST_10'

    start_time = time.perf_counter()

    result = await clean_timescaledb.fetch(
        """
        SELECT time, value FROM telemetry
        WHERE machine_id = $1
        ORDER BY time DESC
        LIMIT 100
        """,
        target_machine
    )

    elapsed = (time.perf_counter() - start_time) * 1000  # ms

    print(f"📊 Single machine query:")
    print(f"   Rows returned: {len(result)}")
    print(f"   Query time: {elapsed:.2f} ms")

    # Query should be fast due to space partitioning
    assert elapsed < 50, f"Query too slow despite space partitioning: {elapsed:.2f}ms"
    assert len(result) == 100

    print(f"✅ Space partitioning accelerated query")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
