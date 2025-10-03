"""
Monitor all 12 PLC simulators in real-time
Shows data flowing from all Allen-Bradley and Siemens PLCs
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from asyncua import Client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def read_allen_bradley(line_num: int, port: int):
    """Read data from Allen-Bradley PLC"""
    line_id = f"LINE-{line_num:03d}"
    prefix = f"Line_{line_id.replace('-', '_')}"

    try:
        reader, writer = await asyncio.open_connection('localhost', port)

        req = {
            'method': 'read',
            'params': {
                'tags': [
                    f'{prefix}_ProductionCount',
                    f'{prefix}_OEE',
                    f'{prefix}_Running',
                    f'{prefix}_GoodCount'
                ]
            }
        }

        data = json.dumps(req).encode('utf-8')
        writer.write(len(data).to_bytes(4, 'big') + data)
        await writer.drain()

        length = int.from_bytes(await reader.readexactly(4), 'big')
        resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

        writer.close()
        await writer.wait_closed()

        if resp.get('success'):
            r = resp['results']
            return {
                'type': 'Allen-Bradley',
                'line': line_id,
                'port': port,
                'production': r[0]['value'],
                'oee': f"{r[1]['value']:.1f}%",
                'running': r[2]['value'],
                'good': r[3]['value'],
                'status': 'OK'
            }

    except Exception as e:
        return {
            'type': 'Allen-Bradley',
            'line': line_id,
            'port': port,
            'status': 'ERROR',
            'error': str(e)
        }


async def read_siemens_opcua(line_id: str, port: int):
    """Read data from Siemens S7 via OPC UA"""
    try:
        endpoint = f"opc.tcp://localhost:{port}/freeopcua/server/"
        client = Client(url=endpoint)
        await client.connect()

        # Read key metrics using node IDs
        ns = 2
        prod_count = await client.get_node(f"ns={ns};i=4").read_value()
        oee = await client.get_node(f"ns={ns};i=11").read_value()
        running = await client.get_node(f"ns={ns};i=8").read_value()
        good = await client.get_node(f"ns={ns};i=6").read_value()

        await client.disconnect()

        return {
            'type': 'Siemens S7-1500',
            'line': line_id,
            'port': port,
            'production': prod_count,
            'oee': f"{oee:.1f}%",
            'running': running,
            'good': good,
            'status': 'OK'
        }

    except Exception as e:
        return {
            'type': 'Siemens S7-1500',
            'line': line_id,
            'port': port,
            'status': 'ERROR',
            'error': str(e)
        }


async def monitor_all():
    """Monitor all 12 PLC simulators"""
    logger.info("="*120)
    logger.info("  REAL-TIME PLC MONITORING - ALL 12 SIMULATORS")
    logger.info("="*120)

    # Allen-Bradley ControlLogix PLCs (10 simulators)
    ab_configs = [
        (1, 44818), (2, 44819), (3, 44820), (4, 44821), (5, 44822),
        (6, 44823), (7, 44824), (8, 44825), (9, 44826), (10, 44827)
    ]

    # Siemens S7-1500 PLCs (2 simulators)
    siemens_configs = [
        ("SIEMENS-001", 4841),
        ("SIEMENS-002", 4842)
    ]

    while True:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"\n{'='*120}")
        logger.info(f"  Update @ {timestamp}")
        logger.info(f"{'='*120}\n")

        # Read all Allen-Bradley PLCs
        logger.info("  ALLEN-BRADLEY CONTROLLOGIX PLCs:")
        logger.info("  " + "-"*116)
        logger.info(f"  {'Line':<15} {'Port':<8} {'Status':<10} {'Production':<12} {'OEE':<10} {'Running':<10} {'Good Count'}")
        logger.info("  " + "-"*116)

        ab_tasks = [read_allen_bradley(line, port) for line, port in ab_configs]
        ab_results = await asyncio.gather(*ab_tasks)

        for result in ab_results:
            if result['status'] == 'OK':
                running_icon = '[RUN]' if result['running'] else '[STOP]'
                logger.info(f"  {result['line']:<15} {result['port']:<8} {result['status']:<10} "
                          f"{result['production']:<12} {result['oee']:<10} {running_icon:<10} {result['good']}")
            else:
                logger.info(f"  {result['line']:<15} {result['port']:<8} {result['status']:<10} "
                          f"ERROR: {result.get('error', 'Unknown')[:40]}")

        # Read all Siemens PLCs
        logger.info("\n  SIEMENS S7-1500 PLCs (OPC UA):")
        logger.info("  " + "-"*116)
        logger.info(f"  {'Line':<15} {'Port':<8} {'Status':<10} {'Production':<12} {'OEE':<10} {'Running':<10} {'Good Count'}")
        logger.info("  " + "-"*116)

        siemens_tasks = [read_siemens_opcua(line, port) for line, port in siemens_configs]
        siemens_results = await asyncio.gather(*siemens_tasks)

        for result in siemens_results:
            if result['status'] == 'OK':
                running_icon = '[RUN]' if result['running'] else '[STOP]'
                logger.info(f"  {result['line']:<15} {result['port']:<8} {result['status']:<10} "
                          f"{result['production']:<12} {result['oee']:<10} {running_icon:<10} {result['good']}")
            else:
                logger.info(f"  {result['line']:<15} {result['port']:<8} {result['status']:<10} "
                          f"ERROR: {result.get('error', 'Unknown')[:40]}")

        # Summary
        ab_ok = sum(1 for r in ab_results if r['status'] == 'OK')
        siemens_ok = sum(1 for r in siemens_results if r['status'] == 'OK')
        total_ok = ab_ok + siemens_ok

        logger.info("\n  " + "-"*116)
        logger.info(f"  Summary: {total_ok}/12 PLCs responding ({ab_ok}/10 Allen-Bradley, {siemens_ok}/2 Siemens)")
        logger.info("  " + "-"*116)

        # Wait before next update
        await asyncio.sleep(5)


if __name__ == '__main__':
    try:
        asyncio.run(monitor_all())
    except KeyboardInterrupt:
        logger.info("\n\nMonitoring stopped by user\n")
    except Exception as e:
        logger.error(f"\n\nError: {e}\n", exc_info=True)
