"""
pycomm3 Compatibility Shim for PLC Simulator
Provides a drop-in replacement for pycomm3.LogixDriver that connects to the simulator server
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class Tag:
    """Tag read result compatible with pycomm3"""
    tag: str
    value: Any
    type: Optional[str] = None
    error: Optional[str] = None


class SimulatorLogixDriver:
    """
    Drop-in replacement for pycomm3.LogixDriver
    Connects to the PLC simulator server instead of a real PLC
    """

    def __init__(self, path: str, *args, **kwargs):
        """
        Initialize simulator driver

        Args:
            path: IP address or hostname (e.g., "192.168.1.10" or "controllogix-sim")
            *args, **kwargs: Compatibility with pycomm3.LogixDriver (ignored)
        """
        # Parse path to get IP
        if '/' in path:
            self.host = path.split('/')[0]
        else:
            self.host = path

        self.port = kwargs.get('port', 44818)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self._info_cache = None

    async def _ensure_connected(self):
        """Ensure connection to simulator server"""
        if not self.connected:
            await self._connect()

    async def _connect(self):
        """Connect to simulator server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            self.connected = True
            logger.info(f"Connected to PLC simulator at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to simulator: {e}")
            self.connected = False
            raise

    async def _send_request(self, method: str, params: dict = None) -> dict:
        """Send request to simulator server"""
        await self._ensure_connected()

        request = {
            'method': method,
            'params': params or {}
        }

        # Send length-prefixed JSON
        request_data = json.dumps(request).encode('utf-8')
        request_length = len(request_data).to_bytes(4, 'big')

        self.writer.write(request_length + request_data)
        await self.writer.drain()

        # Read response
        length_bytes = await self.reader.readexactly(4)
        length = int.from_bytes(length_bytes, 'big')

        response_data = await self.reader.readexactly(length)
        response = json.loads(response_data.decode('utf-8'))

        return response

    def open(self):
        """Open connection (synchronous wrapper)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect())
        finally:
            loop.close()
        return self

    def close(self):
        """Close connection"""
        if self.writer:
            self.writer.close()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.writer.wait_closed())
            finally:
                loop.close()
        self.connected = False

    def read(self, *tags: str) -> Any:
        """
        Read one or more tags (synchronous)

        Compatible with pycomm3 interface:
        - Single tag: driver.read('tag1') -> Tag object
        - Multiple tags: driver.read('tag1', 'tag2') -> List[Tag]
        """
        # Try to use existing event loop if running in async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, need to run in executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._sync_read, tags)
                # Can't use loop.run_in_executor here as we're already in the loop
                # Return a blocking result
                return future.result()
        except RuntimeError:
            # No running loop, create new one
            return self._sync_read(tags)

    def _sync_read(self, tags: tuple) -> Any:
        """Synchronous read implementation"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self._send_request('read', {'tags': list(tags)})
            )

            if not response.get('success'):
                error_msg = response.get('error', 'Unknown error')
                # Return error Tag objects
                result = [Tag(tag=t, value=None, error=error_msg) for t in tags]
            else:
                results = response.get('results', [])
                result = [
                    Tag(
                        tag=r['tag'],
                        value=r['value'],
                        error=r.get('error')
                    )
                    for r in results
                ]

            # Return single Tag if single tag requested, else list
            if len(result) == 1:
                return result[0]
            return result

        finally:
            loop.close()

    def write(self, tag: str, value: Any) -> Tag:
        """Write a value to a tag (synchronous)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self._send_request('write', {'tag': tag, 'value': value})
            )

            return Tag(
                tag=response.get('tag'),
                value=response.get('value'),
                error=response.get('error') if not response.get('success') else None
            )

        finally:
            loop.close()

    def get_tag_list(self, all_tags: bool = True, cache: bool = False) -> List[Dict]:
        """Get list of all available tags"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self._send_request('get_tag_list')
            )

            if response.get('success'):
                return response.get('tags', [])
            return []

        finally:
            loop.close()

    @property
    def info(self) -> Dict[str, Any]:
        """Get PLC info (compatible with pycomm3)"""
        if self._info_cache:
            return self._info_cache

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self._send_request('get_info')
            )

            if response.get('success'):
                self._info_cache = response.get('info', {})
                return self._info_cache
            return {}

        finally:
            loop.close()

    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Monkey-patch pycomm3 when in simulator mode
def enable_simulator_mode():
    """
    Enable simulator mode by patching pycomm3.LogixDriver
    Call this before creating Allen-Bradley connectors
    """
    try:
        import pycomm3
        pycomm3.LogixDriver = SimulatorLogixDriver
        logger.info("Simulator mode enabled - pycomm3.LogixDriver patched")
    except ImportError:
        logger.warning("pycomm3 not installed, cannot patch")


if __name__ == '__main__':
    # Test the shim
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python pycomm3_shim.py <simulator_host>")
        sys.exit(1)

    host = sys.argv[1]

    print(f"Testing connection to simulator at {host}...")

    with SimulatorLogixDriver(host) as driver:
        print("\nPLC Info:")
        print(driver.info)

        print("\nReading tags:")
        result = driver.read('Line_LINE_001_ProductionCount', 'Line_LINE_001_OEE')
        if isinstance(result, list):
            for tag in result:
                print(f"  {tag.tag}: {tag.value} (error: {tag.error})")
        else:
            print(f"  {result.tag}: {result.value} (error: {result.error})")

        print("\nTag list (first 10):")
        tags = driver.get_tag_list()
        for tag in tags[:10]:
            print(f"  {tag['tag_name']}: {tag['value']} ({tag['data_type']})")
