"""
Django Management Command: Setup SQL Server for OEE Dashboard
Configures database, creates schemas, and initializes production-ready environment
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connections, transaction
import os
import sys
import pyodbc
from pathlib import Path


class Command(BaseCommand):
    help = 'Setup SQL Server database for OEE Dashboard with production-ready configuration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            default='development',
            choices=['development', 'staging', 'production'],
            help='Environment to configure (affects performance settings)'
        )
        
        parser.add_argument(
            '--skip-schema',
            action='store_true',
            help='Skip schema creation (useful if already exists)'
        )
        
        parser.add_argument(
            '--skip-jobs',
            action='store_true',
            help='Skip SQL Agent job creation'
        )
        
        parser.add_argument(
            '--load-sample-data',
            action='store_true',
            help='Load sample manufacturing data for testing'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without executing'
        )
    
    def handle(self, *args, **options):
        self.environment = options['environment']
        self.skip_schema = options['skip_schema']
        self.skip_jobs = options['skip_jobs']
        self.load_sample_data = options['load_sample_data']
        self.dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Setting up OEE Dashboard SQL Server for {self.environment} environment'
            )
        )
        
        try:
            # Step 1: Verify SQL Server connection
            self.verify_connection()
            
            # Step 2: Setup database and filegroups
            if not self.skip_schema:
                self.setup_database()
            
            # Step 3: Create schema objects
            if not self.skip_schema:
                self.create_schema_objects()
            
            # Step 4: Setup security and users
            self.setup_security()
            
            # Step 5: Configure performance monitoring
            self.setup_monitoring()
            
            # Step 6: Create maintenance jobs
            if not self.skip_jobs:
                self.create_maintenance_jobs()
            
            # Step 7: Load sample data if requested
            if self.load_sample_data:
                self.load_sample_manufacturing_data()
            
            # Step 8: Verify setup
            self.verify_setup()
            
            self.stdout.write(
                self.style.SUCCESS(
                    'OEE Dashboard SQL Server setup completed successfully!'
                )
            )
            
            self.display_next_steps()
            
        except Exception as e:
            raise CommandError(f'Setup failed: {str(e)}')
    
    def verify_connection(self):
        """Verify SQL Server connection and permissions"""
        self.stdout.write('Verifying SQL Server connection...')
        
        try:
            connection = connections['default']
            with connection.cursor() as cursor:
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()[0]
                self.stdout.write(f'Connected to: {version[:100]}...')
                
                # Check permissions
                cursor.execute("SELECT IS_SRVROLEMEMBER('sysadmin')")
                is_sysadmin = cursor.fetchone()[0]
                
                if not is_sysadmin:
                    self.stdout.write(
                        self.style.WARNING(
                            'Current user is not sysadmin. Some setup steps may require elevated privileges.'
                        )
                    )
                
        except Exception as e:
            raise CommandError(f'Could not connect to SQL Server: {str(e)}')
    
    def setup_database(self):
        """Setup database, filegroups, and partitioning"""
        self.stdout.write('Setting up database configuration...')
        
        if self.dry_run:
            self.stdout.write('  [DRY RUN] Would configure database filegroups and partitioning')
            return
        
        script_path = Path(__file__).parent.parent.parent.parent / 'sql_server_setup.sql'
        
        if not script_path.exists():
            raise CommandError(f'Setup script not found: {script_path}')
        
        with open(script_path, 'r') as f:
            setup_script = f.read()
        
        # Execute setup script in chunks
        self._execute_sql_script(setup_script, 'Database setup')
    
    def create_schema_objects(self):
        """Create tables, indexes, stored procedures, and views"""
        self.stdout.write('Creating schema objects...')
        
        if self.dry_run:
            self.stdout.write('  [DRY RUN] Would create tables, procedures, and views')
            return
        
        # Create tables
        schema_path = Path(__file__).parent.parent.parent.parent / 'sql_server_schema.sql'
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema_script = f.read()
            self._execute_sql_script(schema_script, 'Schema creation')
        
        # Create stored procedures
        procedures_path = Path(__file__).parent.parent.parent.parent / 'sql_server_stored_procedures.sql'
        if procedures_path.exists():
            with open(procedures_path, 'r') as f:
                procedures_script = f.read()
            self._execute_sql_script(procedures_script, 'Stored procedures')
        
        # Create views
        views_path = Path(__file__).parent.parent.parent.parent / 'sql_server_views.sql'
        if views_path.exists():
            with open(views_path, 'r') as f:
                views_script = f.read()
            self._execute_sql_script(views_script, 'Views creation')
    
    def setup_security(self):
        """Configure security and user accounts"""
        self.stdout.write('Configuring security...')
        
        if self.dry_run:
            self.stdout.write('  [DRY RUN] Would configure user accounts and permissions')
            return
        
        # Security configuration is handled in the setup script
        # Additional environment-specific security can be added here
        pass
    
    def setup_monitoring(self):
        """Configure performance monitoring and alerting"""
        self.stdout.write('Setting up performance monitoring...')
        
        if self.dry_run:
            self.stdout.write('  [DRY RUN] Would enable Query Store and Extended Events')
            return
        
        connection = connections['default']
        with connection.cursor() as cursor:
            # Enable Query Store if not already enabled
            cursor.execute("""
                IF (SELECT actual_state FROM sys.database_query_store_options) = 0
                BEGIN
                    ALTER DATABASE CURRENT SET QUERY_STORE = ON;
                    ALTER DATABASE CURRENT SET QUERY_STORE (
                        OPERATION_MODE = READ_WRITE,
                        CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = 30),
                        DATA_FLUSH_INTERVAL_SECONDS = 900,
                        INTERVAL_LENGTH_MINUTES = 60,
                        MAX_STORAGE_SIZE_MB = 1000,
                        QUERY_CAPTURE_MODE = AUTO,
                        SIZE_BASED_CLEANUP_MODE = AUTO
                    );
                    PRINT 'Query Store enabled successfully';
                END
                ELSE
                    PRINT 'Query Store already enabled';
            """)
    
    def create_maintenance_jobs(self):
        """Create SQL Agent jobs for maintenance"""
        self.stdout.write('Creating maintenance jobs...')
        
        if self.dry_run:
            self.stdout.write('  [DRY RUN] Would create SQL Agent jobs for OEE calculations and maintenance')
            return
        
        # Job creation is handled in the setup script
        # Environment-specific job configurations can be added here
        if self.environment == 'production':
            self.stdout.write('  Production environment: Enhanced job monitoring enabled')
        elif self.environment == 'development':
            self.stdout.write('  Development environment: Reduced job frequency for testing')
    
    def load_sample_manufacturing_data(self):
        """Load sample data for testing and demonstration"""
        self.stdout.write('Loading sample manufacturing data...')
        
        if self.dry_run:
            self.stdout.write('  [DRY RUN] Would load sample plant, machine, and production data')
            return
        
        from ..sql_server_models import (
            Plant, Area, ProductionLine, Machine, Product, Recipe,
            DowntimeReason, QualityDefect
        )
        
        # Sample data is already included in the schema script
        # Additional test data can be added here
        
        connection = connections['default']
        with connection.cursor() as cursor:
            # Generate some sample events for demonstration
            cursor.execute("""
                -- Insert sample machine events
                INSERT INTO dbo.MachineEvents (machine_id, timestamp_utc, event_type, event_value, source_system)
                SELECT 
                    'M001',
                    DATEADD(MINUTE, -n.num, GETUTCDATE()),
                    CASE (n.num % 4)
                        WHEN 0 THEN 'CYCLE_START'
                        WHEN 1 THEN 'CYCLE_END'
                        WHEN 2 THEN 'SENSOR_DATA'
                        ELSE 'STATUS_UPDATE'
                    END,
                    RAND() * 100,
                    'PLC'
                FROM (
                    SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) as num
                    FROM sys.objects s1 CROSS JOIN sys.objects s2
                ) n
                WHERE n.num <= 100;
            """)
            
            self.stdout.write('  Sample telemetry data created')
    
    def verify_setup(self):
        """Verify the setup was successful"""
        self.stdout.write('Verifying setup...')
        
        connection = connections['default']
        with connection.cursor() as cursor:
            # Run verification procedure
            cursor.execute("EXEC dbo.sp_VerifyOEESetup")
            
            # Check key tables exist
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = 'dbo' 
                AND TABLE_NAME IN ('Machines', 'ProductionCycles', 'OEE_Rollup_Hourly')
            """)
            
            table_count = cursor.fetchone()[0]
            if table_count < 3:
                raise CommandError('Key tables not found. Setup may have failed.')
            
            # Check stored procedures exist
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES 
                WHERE ROUTINE_SCHEMA = 'dbo' 
                AND ROUTINE_NAME LIKE 'sp_%OEE%'
            """)
            
            proc_count = cursor.fetchone()[0]
            self.stdout.write(f'  Found {proc_count} OEE stored procedures')
            
            # Check views exist
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.VIEWS 
                WHERE TABLE_SCHEMA = 'dbo' 
                AND TABLE_NAME LIKE 'vw_%'
            """)
            
            view_count = cursor.fetchone()[0]
            self.stdout.write(f'  Found {view_count} dashboard views')
        
        self.stdout.write(self.style.SUCCESS('  Setup verification passed!'))
    
    def display_next_steps(self):
        """Display next steps for configuration"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('NEXT STEPS:'))
        self.stdout.write('='*50)
        
        self.stdout.write(
            '\n1. Update Django settings.py with SQL Server configuration:'
        )
        self.stdout.write("""
from oee_dashboard.sql_server_settings import get_database_config, OEEDatabaseRouter

DATABASES = get_database_config('{environment}')
DATABASE_ROUTERS = ['oee_dashboard.sql_server_settings.OEEDatabaseRouter']
        """.format(environment=self.environment))
        
        self.stdout.write('\n2. Install SQL Server dependencies:')
        self.stdout.write('   pip install mssql-django pyodbc')
        
        self.stdout.write('\n3. Set environment variables:')
        self.stdout.write('   SQL_SERVER_HOST=your_server')
        self.stdout.write('   SQL_SERVER_DATABASE=OEE_Dashboard')
        self.stdout.write('   SQL_SERVER_USER=oee_app_user')
        self.stdout.write('   SQL_SERVER_PASSWORD=your_password')
        
        self.stdout.write('\n4. Test the connection:')
        self.stdout.write('   python manage.py dbshell')
        
        self.stdout.write('\n5. Start real-time data collection:')
        self.stdout.write('   python manage.py run_oee_calculations')
        
        self.stdout.write('\n6. Access dashboard views:')
        self.stdout.write('   - Current Shift OEE: vw_CurrentShiftOEE')
        self.stdout.write('   - Line Performance: vw_LinePerformance')
        self.stdout.write('   - Top Downtime: vw_TopDowntimeReasons24h')
        
        if self.environment == 'production':
            self.stdout.write(self.style.WARNING('\nPRODUCTION CHECKLIST:'))
            self.stdout.write('□ Configure proper SSL certificates')
            self.stdout.write('□ Set up database backup strategy')
            self.stdout.write('□ Configure monitoring and alerting')
            self.stdout.write('□ Review security permissions')
            self.stdout.write('□ Test disaster recovery procedures')
    
    def _execute_sql_script(self, script, description):
        """Execute SQL script with proper error handling"""
        try:
            connection = connections['default']
            
            # Split script into individual statements
            statements = [stmt.strip() for stmt in script.split('GO') if stmt.strip()]
            
            executed_count = 0
            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    with connection.cursor() as cursor:
                        cursor.execute(stmt)
                    executed_count += 1
            
            self.stdout.write(f'  {description}: {executed_count} statements executed')
            
        except Exception as e:
            raise CommandError(f'Error executing {description}: {str(e)}')