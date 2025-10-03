"""
Custom Views for PLC Configuration Management
Provides user-friendly web interface for configuring PLC connections
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
import asyncio
import json

from .models_plc_config import PLCConnection, PLCTag, PLCConnectionTemplate
from .forms_plc_config import PLCConnectionForm, PLCTagFormSet


@login_required
def plc_config_dashboard(request):
    """Main dashboard for PLC configuration"""
    connections = PLCConnection.objects.all().prefetch_related('tags')
    templates = PLCConnectionTemplate.objects.filter(is_active=True)

    # Calculate statistics
    stats = {
        'total_connections': connections.count(),
        'enabled_connections': connections.filter(enabled=True).count(),
        'total_tags': PLCTag.objects.count(),
        'simulator_connections': connections.filter(simulator_mode=True).count(),
    }

    context = {
        'connections': connections,
        'templates': templates,
        'stats': stats,
    }

    return render(request, 'oee_analytics/plc_config_dashboard.html', context)


@login_required
def plc_connection_create(request):
    """Create a new PLC connection"""
    if request.method == 'POST':
        form = PLCConnectionForm(request.POST)
        tag_formset = PLCTagFormSet(request.POST)

        if form.is_valid() and tag_formset.is_valid():
            connection = form.save()

            # Save tags
            tags = tag_formset.save(commit=False)
            for tag in tags:
                tag.connection = connection
                tag.save()

            messages.success(request, f'PLC connection "{connection.name}" created successfully.')
            return redirect('plc_config_dashboard')
    else:
        form = PLCConnectionForm()
        tag_formset = PLCTagFormSet()

    context = {
        'form': form,
        'tag_formset': tag_formset,
        'action': 'Create',
    }

    return render(request, 'oee_analytics/plc_connection_form.html', context)


@login_required
def plc_connection_edit(request, pk):
    """Edit an existing PLC connection"""
    connection = get_object_or_404(PLCConnection, pk=pk)

    if request.method == 'POST':
        form = PLCConnectionForm(request.POST, instance=connection)
        tag_formset = PLCTagFormSet(request.POST, instance=connection)

        if form.is_valid() and tag_formset.is_valid():
            connection = form.save()
            tag_formset.save()

            messages.success(request, f'PLC connection "{connection.name}" updated successfully.')
            return redirect('plc_config_dashboard')
    else:
        form = PLCConnectionForm(instance=connection)
        tag_formset = PLCTagFormSet(instance=connection)

    context = {
        'form': form,
        'tag_formset': tag_formset,
        'connection': connection,
        'action': 'Edit',
    }

    return render(request, 'oee_analytics/plc_connection_form.html', context)


@login_required
def plc_connection_delete(request, pk):
    """Delete a PLC connection"""
    connection = get_object_or_404(PLCConnection, pk=pk)

    if request.method == 'POST':
        name = connection.name
        connection.delete()
        messages.success(request, f'PLC connection "{name}" deleted.')
        return redirect('plc_config_dashboard')

    context = {'connection': connection}
    return render(request, 'oee_analytics/plc_connection_confirm_delete.html', context)


@login_required
@require_http_methods(["POST"])
def plc_connection_test(request, pk):
    """Test a PLC connection (AJAX endpoint)"""
    connection = get_object_or_404(PLCConnection, pk=pk)

    try:
        from oee_analytics.sparkplug.connectors.allen_bradley import (
            AllenBradleyConnector, AllenBradleyConfig
        )

        # Create config
        config = AllenBradleyConfig(
            host=connection.ip_address,
            port=connection.port,
            plc_family=connection.plc_family,
            slot=connection.slot,
            timeout=connection.timeout,
            simulator_mode=connection.simulator_mode
        )

        # Test connection
        connector = AllenBradleyConnector(config)

        async def test():
            try:
                success = await connector.connect()
                if success:
                    # Try to read a tag if any exist
                    if connection.tags.exists():
                        first_tag = connection.tags.first()
                        data_point = await connector.read_single(
                            first_tag.address,
                            first_tag.data_type
                        )
                        await connector.disconnect()

                        return True, f"Connected successfully. Read {first_tag.name} = {data_point.value}"
                    else:
                        await connector.disconnect()
                        return True, "Connected successfully (no tags to read)"
                else:
                    return False, "Connection failed"
            except Exception as e:
                return False, f"Error: {str(e)}"

        # Run async test
        success, message = asyncio.run(test())

        # Update status
        from django.utils import timezone
        connection.connection_status = 'connected' if success else 'error'
        connection.last_connection_test = timezone.now()
        connection.save()

        return JsonResponse({
            'success': success,
            'message': message,
            'status': connection.connection_status,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Test failed: {str(e)}',
            'status': 'error'
        }, status=500)


@login_required
def plc_connection_apply_template(request, pk, template_id):
    """Apply a template to a connection"""
    connection = get_object_or_404(PLCConnection, pk=pk)
    template = get_object_or_404(PLCConnectionTemplate, pk=template_id)

    # Delete existing tags
    connection.tags.all().delete()

    # Apply template
    template.apply_to_connection(connection)

    messages.success(request, f'Template "{template.name}" applied to "{connection.name}".')
    return redirect('plc_connection_edit', pk=pk)


@login_required
def plc_connection_export(request, pk):
    """Export a single connection to JSON"""
    connection = get_object_or_404(PLCConnection, pk=pk)

    config = {
        'plc_connections': [connection.to_json_config()],
        'global_settings': {
            'retry_attempts': 3,
            'retry_delay_ms': 1000,
            'connection_timeout_ms': 5000,
            'health_check_interval_ms': 30000,
            'enable_auto_discovery': False,
            'log_level': 'INFO'
        }
    }

    response = HttpResponse(
        json.dumps(config, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="{connection.name}_config.json"'
    return response


@login_required
def plc_config_export_all(request):
    """Export all connections to JSON"""
    connections = PLCConnection.objects.all()

    config = {
        'plc_connections': [conn.to_json_config() for conn in connections],
        'global_settings': {
            'retry_attempts': 3,
            'retry_delay_ms': 1000,
            'connection_timeout_ms': 5000,
            'health_check_interval_ms': 30000,
            'enable_auto_discovery': False,
            'log_level': 'INFO'
        }
    }

    response = HttpResponse(
        json.dumps(config, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="all_plc_configs.json"'
    return response


@login_required
def plc_config_import(request):
    """Import connections from JSON file"""
    if request.method == 'POST' and request.FILES.get('config_file'):
        try:
            config_file = request.FILES['config_file']
            config_data = json.load(config_file)

            imported_count = 0
            for conn_data in config_data.get('plc_connections', []):
                # Create or update connection
                connection, created = PLCConnection.objects.update_or_create(
                    name=conn_data['name'],
                    defaults={
                        'plc_type': conn_data.get('type', 'ALLEN_BRADLEY'),
                        'plc_family': conn_data.get('family', 'CONTROLLOGIX'),
                        'enabled': conn_data.get('enabled', True),
                        'ip_address': conn_data['connection']['ip_address'],
                        'port': conn_data['connection'].get('port', 44818),
                        'slot': conn_data['connection'].get('slot', 0),
                        'timeout': conn_data['connection'].get('timeout', 5.0),
                        'simulator_mode': conn_data['connection'].get('simulator_mode', False),
                        'polling_interval_ms': conn_data['polling'].get('interval_ms', 1000),
                        'batch_size': conn_data['polling'].get('batch_size', 20),
                        'site_id': conn_data.get('metadata', {}).get('site_id', ''),
                        'area_id': conn_data.get('metadata', {}).get('area_id', ''),
                        'line_id': conn_data.get('metadata', {}).get('line_id', ''),
                        'machine_type': conn_data.get('metadata', {}).get('machine_type', ''),
                        'manufacturer': conn_data.get('metadata', {}).get('manufacturer', ''),
                        'model': conn_data.get('metadata', {}).get('model', ''),
                        'location': conn_data.get('metadata', {}).get('location', ''),
                    }
                )

                # Delete existing tags and create new ones
                connection.tags.all().delete()
                for i, tag_data in enumerate(conn_data.get('tags', [])):
                    PLCTag.objects.create(
                        connection=connection,
                        name=tag_data['name'],
                        address=tag_data['address'],
                        data_type=tag_data['data_type'],
                        description=tag_data.get('description', ''),
                        sparkplug_metric=tag_data.get('sparkplug_metric', ''),
                        units=tag_data.get('units', ''),
                        scale_factor=tag_data.get('scale_factor', 1.0),
                        offset=tag_data.get('offset', 0.0),
                        sort_order=i
                    )

                imported_count += 1

            messages.success(request, f'Successfully imported {imported_count} PLC connections.')
            return redirect('plc_config_dashboard')

        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')

    return render(request, 'oee_analytics/plc_config_import.html')


@login_required
def plc_connection_clone(request, pk):
    """Clone an existing connection"""
    original = get_object_or_404(PLCConnection, pk=pk)

    # Clone the connection
    connection = PLCConnection.objects.create(
        name=f"{original.name} (Copy)",
        description=original.description,
        plc_type=original.plc_type,
        plc_family=original.plc_family,
        enabled=False,  # Start disabled
        ip_address=original.ip_address,
        port=original.port,
        slot=original.slot,
        timeout=original.timeout,
        simulator_mode=original.simulator_mode,
        polling_interval_ms=original.polling_interval_ms,
        batch_size=original.batch_size,
        site_id=original.site_id,
        area_id=original.area_id,
        line_id=original.line_id,
        machine_type=original.machine_type,
        manufacturer=original.manufacturer,
        model=original.model,
        location=original.location,
    )

    # Clone tags
    for tag in original.tags.all():
        PLCTag.objects.create(
            connection=connection,
            name=tag.name,
            address=tag.address,
            data_type=tag.data_type,
            description=tag.description,
            sparkplug_metric=tag.sparkplug_metric,
            units=tag.units,
            scale_factor=tag.scale_factor,
            offset=tag.offset,
            sort_order=tag.sort_order,
        )

    messages.success(request, f'Cloned "{original.name}" to "{connection.name}".')
    return redirect('plc_connection_edit', pk=connection.pk)
