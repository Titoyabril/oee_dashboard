"""
Test connectivity to all 10 PLC simulators
"""
import asyncio
import socket
import json
from typing import List, Dict, Any


async def send_request(host: str, port: int, request: dict) -> dict:
    """Send length-prefixed JSON request to simulator"""
    reader, writer = await asyncio.open_connection(host, port)

    # Send request (length-prefixed)
    request_json = json.dumps(request).encode('utf-8')
    length_bytes = len(request_json).to_bytes(4, 'big')
    writer.write(length_bytes + request_json)
    await writer.drain()

    # Receive response (length-prefixed)
    length_bytes = await reader.readexactly(4)
    length = int.from_bytes(length_bytes, 'big')
    response_data = await reader.readexactly(length)
    response = json.loads(response_data.decode('utf-8'))

    # Close connection
    writer.close()
    await writer.wait_closed()

    return response


async def test_simulator(line_num: int, port: int) -> Dict[str, Any]:
    """Test a single simulator"""
    try:
        # Read production count and OEE
        line_id = f"LINE-{line_num:03d}"
        prefix = f"Line_{line_id.replace('-', '_')}"

        request = {
            "method": "read",
            "params": {
                "tags": [
                    f"{prefix}_ProductionCount",
                    f"{prefix}_OEE",
                    f"{prefix}_Running",
                    f"{prefix}_GoodCount"
                ]
            }
        }

        response = await send_request("localhost", port, request)

        if response.get("success") and response.get("results"):
            results = response["results"]
            return {
                "line": line_id,
                "port": port,
                "status": "[OK] Connected",
                "production": results[0]["value"],
                "oee": f"{results[1]['value']:.1f}%",
                "running": results[2]["value"],
                "good_count": results[3]["value"]
            }
        else:
            return {
                "line": line_id,
                "port": port,
                "status": "[ERROR]",
                "error": response.get("error", "Unknown error")
            }
    except Exception as e:
        return {
            "line": f"LINE-{line_num:03d}",
            "port": port,
            "status": "[FAILED]",
            "error": str(e)
        }


async def main():
    """Test all 10 simulators"""
    print("=" * 80)
    print("Testing connectivity to all 10 ControlLogix PLC simulators")
    print("=" * 80)
    print()

    # Configuration for all 10 lines
    simulators = [
        (1, 44818), (2, 44819), (3, 44820), (4, 44821), (5, 44822),
        (6, 44823), (7, 44824), (8, 44825), (9, 44826), (10, 44827)
    ]

    # Test all simulators concurrently
    tasks = [test_simulator(line_num, port) for line_num, port in simulators]
    results = await asyncio.gather(*tasks)

    # Print results
    print(f"{'Line':<12} {'Port':<8} {'Status':<15} {'Production':<12} {'OEE':<10} {'Running':<10} {'Good Count'}")
    print("-" * 80)

    connected_count = 0
    for result in results:
        if result["status"] == "[OK] Connected":
            connected_count += 1
            print(f"{result['line']:<12} {result['port']:<8} {result['status']:<15} "
                  f"{result['production']:<12} {result['oee']:<10} {result['running']:<10} {result['good_count']}")
        else:
            print(f"{result['line']:<12} {result['port']:<8} {result['status']:<15} "
                  f"Error: {result.get('error', 'Unknown')}")

    print()
    print(f"Summary: {connected_count}/10 simulators responding")
    print()

    if connected_count == 10:
        print("[OK] All simulators are running and responding correctly!")
    else:
        print(f"[ERROR] {10 - connected_count} simulator(s) not responding")


if __name__ == '__main__':
    asyncio.run(main())
