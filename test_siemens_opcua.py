"""
Test connectivity to Siemens S7 PLC simulators via OPC UA
"""
import asyncio
from asyncua import Client
from typing import Dict, Any


async def test_opcua_connection(endpoint: str, line_id: str) -> Dict[str, Any]:
    """Test connection to a single OPC UA server"""
    try:
        client = Client(url=endpoint)
        await client.connect()

        # Get namespace index
        namespaces = await client.get_namespace_array()
        ns = 2  # Custom namespace

        # Read production data using numeric node IDs
        node_paths = {
            "ProductionCount": f"ns={ns};i=4",
            "TargetCount": f"ns={ns};i=5",
            "GoodCount": f"ns={ns};i=6",
            "RejectCount": f"ns={ns};i=7",
            "Running": f"ns={ns};i=8",
            "Faulted": f"ns={ns};i=9",
            "OEE": f"ns={ns};i=11",
            "Availability": f"ns={ns};i=12",
            "Performance": f"ns={ns};i=13",
            "Quality": f"ns={ns};i=14",
            "CycleTime": f"ns={ns};i=15",
            "DowntimeMinutes": f"ns={ns};i=17",
            "LastFaultCode": f"ns={ns};i=18",
        }

        # Read all values
        results = {}
        for name, node_id in node_paths.items():
            try:
                node = client.get_node(node_id)
                value = await node.read_value()
                results[name] = value
            except Exception as e:
                results[name] = f"ERROR: {e}"

        await client.disconnect()

        return {
            "status": "[OK] Connected",
            "line": line_id,
            "endpoint": endpoint,
            "data": results
        }

    except Exception as e:
        return {
            "status": "[FAILED]",
            "line": line_id,
            "endpoint": endpoint,
            "error": str(e)
        }


async def main():
    """Test both Siemens S7 OPC UA simulators"""
    print("=" * 80)
    print("Testing connectivity to Siemens S7-1500 OPC UA simulators")
    print("=" * 80)
    print()

    # Configuration for 2 Siemens PLCs
    plcs = [
        ("opc.tcp://localhost:4841/freeopcua/server/", "SIEMENS-001"),
        ("opc.tcp://localhost:4842/freeopcua/server/", "SIEMENS-002"),
    ]

    # Test both PLCs concurrently
    tasks = [test_opcua_connection(endpoint, line_id) for endpoint, line_id in plcs]
    results = await asyncio.gather(*tasks)

    # Print results
    connected_count = 0
    for result in results:
        print(f"Line: {result['line']}")
        print(f"Endpoint: {result['endpoint']}")
        print(f"Status: {result['status']}")

        if result['status'] == "[OK] Connected":
            connected_count += 1
            data = result['data']
            print()
            print(f"  Production Count:  {data.get('ProductionCount', 'N/A')}")
            print(f"  Target Count:      {data.get('TargetCount', 'N/A')}")
            print(f"  Good Count:        {data.get('GoodCount', 'N/A')}")
            print(f"  Reject Count:      {data.get('RejectCount', 'N/A')}")
            print(f"  Running:           {data.get('Running', 'N/A')}")
            print(f"  Faulted:           {data.get('Faulted', 'N/A')}")
            print(f"  OEE:               {data.get('OEE', 'N/A')}%")
            print(f"  Availability:      {data.get('Availability', 'N/A')}%")
            print(f"  Performance:       {data.get('Performance', 'N/A')}%")
            print(f"  Quality:           {data.get('Quality', 'N/A')}%")
            print(f"  Cycle Time:        {data.get('CycleTime', 'N/A')} seconds")
            print(f"  Downtime:          {data.get('DowntimeMinutes', 'N/A')} minutes")
            print(f"  Last Fault Code:   {data.get('LastFaultCode', 'N/A')}")
        else:
            print(f"  Error: {result.get('error', 'Unknown')}")

        print()
        print("-" * 80)
        print()

    print(f"Summary: {connected_count}/2 Siemens PLCs responding")
    print()

    if connected_count == 2:
        print("[OK] All Siemens S7-1500 OPC UA simulators are running and responding correctly!")
    else:
        print(f"[ERROR] {2 - connected_count} simulator(s) not responding")


if __name__ == '__main__':
    asyncio.run(main())
