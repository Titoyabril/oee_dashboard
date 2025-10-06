"""
API Views for Audit Logging
Provides endpoints for viewing and analyzing audit logs
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from ..models import PLCWriteAudit, SystemAuditLog, DataIntegrityLog
from .serializers_audit import (
    PLCWriteAuditSerializer,
    SystemAuditLogSerializer,
    DataIntegrityLogSerializer,
    AuditSearchSerializer
)
from .permissions import IsAdminOrReadOnly


class PLCWriteAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for PLC write audit logs
    Provides read-only access to audit trail
    """
    queryset = PLCWriteAudit.objects.all().select_related('user', 'machine', 'approved_by')
    serializer_class = PLCWriteAuditSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['timestamp', 'severity', 'execution_time_ms']
    ordering = ['-timestamp']
    search_fields = ['username', 'tag_address', 'tag_name', 'plc_address']

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filter by machine
        machine_id = self.request.query_params.get('machine_id')
        if machine_id:
            queryset = queryset.filter(machine_id=machine_id)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by severity
        severity_filter = self.request.query_params.get('severity')
        if severity_filter:
            queryset = queryset.filter(severity=severity_filter)

        # Filter by user
        username = self.request.query_params.get('username')
        if username:
            queryset = queryset.filter(username__icontains=username)

        # Filter by PLC address
        plc_address = self.request.query_params.get('plc_address')
        if plc_address:
            queryset = queryset.filter(plc_address__icontains=plc_address)

        # Filter failed operations only
        failed_only = self.request.query_params.get('failed_only', '').lower() == 'true'
        if failed_only:
            queryset = queryset.exclude(status='SUCCESS')

        # Filter production impacting only
        production_only = self.request.query_params.get('production_only', '').lower() == 'true'
        if production_only:
            queryset = queryset.filter(production_impacting=True)

        # Filter safety related only
        safety_only = self.request.query_params.get('safety_only', '').lower() == 'true'
        if safety_only:
            queryset = queryset.filter(safety_related=True)

        return queryset

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get audit log summary statistics
        GET /api/audit/plc-writes/summary/
        """
        # Get time range (default last 24 hours)
        start_time = timezone.now() - timedelta(hours=24)
        end_time = timezone.now()

        start_param = request.query_params.get('start_date')
        end_param = request.query_params.get('end_date')

        if start_param:
            start_time = timezone.datetime.fromisoformat(start_param)
        if end_param:
            end_time = timezone.datetime.fromisoformat(end_param)

        queryset = self.get_queryset().filter(
            timestamp__gte=start_time,
            timestamp__lte=end_time
        )

        summary = {
            'time_range': {
                'start': start_time,
                'end': end_time
            },
            'total_writes': queryset.count(),
            'by_status': dict(
                queryset.values('status').annotate(count=Count('id')).values_list('status', 'count')
            ),
            'by_severity': dict(
                queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count')
            ),
            'by_user': list(
                queryset.values('username').annotate(count=Count('id')).order_by('-count')[:10]
            ),
            'by_plc': list(
                queryset.values('plc_address', 'plc_type').annotate(count=Count('id')).order_by('-count')[:10]
            ),
            'failed_writes': queryset.exclude(status='SUCCESS').count(),
            'production_impacting': queryset.filter(production_impacting=True).count(),
            'safety_related': queryset.filter(safety_related=True).count(),
            'avg_execution_time_ms': queryset.aggregate(
                avg=Count('execution_time_ms')
            )['avg'] or 0,
        }

        return Response(summary)

    @action(detail=False, methods=['get'])
    def recent_failures(self, request):
        """
        Get recent failed write operations
        GET /api/audit/plc-writes/recent-failures/
        """
        limit = int(request.query_params.get('limit', 20))

        failures = self.get_queryset().exclude(
            status='SUCCESS'
        ).order_by('-timestamp')[:limit]

        serializer = self.get_serializer(failures, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def critical_operations(self, request):
        """
        Get critical/safety-related operations
        GET /api/audit/plc-writes/critical-operations/
        """
        limit = int(request.query_params.get('limit', 50))

        critical = self.get_queryset().filter(
            Q(severity='CRITICAL') | Q(safety_related=True)
        ).order_by('-timestamp')[:limit]

        serializer = self.get_serializer(critical, many=True)
        return Response(serializer.data)


class SystemAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for system audit logs
    """
    queryset = SystemAuditLog.objects.all().select_related('user')
    serializer_class = SystemAuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
    search_fields = ['username', 'component', 'action', 'description']

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filter by event type
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by component
        component = self.request.query_params.get('component')
        if component:
            queryset = queryset.filter(component__icontains=component)

        # Filter by success
        success = self.request.query_params.get('success')
        if success is not None:
            queryset = queryset.filter(success=success.lower() == 'true')

        return queryset


class DataIntegrityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for data integrity logs
    """
    queryset = DataIntegrityLog.objects.all().select_related('machine')
    serializer_class = DataIntegrityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['timestamp', 'severity']
    ordering = ['-timestamp']
    search_fields = ['description', 'source']

    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filter by machine
        machine_id = self.request.query_params.get('machine_id')
        if machine_id:
            queryset = queryset.filter(machine_id=machine_id)

        # Filter by issue type
        issue_type = self.request.query_params.get('issue_type')
        if issue_type:
            queryset = queryset.filter(issue_type=issue_type)

        # Filter by auto-corrected
        auto_corrected = self.request.query_params.get('auto_corrected')
        if auto_corrected is not None:
            queryset = queryset.filter(auto_corrected=auto_corrected.lower() == 'true')

        return queryset

    @action(detail=False, methods=['get'])
    def uncorrected(self, request):
        """
        Get integrity issues that were NOT auto-corrected
        GET /api/audit/data-integrity/uncorrected/
        """
        limit = int(request.query_params.get('limit', 50))

        uncorrected = self.get_queryset().filter(
            auto_corrected=False
        ).order_by('-timestamp')[:limit]

        serializer = self.get_serializer(uncorrected, many=True)
        return Response(serializer.data)
