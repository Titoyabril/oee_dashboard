"""
Test script to demonstrate data flow from Allen-Bradley simulators through the system
Shows: PLC Simulator -> Allen-Bradley Connector -> MQTT Sparkplug B -> Logs
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging to show data flow
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def test_allen_bradley_data_flow():
    """Test complete data flow from PLC simulators"""

    logger.info("="*80)
    logger.info("ALLEN-BRADLEY PLC SIMULATOR DATA FLOW TEST")
    logger.info("="*80)

    # Import after path is set
    from oee_analytics.sparkplug.connectors.allen_bradley import AllenBradleyConnector, AllenBradleyConfig
    from oee_analytics.sparkplug.connectors.base import PLCConnectionConfig

    # Configure for simulator mode
    config = AllenBradleyConfig(
        host="localhost",
        port=44818,
        plc_family="CONTROLLOGIX",
        slot=0,
        timeout=5.0,
        simulator_mode=True  # Use simulator instead of real PLC
    )

    logger.info(f"\n{'='*80}")
    logger.info("STEP 1: Connecting to PLC Simulator")
    logger.info(f"{'='*80}")
    logger.info(f"  Host: {config.host}:{config.port}")
    logger.info(f"  PLC Family: {config.plc_family}")
    logger.info(f"  Simulator Mode: {config.simulator_mode}")

    # Create connector
    connector = AllenBradleyConnector(config, logger=logger)

    try:
        # Connect to simulator
        connected = await connector.connect()

        if not connected:
            logger.error("Failed to connect to simulator")
            return

        logger.info(f"\n{'='*80}")
        logger.info("STEP 2: Reading Tags from PLC Simulator")
        logger.info(f"{'='*80}")

        # Define tags to read (matching our simulator)
        tags_to_read = [
            ("Line_LINE_001_ProductionCount", "DINT"),
            ("Line_LINE_001_TargetCount", "DINT"),
            ("Line_LINE_001_GoodCount", "DINT"),
            ("Line_LINE_001_RejectCount", "DINT"),
            ("Line_LINE_001_Running", "BOOL"),
            ("Line_LINE_001_Faulted", "BOOL"),
            ("Line_LINE_001_OEE", "REAL"),
            ("Line_LINE_001_Availability", "REAL"),
            ("Line_LINE_001_Performance", "REAL"),
            ("Line_LINE_001_Quality", "REAL"),
            ("Line_LINE_001_CycleTime", "REAL"),
            ("Line_LINE_001_DowntimeMinutes", "REAL"),
            ("Line_LINE_001_LastFaultCode", "INT"),
        ]

        logger.info(f"  Reading {len(tags_to_read)} tags...")

        # Read all tags
        data_points = await connector.read_multiple(tags_to_read)

        logger.info(f"\n{'='*80}")
        logger.info("STEP 3: Displaying Tag Values")
        logger.info(f"{'='*80}")

        # Group by category for better display
        production_tags = []
        status_tags = []
        oee_tags = []
        other_tags = []

        for dp in data_points:
            tag_name = dp.address.replace("Line_LINE_001_", "")

            if any(x in tag_name for x in ['ProductionCount', 'TargetCount', 'GoodCount', 'RejectCount']):
                production_tags.append((tag_name, dp.value, dp.data_type))
            elif any(x in tag_name for x in ['Running', 'Faulted', 'Stopped']):
                status_tags.append((tag_name, dp.value, dp.data_type))
            elif any(x in tag_name for x in ['OEE', 'Availability', 'Performance', 'Quality']):
                oee_tags.append((tag_name, dp.value, dp.data_type))
            else:
                other_tags.append((tag_name, dp.value, dp.data_type))

        # Display Production Metrics
        logger.info("\n  📊 PRODUCTION METRICS:")
        for tag_name, value, data_type in production_tags:
            logger.info(f"    ├─ {tag_name:20s} = {value:>8} ({data_type})")

        # Display Machine Status
        logger.info("\n  🔧 MACHINE STATUS:")
        for tag_name, value, data_type in status_tags:
            status_icon = "✅" if value else "❌"
            logger.info(f"    ├─ {tag_name:20s} = {status_icon} {value} ({data_type})")

        # Display OEE Metrics
        logger.info("\n  📈 OEE METRICS:")
        for tag_name, value, data_type in oee_tags:
            logger.info(f"    ├─ {tag_name:20s} = {value:>6.1f}% ({data_type})")

        # Display Other Metrics
        if other_tags:
            logger.info("\n  ⚙️  OTHER METRICS:")
            for tag_name, value, data_type in other_tags:
                logger.info(f"    ├─ {tag_name:20s} = {value:>8} ({data_type})")

        # Wait a bit and read again to show data changing
        logger.info(f"\n{'='*80}")
        logger.info("STEP 4: Monitoring Data Changes (5 second interval)")
        logger.info(f"{'='*80}")

        for i in range(3):
            await asyncio.sleep(5)

            # Read key metrics
            key_tags = [
                ("Line_LINE_001_ProductionCount", "DINT"),
                ("Line_LINE_001_OEE", "REAL"),
                ("Line_LINE_001_Running", "BOOL"),
            ]

            key_data = await connector.read_multiple(key_tags)

            logger.info(f"\n  Update {i+1}/3 @ {datetime.now().strftime('%H:%M:%S')}:")
            logger.info(f"    Production Count: {key_data[0].value} parts")
            logger.info(f"    OEE:              {key_data[1].value:.1f}%")
            logger.info(f"    Running:          {'✅ YES' if key_data[2].value else '❌ NO'}")

        logger.info(f"\n{'='*80}")
        logger.info("STEP 5: Simulating Sparkplug B MQTT Publish")
        logger.info(f"{'='*80}")

        # Show what would be published to MQTT
        final_data = await connector.read_multiple(tags_to_read)

        sparkplug_payload = {
            "timestamp": int(datetime.now().timestamp() * 1000),
            "metrics": []
        }

        for dp in final_data:
            metric_name = dp.address.replace("Line_LINE_001_", "").lower()
            sparkplug_payload["metrics"].append({
                "name": metric_name,
                "timestamp": int(dp.timestamp.timestamp() * 1000) if dp.timestamp else None,
                "datatype": dp.data_type,
                "value": dp.value
            })

        logger.info("\n  📤 Sparkplug B Payload (would be published to MQTT):")
        logger.info(f"    Topic: spBv1.0/OEE_SITE/DDATA/EdgeNode1/LINE-001")
        logger.info(f"    Timestamp: {sparkplug_payload['timestamp']}")
        logger.info(f"    Metrics Count: {len(sparkplug_payload['metrics'])}")
        logger.info("\n  Sample Metrics:")
        for metric in sparkplug_payload['metrics'][:5]:
            logger.info(f"    ├─ {metric['name']:25s} = {metric['value']} ({metric['datatype']})")
        logger.info(f"    └─ ... ({len(sparkplug_payload['metrics']) - 5} more metrics)")

        logger.info(f"\n{'='*80}")
        logger.info("✅ DATA FLOW TEST COMPLETED SUCCESSFULLY")
        logger.info(f"{'='*80}")
        logger.info("\nData Flow Path:")
        logger.info("  1. ✅ PLC Simulator (Docker container)")
        logger.info("  2. ✅ Allen-Bradley Connector (pycomm3 shim)")
        logger.info("  3. ✅ Tag Read Operations")
        logger.info("  4. ✅ Data Point Objects")
        logger.info("  5. 📋 Ready for: Sparkplug B MQTT Publish")
        logger.info("  6. 📋 Ready for: TimescaleDB Ingestion")
        logger.info("  7. 📋 Ready for: Dashboard Display")

    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

    finally:
        # Disconnect
        logger.info("\n  Disconnecting from simulator...")
        await connector.disconnect()
        logger.info("  Disconnected.")


if __name__ == '__main__':
    try:
        asyncio.run(test_allen_bradley_data_flow())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
