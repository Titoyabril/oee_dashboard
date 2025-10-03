"""
PLC Simulator Server
Provides network access to the ControlLogix simulator
Wraps the simulator in a simple protocol that the connector can use
"""

import asyncio
import json
import logging
from typing import Optional
from controllogix_simulator import get_simulator, ControlLogixSimulator


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PLCSimulatorServer:
    """
    Network server for ControlLogix simulator
    Provides simple JSON-RPC-like protocol over TCP
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 44818):
        self.host = host
        self.port = port
        self.simulator: Optional[ControlLogixSimulator] = None
        self.server: Optional[asyncio.Server] = None

    async def start(self):
        """Start the simulator server"""
        # Initialize simulator
        self.simulator = get_simulator("simulator", slot=0)
        await self.simulator.connect()

        logger.info(f"Simulator initialized with {len(self.simulator.tags)} tags")

        # Start TCP server
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )

        addr = self.server.sockets[0].getsockname()
        logger.info(f'PLC Simulator Server running on {addr[0]}:{addr[1]}')
        logger.info(f'Simulating {len(self.simulator.production_lines)} production lines')

        async with self.server:
            await self.server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle client connection"""
        addr = writer.get_extra_info('peername')
        logger.info(f"Client connected from {addr}")

        try:
            while True:
                # Read request (length-prefixed JSON)
                length_bytes = await reader.readexactly(4)
                length = int.from_bytes(length_bytes, 'big')

                if length > 1024 * 1024:  # 1MB max
                    logger.error(f"Request too large: {length} bytes")
                    break

                # Read JSON payload
                data = await reader.readexactly(length)
                request = json.loads(data.decode('utf-8'))

                # Process request
                response = await self.process_request(request)

                # Send response (length-prefixed JSON)
                response_data = json.dumps(response).encode('utf-8')
                response_length = len(response_data).to_bytes(4, 'big')

                writer.write(response_length + response_data)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.info(f"Client {addr} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def process_request(self, request: dict) -> dict:
        """Process a client request"""
        method = request.get('method')
        params = request.get('params', {})

        try:
            if method == 'read':
                # Read one or more tags
                tags = params.get('tags', [])
                if isinstance(tags, str):
                    tags = [tags]

                results = self.simulator.read(*tags)

                # Convert to list if single result
                if not isinstance(results, list):
                    results = [results]

                return {
                    'success': True,
                    'results': [
                        {
                            'tag': r.tag,
                            'value': r.value,
                            'error': r.error
                        }
                        for r in results
                    ]
                }

            elif method == 'write':
                # Write a tag
                tag = params.get('tag')
                value = params.get('value')

                result = self.simulator.write(tag, value)

                return {
                    'success': result.error is None,
                    'tag': result.tag,
                    'value': result.value,
                    'error': result.error
                }

            elif method == 'get_tag_list':
                # Get list of all tags
                tags = self.simulator.get_tag_list()

                return {
                    'success': True,
                    'tags': tags
                }

            elif method == 'get_info':
                # Get PLC info
                return {
                    'success': True,
                    'info': self.simulator.info
                }

            elif method == 'ping':
                # Health check
                return {
                    'success': True,
                    'pong': True,
                    'connected': self.simulator.connected
                }

            else:
                return {
                    'success': False,
                    'error': f"Unknown method: {method}"
                }

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                'success': False,
                'error': str(e)
            }


async def main():
    """Run the simulator server"""
    server = PLCSimulatorServer(host='0.0.0.0', port=44818)
    await server.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
