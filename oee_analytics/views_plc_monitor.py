"""
Real-time PLC Monitoring Views
Provides live data streaming from all PLC simulators
"""
import asyncio
import json
import time
from datetime import datetime
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from asyncua import Client


async def read_allen_bradley_data(line_num: int, port: int):
    """Read data from Allen-Bradley PLC simulator"""
    line_id = f"LINE-{line_num:03d}"
    prefix = f"Line_{line_id.replace('-', '_')}"

    try:
        reader, writer = await asyncio.open_connection('localhost', port)

        req = {
            'method': 'read',
            'params': {
                'tags': [
                    f'{prefix}_ProductionCount',
                    f'{prefix}_TargetCount',
                    f'{prefix}_GoodCount',
                    f'{prefix}_RejectCount',
                    f'{prefix}_Running',
                    f'{prefix}_Faulted',
                    f'{prefix}_OEE',
                    f'{prefix}_Availability',
                    f'{prefix}_Performance',
                    f'{prefix}_Quality',
                    f'{prefix}_CycleTime',
                    f'{prefix}_DowntimeMinutes',
                    f'{prefix}_LastFaultCode',
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
                'type': 'Allen-Bradley ControlLogix',
                'line': line_id,
                'port': port,
                'status': 'online',
                'data': {
                    'production_count': r[0]['value'],
                    'target_count': r[1]['value'],
                    'good_count': r[2]['value'],
                    'reject_count': r[3]['value'],
                    'running': r[4]['value'],
                    'faulted': r[5]['value'],
                    'oee': round(r[6]['value'], 1),
                    'availability': round(r[7]['value'], 1),
                    'performance': round(r[8]['value'], 1),
                    'quality': round(r[9]['value'], 1),
                    'cycle_time': round(r[10]['value'], 2),
                    'downtime_minutes': round(r[11]['value'], 2),
                    'last_fault_code': r[12]['value'],
                }
            }
    except Exception as e:
        return {
            'type': 'Allen-Bradley ControlLogix',
            'line': line_id,
            'port': port,
            'status': 'offline',
            'error': str(e)
        }


async def read_siemens_opcua_data(line_id: str, port: int):
    """Read data from Siemens S7 OPC UA simulator"""
    try:
        endpoint = f"opc.tcp://localhost:{port}/freeopcua/server/"
        client = Client(url=endpoint)
        await client.connect()

        ns = 2
        data = {
            'production_count': await client.get_node(f"ns={ns};i=4").read_value(),
            'target_count': await client.get_node(f"ns={ns};i=5").read_value(),
            'good_count': await client.get_node(f"ns={ns};i=6").read_value(),
            'reject_count': await client.get_node(f"ns={ns};i=7").read_value(),
            'running': await client.get_node(f"ns={ns};i=8").read_value(),
            'faulted': await client.get_node(f"ns={ns};i=9").read_value(),
            'oee': round(await client.get_node(f"ns={ns};i=11").read_value(), 1),
            'availability': round(await client.get_node(f"ns={ns};i=12").read_value(), 1),
            'performance': round(await client.get_node(f"ns={ns};i=13").read_value(), 1),
            'quality': round(await client.get_node(f"ns={ns};i=14").read_value(), 1),
            'cycle_time': round(await client.get_node(f"ns={ns};i=15").read_value(), 2),
            'downtime_minutes': round(await client.get_node(f"ns={ns};i=17").read_value(), 2),
            'last_fault_code': await client.get_node(f"ns={ns};i=18").read_value(),
        }

        await client.disconnect()

        return {
            'type': 'Siemens S7-1500 (OPC UA)',
            'line': line_id,
            'port': port,
            'status': 'online',
            'data': data
        }
    except Exception as e:
        return {
            'type': 'Siemens S7-1500 (OPC UA)',
            'line': line_id,
            'port': port,
            'status': 'offline',
            'error': str(e)
        }


async def collect_all_plc_data():
    """Collect data from all 12 PLC simulators"""
    # Allen-Bradley ControlLogix PLCs (10)
    ab_configs = [
        (1, 44818), (2, 44819), (3, 44820), (4, 44821), (5, 44822),
        (6, 44823), (7, 44824), (8, 44825), (9, 44826), (10, 44827)
    ]

    # Siemens S7-1500 PLCs (2)
    siemens_configs = [
        ("SIEMENS-001", 4841),
        ("SIEMENS-002", 4842)
    ]

    # Collect all data concurrently
    ab_tasks = [read_allen_bradley_data(line, port) for line, port in ab_configs]
    siemens_tasks = [read_siemens_opcua_data(line, port) for line, port in siemens_configs]

    all_results = await asyncio.gather(*ab_tasks, *siemens_tasks)

    return {
        'timestamp': datetime.now().isoformat(),
        'plcs': all_results,
        'summary': {
            'total': len(all_results),
            'online': sum(1 for r in all_results if r['status'] == 'online'),
            'offline': sum(1 for r in all_results if r['status'] == 'offline'),
        }
    }


def plc_monitor_dashboard(request):
    """Render the PLC monitoring dashboard"""
    return render(request, 'oee_analytics/plc_monitor_dashboard.html')


@require_http_methods(["GET"])
def plc_data_api(request):
    """API endpoint to get current PLC data (JSON)"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        data = loop.run_until_complete(collect_all_plc_data())
        loop.close()
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def plc_stream(request):
    """Server-Sent Events stream for real-time PLC data"""
    def event_stream():
        """Generator for SSE events"""
        while True:
            try:
                # Collect data
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                data = loop.run_until_complete(collect_all_plc_data())
                loop.close()

                # Send as SSE event
                yield f"data: {json.dumps(data)}\n\n"

                # Wait 2 seconds before next update
                time.sleep(2)

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(5)

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
