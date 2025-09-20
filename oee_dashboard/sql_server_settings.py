"""
OEE Dashboard - SQL Server Configuration
Production-Ready Database Settings for Manufacturing Analytics
High-Performance Configuration for Real-Time OEE Data Processing
"""

import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================
# SQL SERVER DATABASE CONFIGURATION
# =============================================

# SQL Server connection settings
SQL_SERVER_CONFIG = {
    'default': {
        'ENGINE': 'mssql',  # mssql-django engine
        'NAME': os.environ.get('SQL_SERVER_DATABASE', 'OEE_Dashboard'),
        'USER': os.environ.get('SQL_SERVER_USER', 'oee_app_user'),
        'PASSWORD': os.environ.get('SQL_SERVER_PASSWORD', ''),
        'HOST': os.environ.get('SQL_SERVER_HOST', 'localhost'),
        'PORT': os.environ.get('SQL_SERVER_PORT', '1433'),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'extra_params': (
                'TrustServerCertificate=yes;'  # For development
                'Encrypt=yes;'
                'Connection Timeout=30;'
                'Command Timeout=60;'
                'MARS_Connection=yes;'  # Multiple Active Result Sets
                'ApplicationIntent=ReadWrite;'
            ),
        },
        # Connection pooling for high performance
        'CONN_MAX_AGE': 300,  # 5 minutes
    },
    
    # Read replica for dashboard queries (optional)
    'readonly': {
        'ENGINE': 'mssql',
        'NAME': os.environ.get('SQL_SERVER_DATABASE', 'OEE_Dashboard'),
        'USER': os.environ.get('SQL_SERVER_READONLY_USER', 'oee_readonly_user'),
        'PASSWORD': os.environ.get('SQL_SERVER_READONLY_PASSWORD', ''),
        'HOST': os.environ.get('SQL_SERVER_READONLY_HOST', 'localhost'),
        'PORT': os.environ.get('SQL_SERVER_PORT', '1433'),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'extra_params': (
                'TrustServerCertificate=yes;'
                'Encrypt=yes;'
                'Connection Timeout=30;'
                'Command Timeout=60;'
                'MARS_Connection=yes;'
                'ApplicationIntent=ReadOnly;'  # Force read-only
            ),
        },
        'CONN_MAX_AGE': 600,  # 10 minutes for read queries
    }
}

# =============================================
# DATABASE ROUTER FOR READ/WRITE SPLITTING
# =============================================

class OEEDatabaseRouter:
    """
    Database router for OEE dashboard
    Routes reads to readonly replica if available
    Routes writes to primary database
    """
    
    read_db = 'readonly'
    write_db = 'default'
    
    # Models that should always use primary database
    write_only_models = {
        'machinevent',
        'productioncycle', 
        'downtimeevent',
        'qualityevent',
        'configurationaudit',
        'queryperformancelog'
    }
    
    # Models that can use read replica
    read_models = {
        'oeerollup',
        'plant',
        'area',
        'productionline',
        'machine',
        'product',
        'recipe',
        'downtimereason',
        'qualitydefect'
    }
    
    def db_for_read(self, model, **hints):
        """Suggest database for reads"""
        model_name = model._meta.model_name.lower()
        
        # Time-series rollups can use read replica
        if any(read_model in model_name for read_model in self.read_models):
            return self.read_db
        
        # Real-time data should use primary for consistency
        if any(write_model in model_name for write_model in self.write_only_models):
            return self.write_db
            
        return self.read_db
    
    def db_for_write(self, model, **hints):
        """Suggest database for writes"""
        return self.write_db
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations within same database"""
        db_set = {'default', 'readonly'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure migrations only run on primary database"""
        if app_label == 'oee_analytics':
            return db == 'default'
        return db == 'default'


# =============================================
# PERFORMANCE OPTIMIZATION SETTINGS
# =============================================

# Query optimization settings
OEE_QUERY_SETTINGS = {
    # Enable query result caching
    'ENABLE_QUERY_CACHE': True,
    'QUERY_CACHE_TIMEOUT': 300,  # 5 minutes
    
    # Batch size for bulk operations
    'BULK_INSERT_BATCH_SIZE': 1000,
    'BULK_UPDATE_BATCH_SIZE': 500,
    
    # Pagination settings for large datasets
    'DEFAULT_PAGE_SIZE': 100,
    'MAX_PAGE_SIZE': 1000,
    
    # Connection pool settings
    'CONNECTION_POOL_SIZE': 20,
    'CONNECTION_MAX_OVERFLOW': 10,
    
    # Query timeout settings
    'SLOW_QUERY_THRESHOLD_MS': 1000,
    'DASHBOARD_QUERY_TIMEOUT_MS': 5000,
    'REPORT_QUERY_TIMEOUT_MS': 30000,
}

# =============================================
# MONITORING AND LOGGING
# =============================================

OEE_MONITORING = {
    # Performance monitoring
    'LOG_SLOW_QUERIES': True,
    'LOG_QUERY_PERFORMANCE': True,
    'ENABLE_QUERY_METRICS': True,
    
    # Health check settings
    'DATABASE_HEALTH_CHECK_INTERVAL': 60,  # seconds
    'CONNECTION_HEALTH_CHECK': True,
    
    # Alerting thresholds
    'ALERT_SLOW_QUERY_MS': 2000,
    'ALERT_CONNECTION_FAILURES': 5,
    'ALERT_DISK_USAGE_PERCENT': 85,
}

# =============================================
# DATA RETENTION CONFIGURATION
# =============================================

OEE_DATA_RETENTION = {
    # High-frequency data retention (days)
    'MACHINE_EVENTS_RETENTION_DAYS': 90,
    'PRODUCTION_CYCLES_RETENTION_DAYS': 1095,  # 3 years
    'DOWNTIME_EVENTS_RETENTION_DAYS': 1095,
    'QUALITY_EVENTS_RETENTION_DAYS': 1095,
    
    # Aggregated data retention (days)
    'HOURLY_ROLLUPS_RETENTION_DAYS': 365,  # 1 year
    'SHIFT_ROLLUPS_RETENTION_DAYS': 1095,  # 3 years
    'DAILY_ROLLUPS_RETENTION_DAYS': 2190,  # 6 years
    
    # Archive settings
    'ENABLE_DATA_ARCHIVAL': True,
    'ARCHIVE_TO_BLOB_STORAGE': False,
    'COMPRESSION_ENABLED': True,
    
    # Cleanup schedule
    'CLEANUP_SCHEDULE_HOUR': 2,  # 2 AM
    'CLEANUP_BATCH_SIZE': 10000,
}

# =============================================
# SECURITY CONFIGURATION
# =============================================

OEE_SECURITY = {
    # Database encryption
    'ENCRYPT_CONNECTION': True,
    'TRUST_SERVER_CERTIFICATE': True,  # Set to False in production with proper certs
    
    # Access control
    'ENABLE_ROW_LEVEL_SECURITY': True,
    'AUDIT_DATA_ACCESS': True,
    'MASK_SENSITIVE_DATA': True,
    
    # Connection security
    'MIN_TLS_VERSION': '1.2',
    'REQUIRE_SECURE_CONNECTION': True,
    
    # SQL injection protection
    'ENABLE_PARAMETERIZED_QUERIES': True,
    'VALIDATE_INPUT_PARAMETERS': True,
}

# =============================================
# REAL-TIME DATA PROCESSING
# =============================================

OEE_REALTIME = {
    # Data ingestion settings
    'MAX_EVENTS_PER_BATCH': 1000,
    'BATCH_PROCESSING_INTERVAL_MS': 1000,
    'ENABLE_ASYNC_PROCESSING': True,
    
    # Real-time calculation intervals
    'OEE_CALCULATION_INTERVAL_SECONDS': 30,
    'ROLLUP_CALCULATION_INTERVAL_MINUTES': 5,
    'DASHBOARD_REFRESH_INTERVAL_SECONDS': 15,
    
    # Event streaming
    'ENABLE_EVENT_STREAMING': True,
    'STREAM_BUFFER_SIZE': 10000,
    'STREAM_FLUSH_INTERVAL_MS': 500,
    
    # Alert thresholds
    'LOW_OEE_THRESHOLD': 60.0,
    'CRITICAL_OEE_THRESHOLD': 40.0,
    'HIGH_DOWNTIME_THRESHOLD_MINUTES': 30,
}

# =============================================
# DASHBOARD PERFORMANCE SETTINGS
# =============================================

OEE_DASHBOARD = {
    # Response time targets (milliseconds)
    'TARGET_RESPONSE_TIME_MS': 200,
    'MAX_RESPONSE_TIME_MS': 1000,
    
    # Caching strategy
    'ENABLE_DASHBOARD_CACHE': True,
    'CACHE_REFRESH_INTERVAL_SECONDS': 30,
    'CACHE_WARM_UP_ON_STARTUP': True,
    
    # Data freshness
    'REAL_TIME_DATA_MAX_AGE_SECONDS': 60,
    'STALE_DATA_WARNING_SECONDS': 300,
    'OFFLINE_DATA_THRESHOLD_SECONDS': 600,
    
    # Aggregation levels
    'DEFAULT_TIME_RANGE_HOURS': 8,  # Current shift
    'MAX_TIME_RANGE_DAYS': 30,
    'TREND_ANALYSIS_PERIODS': ['hourly', 'shift', 'daily'],
}

# =============================================
# INTEGRATION SETTINGS
# =============================================

OEE_INTEGRATIONS = {
    # PLC/SCADA integration
    'PLC_DATA_SOURCE_TIMEOUT_SECONDS': 10,
    'SCADA_POLLING_INTERVAL_SECONDS': 5,
    'MES_SYNC_INTERVAL_MINUTES': 15,
    
    # External systems
    'ERP_INTEGRATION_ENABLED': False,
    'CMMS_INTEGRATION_ENABLED': False,
    'HISTORIAN_INTEGRATION_ENABLED': False,
    
    # Data validation
    'VALIDATE_INCOMING_DATA': True,
    'REJECT_FUTURE_TIMESTAMPS': True,
    'REJECT_NEGATIVE_VALUES': True,
    'MAX_CYCLE_TIME_SECONDS': 3600,  # 1 hour max cycle time
}

# =============================================
# ENVIRONMENT-SPECIFIC CONFIGURATIONS
# =============================================

def get_database_config(environment='development'):
    """Get database configuration for specific environment"""
    
    if environment == 'production':
        return {
            **SQL_SERVER_CONFIG,
            'default': {
                **SQL_SERVER_CONFIG['default'],
                'OPTIONS': {
                    **SQL_SERVER_CONFIG['default']['OPTIONS'],
                    'extra_params': (
                        'TrustServerCertificate=no;'  # Require valid certificates
                        'Encrypt=yes;'
                        'Connection Timeout=30;'
                        'Command Timeout=60;'
                        'MARS_Connection=yes;'
                        'ApplicationIntent=ReadWrite;'
                        'MultipleActiveResultSets=true;'
                        'Pooling=true;'
                        'Max Pool Size=100;'
                        'Min Pool Size=10;'
                    ),
                },
                'CONN_MAX_AGE': 600,  # 10 minutes for production
            }
        }
    
    elif environment == 'staging':
        return {
            **SQL_SERVER_CONFIG,
            'default': {
                **SQL_SERVER_CONFIG['default'],
                'NAME': 'OEE_Dashboard_Staging',
                'CONN_MAX_AGE': 300,
            }
        }
    
    elif environment == 'test':
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        }
    
    else:  # development
        return SQL_SERVER_CONFIG


def get_performance_config(environment='development'):
    """Get performance configuration for specific environment"""
    
    base_config = OEE_QUERY_SETTINGS.copy()
    
    if environment == 'production':
        base_config.update({
            'CONNECTION_POOL_SIZE': 50,
            'CONNECTION_MAX_OVERFLOW': 20,
            'BULK_INSERT_BATCH_SIZE': 2000,
            'DEFAULT_PAGE_SIZE': 50,
            'DASHBOARD_QUERY_TIMEOUT_MS': 3000,
        })
    
    elif environment == 'development':
        base_config.update({
            'CONNECTION_POOL_SIZE': 5,
            'CONNECTION_MAX_OVERFLOW': 2,
            'BULK_INSERT_BATCH_SIZE': 100,
            'DASHBOARD_QUERY_TIMEOUT_MS': 10000,  # More lenient for debugging
        })
    
    return base_config


# =============================================
# EXAMPLE SETTINGS INTEGRATION
# =============================================

"""
To integrate with Django settings.py, add:

from .sql_server_settings import (
    get_database_config, 
    get_performance_config,
    OEEDatabaseRouter,
    OEE_REALTIME,
    OEE_DASHBOARD
)

ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

# Database configuration
DATABASES = get_database_config(ENVIRONMENT)
DATABASE_ROUTERS = ['oee_dashboard.sql_server_settings.OEEDatabaseRouter']

# OEE-specific settings
OEE_QUERY_SETTINGS = get_performance_config(ENVIRONMENT)
OEE_REALTIME_CONFIG = OEE_REALTIME
OEE_DASHBOARD_CONFIG = OEE_DASHBOARD

# Cache configuration for dashboard
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': OEE_DASHBOARD['CACHE_REFRESH_INTERVAL_SECONDS'],
    }
}
"""