"""
TimescaleDB Database Backend for Django
Extends PostgreSQL backend with TimescaleDB-specific features
"""

from django.db.backends.postgresql import base, features, operations


class DatabaseFeatures(features.DatabaseFeatures):
    """TimescaleDB database features"""
    supports_timescaledb = True
    has_native_duration_field = True
    has_native_uuid_field = True
    supports_partial_indexes = True
    supports_functions_in_partial_indexes = True


class DatabaseOperations(operations.DatabaseOperations):
    """TimescaleDB database operations"""

    def date_trunc_sql(self, lookup_type, field_name):
        """
        Override to use TimescaleDB's time_bucket function for better performance
        """
        if lookup_type in ('year', 'month', 'week', 'day', 'hour', 'minute', 'second'):
            interval_map = {
                'year': '1 year',
                'month': '1 month',
                'week': '1 week',
                'day': '1 day',
                'hour': '1 hour',
                'minute': '1 minute',
                'second': '1 second',
            }
            interval = interval_map.get(lookup_type)
            return f"time_bucket('{interval}', {field_name})"
        return super().date_trunc_sql(lookup_type, field_name)


class DatabaseWrapper(base.DatabaseWrapper):
    """TimescaleDB database wrapper"""
    vendor = 'timescaledb'
    display_name = 'TimescaleDB'

    features_class = DatabaseFeatures
    ops_class = DatabaseOperations

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_new_connection(self, conn_params):
        """Establish a new database connection"""
        connection = super().get_new_connection(conn_params)
        # Ensure timescaledb extension is loaded
        with connection.cursor() as cursor:
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
            if not cursor.fetchone():
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        return connection

    def init_connection_state(self):
        """Initialize connection state"""
        super().init_connection_state()
        # Set application name for connection tracking
        with self.cursor() as cursor:
            cursor.execute("SET application_name = 'django_oee_analytics'")
