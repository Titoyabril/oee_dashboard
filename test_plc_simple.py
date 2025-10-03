"""
Simple direct test of PLC simulator data flow
Shows tags being read from simulator through to logs
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def read_plc_tags(host='localhost', port=44818):
    """Read tags directly from PLC simulator"""

    logger.info("="*100)
    logger.info("ALLEN-BRADLEY CONTROLLOGIX PLC SIMULATOR - DATA FLOW DEMONSTRATION")
    logger.info("="*100)

    # Connect to simulator
    logger.info(f"\n📡 STEP 1: Connecting to PLC Simulator at {host}:{port}")
    reader, writer = await asyncio.open_connection(host, port)
    logger.info("   ✅ Connected successfully!")

    try:
        # Read all production tags for LINE-001
        tags_to_read = [
            'Line_LINE_001_ProductionCount',
            'Line_LINE_001_TargetCount',
            'Line_LINE_001_GoodCount',
            'Line_LINE_001_RejectCount',
            'Line_LINE_001_Running',
            'Line_LINE_001_Faulted',
            'Line_LINE_001_OEE',
            'Line_LINE_001_Availability',
            'Line_LINE_001_Performance',
            'Line_LINE_001_Quality',
            'Line_LINE_001_CycleTime',
            'Line_LINE_001_DowntimeMinutes',
            'Line_LINE_001_LastFaultCode',
        ]

        logger.info(f"\n📖 STEP 2: Reading {len(tags_to_read)} Tags from PLC")

        # Send read request
        req = {'method': 'read', 'params': {'tags': tags_to_read}}
        data = json.dumps(req).encode('utf-8')
        writer.write(len(data).to_bytes(4, 'big') + data)
        await writer.drain()

        # Read response
        length = int.from_bytes(await reader.readexactly(4), 'big')
        resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

        if not resp.get('success'):
            logger.error(f"   ❌ Failed to read tags: {resp.get('error')}")
            return

        results = resp.get('results', [])
        logger.info(f"   ✅ Successfully read {len(results)} tags")

        # Display results organized by category
        logger.info(f"\n{'='*100}")
        logger.info("📊 PRODUCTION METRICS (LINE-001)")
        logger.info(f"{'='*100}")

        production_data = {}
        for r in results:
            tag_name = r['tag'].replace('Line_LINE_001_', '')
            production_data[tag_name] = r['value']

        # Production counts
        logger.info(f"\n🏭 Production Counters:")
        logger.info(f"   ProductionCount  : {production_data['ProductionCount']:>8} parts")
        logger.info(f"   TargetCount      : {production_data['TargetCount']:>8} parts")
        logger.info(f"   GoodCount        : {production_data['GoodCount']:>8} parts")
        logger.info(f"   RejectCount      : {production_data['RejectCount']:>8} parts")

        quality_rate = (production_data['GoodCount'] / production_data['ProductionCount'] * 100) if production_data['ProductionCount'] > 0 else 0
        logger.info(f"   Quality Rate     : {quality_rate:>7.1f}%")

        # Machine status
        logger.info(f"\n🔧 Machine Status:")
        logger.info(f"   Running          : {'✅ YES' if production_data['Running'] else '❌ NO'}")
        logger.info(f"   Faulted          : {'⚠️  YES' if production_data['Faulted'] else '✅ NO'}")
        logger.info(f"   Downtime         : {production_data['DowntimeMinutes']:>7.1f} minutes")
        logger.info(f"   Last Fault Code  : {production_data['LastFaultCode']:>8}")

        # OEE metrics
        logger.info(f"\n📈 OEE Performance Metrics:")
        logger.info(f"   Overall OEE      : {production_data['OEE']:>6.1f}%")
        logger.info(f"   Availability     : {production_data['Availability']:>6.1f}%")
        logger.info(f"   Performance      : {production_data['Performance']:>6.1f}%")
        logger.info(f"   Quality          : {production_data['Quality']:>6.1f}%")
        logger.info(f"   Cycle Time       : {production_data['CycleTime']:>6.2f} sec")

        # Monitor changes over time
        logger.info(f"\n{'='*100}")
        logger.info("⏱️  STEP 3: Monitoring Real-Time Data Changes (5 second intervals)")
        logger.info(f"{'='*100}")

        for i in range(4):
            await asyncio.sleep(5)

            # Read key metrics
            req = {'method': 'read', 'params': {'tags': [
                'Line_LINE_001_ProductionCount',
                'Line_LINE_001_OEE',
                'Line_LINE_001_Running',
                'Line_LINE_001_Faulted'
            ]}}
            data = json.dumps(req).encode('utf-8')
            writer.write(len(data).to_bytes(4, 'big') + data)
            await writer.drain()

            length = int.from_bytes(await reader.readexactly(4), 'big')
            resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

            if resp.get('success'):
                r = {x['tag'].replace('Line_LINE_001_', ''): x['value'] for x in resp['results']}
                timestamp = datetime.now().strftime('%H:%M:%S')

                status = ""
                if r['Faulted']:
                    status = "⚠️  FAULTED"
                elif r['Running']:
                    status = "✅ RUNNING"
                else:
                    status = "🔴 STOPPED"

                logger.info(f"\n   Update #{i+1} @ {timestamp}")
                logger.info(f"   ├─ Production Count : {r['ProductionCount']:>4} parts")
                logger.info(f"   ├─ OEE             : {r['OEE']:>5.1f}%")
                logger.info(f"   └─ Status          : {status}")

        # Simulate Sparkplug B MQTT publish
        logger.info(f"\n{'='*100}")
        logger.info("📤 STEP 4: Sparkplug B MQTT Publish Simulation")
        logger.info(f"{'='*100}")

        # Read final data
        req = {'method': 'read', 'params': {'tags': tags_to_read}}
        data = json.dumps(req).encode('utf-8')
        writer.write(len(data).to_bytes(4, 'big') + data)
        await writer.drain()

        length = int.from_bytes(await reader.readexactly(4), 'big')
        resp = json.loads((await reader.readexactly(length)).decode('utf-8'))

        if resp.get('success'):
            logger.info(f"\n   Sparkplug B Payload:")
            logger.info(f"   ├─ Topic: spBv1.0/OEE_SITE/DDATA/EdgeNode1/LINE-001")
            logger.info(f"   ├─ Timestamp: {int(datetime.now().timestamp() * 1000)}")
            logger.info(f"   ├─ Metrics: {len(resp['results'])}")
            logger.info(f"   └─ Sample Metrics:")

            for i, r in enumerate(resp['results'][:5], 1):
                metric_name = r['tag'].replace('Line_LINE_001_', '').lower()
                logger.info(f"       {i}. {metric_name:30s} = {r['value']}")

            logger.info(f"       ... ({len(resp['results']) - 5} more metrics)")

        # Summary
        logger.info(f"\n{'='*100}")
        logger.info("✅ DATA FLOW TEST COMPLETED SUCCESSFULLY")
        logger.info(f"{'='*100}")
        logger.info(f"\n📋 Data Flow Path Demonstrated:")
        logger.info(f"   1. ✅ PLC Simulator (Docker container on port {port})")
        logger.info(f"   2. ✅ TCP/IP Socket Connection")
        logger.info(f"   3. ✅ JSON-RPC Protocol")
        logger.info(f"   4. ✅ Tag Read Operations ({len(tags_to_read)} tags)")
        logger.info(f"   5. ✅ Real-time Data Monitoring")
        logger.info(f"   6. 📋 Ready for: Allen-Bradley Connector Integration")
        logger.info(f"   7. 📋 Ready for: Sparkplug B MQTT Publishing")
        logger.info(f"   8. 📋 Ready for: TimescaleDB Storage")
        logger.info(f"   9. 📋 Ready for: Django API & Dashboard")
        logger.info("")

    finally:
        writer.close()
        await writer.wait_closed()
        logger.info("   🔌 Disconnected from simulator\n")


if __name__ == '__main__':
    try:
        asyncio.run(read_plc_tags())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Test interrupted by user\n")
    except Exception as e:
        logger.error(f"\n\n❌ Error: {e}\n", exc_info=True)
