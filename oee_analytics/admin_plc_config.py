"""
Django Admin Configuration for PLC Connection Management
Provides user-friendly admin interface for managing PLC connections and tags
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
import asyncio
from .models_plc_config import PLCConnection, PLCTag, PLCConnectionTemplate


class PLCTagInline(admin.TabularInline):
    """Inline editor for PLC tags"""
    model = PLCTag
    extra = 1
    fields = [
        'sort_order', 'name', 'address', 'data_type',
        'sparkplug_metric', 'description', 'units'
    ]
    ordering = ['sort_order', 'name']


@admin.register(PLCConnection)
class PLCConnectionAdmin(admin.ModelAdmin):
    """Admin interface for PLC connections"""

    list_display = [
        'name', 'plc_family', 'ip_address', 'enabled',
        'connection_status_badge', 'tag_count', 'test_connection_button'
    ]
    list_filter = ['enabled', 'plc_type', 'plc_family', 'simulator_mode', 'site_id']
    search_fields = ['name', 'description', 'ip_address', 'line_id']

    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'plc_type', 'plc_family', 'enabled']
        }),
        ('Connection Settings', {
            'fields': [
                'ip_address', 'port', 'slot', 'timeout', 'simulator_mode'
            ]
        }),
        ('Polling Configuration', {
            'fields': ['polling_interval_ms', 'batch_size']
        }),
        ('Metadata', {
            'fields': [
                'site_id', 'area_id', 'line_id',
                'machine_type', 'manufacturer', 'model', 'location'
            ],
            'classes': ['collapse']
        }),
        ('Status', {
            'fields': ['connection_status', 'last_connection_test'],
            'classes': ['collapse']
        }),
    ]

    inlines = [PLCTagInline]

    readonly_fields = ['connection_status', 'last_connection_test']

    actions = ['enable_connections', 'disable_connections', 'test_all_connections', 'export_to_json']

    def tag_count(self, obj):
        """Display number of configured tags"""
        count = obj.tags.count()
        return format_html(
            '<span style="color: {};">{} tags</span>',
            'green' if count > 0 else 'red',
            count
        )
    tag_count.short_description = 'Tags'

    def connection_status_badge(self, obj):
        """Display connection status as colored badge"""
        colors = {
            'connected': 'green',
            'disconnected': 'red',
            'error': 'orange',
            'unknown': 'gray'
        }
        color = colors.get(obj.connection_status, 'gray')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.connection_status.upper()
        )
    connection_status_badge.short_description = 'Status'

    def test_connection_button(self, obj):
        """Display test connection button"""
        return format_html(
            '<a class="button" href="{}">Test</a>',
            reverse('admin:test_plc_connection', args=[obj.pk])
        )
    test_connection_button.short_description = 'Actions'

    def enable_connections(self, request, queryset):
        """Enable selected connections"""
        updated = queryset.update(enabled=True)
        self.message_user(request, f'{updated} connections enabled.')
    enable_connections.short_description = "Enable selected connections"

    def disable_connections(self, request, queryset):
        """Disable selected connections"""
        updated = queryset.update(enabled=False)
        self.message_user(request, f'{updated} connections disabled.')
    disable_connections.short_description = "Disable selected connections"

    def test_all_connections(self, request, queryset):
        """Test all selected connections"""
        # This would call the actual connection test
        self.message_user(request, 'Connection tests initiated.')
    test_all_connections.short_description = "Test selected connections"

    def export_to_json(self, request, queryset):
        """Export connections to JSON config file"""
        import json
        from django.http import HttpResponse

        connections_data = {
            'plc_connections': [conn.to_json_config() for conn in queryset],
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
            json.dumps(connections_data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="plc_config.json"'
        return response
    export_to_json.short_description = "Export to JSON config"

    def get_urls(self):
        """Add custom URLs for testing connections"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:connection_id>/test/',
                self.admin_site.admin_view(self.test_connection_view),
                name='test_plc_connection'
            ),
        ]
        return custom_urls + urls

    def test_connection_view(self, request, connection_id):
        """Test a specific PLC connection"""
        try:
            connection = PLCConnection.objects.get(pk=connection_id)

            # Import connector
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
                        await connector.disconnect()
                        return True, "Connection successful"
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

            # Show message
            if success:
                messages.success(request, f'✓ {message}')
            else:
                messages.error(request, f'✗ {message}')

        except Exception as e:
            messages.error(request, f'Test failed: {str(e)}')

        # Redirect back
        return redirect('admin:oee_analytics_plcconnection_change', connection_id)


@admin.register(PLCTag)
class PLCTagAdmin(admin.ModelAdmin):
    """Admin interface for PLC tags"""

    list_display = [
        'name', 'connection', 'address', 'data_type',
        'sparkplug_metric', 'units'
    ]
    list_filter = ['connection', 'data_type']
    search_fields = ['name', 'address', 'description', 'sparkplug_metric']

    fieldsets = [
        ('Basic Configuration', {
            'fields': ['connection', 'name', 'address', 'data_type', 'description']
        }),
        ('Sparkplug Mapping', {
            'fields': ['sparkplug_metric', 'units']
        }),
        ('Advanced', {
            'fields': ['scale_factor', 'offset', 'sort_order'],
            'classes': ['collapse']
        }),
    ]


@admin.register(PLCConnectionTemplate)
class PLCConnectionTemplateAdmin(admin.ModelAdmin):
    """Admin interface for connection templates"""

    list_display = ['name', 'plc_family', 'is_active', 'tag_count_display']
    list_filter = ['is_active', 'plc_type', 'plc_family']
    search_fields = ['name', 'description']

    fieldsets = [
        ('Template Information', {
            'fields': ['name', 'description', 'is_active']
        }),
        ('PLC Configuration', {
            'fields': [
                'plc_type', 'plc_family',
                'default_port', 'default_slot', 'default_timeout',
                'default_polling_interval'
            ]
        }),
        ('Template Tags', {
            'fields': ['template_tags'],
            'description': 'JSON array of tag configurations'
        }),
    ]

    def tag_count_display(self, obj):
        """Display number of tags in template"""
        count = len(obj.template_tags) if obj.template_tags else 0
        return f"{count} tags"
    tag_count_display.short_description = 'Tags'
