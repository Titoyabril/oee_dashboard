import redis

try:
    # Connect to Redis (Memurai runs on default port 6379)
    r = redis.Redis(host='localhost', port=6379, db=0)

    # Test write
    r.set("test_key", "Hello from Redis!")

    # Test read
    value = r.get("test_key")
    print("Value from Redis:", value.decode())

    # Test ping
    if r.ping():
        print("Redis connection OK ✅")

except redis.ConnectionError as e:
    print("Redis connection failed ❌:", e)
