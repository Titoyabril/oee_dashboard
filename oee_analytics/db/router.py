"""
Database Router for OEE Analytics
Routes time-series data to TimescaleDB and other data to default database
"""


class TimeSeriesRouter:
    """
    Route time-series models to TimescaleDB,
    keep configuration/relational data in default database
    """

    # Models that should use TimescaleDB
    timeseries_models = {
        'sparkplugmetrichistory',
        'sparkplugeventraw',
        'machineevent',
        'productioncycle',
        'downtimeevent',
        'qualityevent',
        'oeerollup hourly',
        'oeerollupshift',
        'oerollupdaily',
    }

    # App label for time-series data
    timeseries_app = 'oee_analytics'

    def db_for_read(self, model, **hints):
        """
        Route reads of time-series models to TimescaleDB
        """
        if model._meta.model_name.lower() in self.timeseries_models:
            return 'timescaledb'
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Route writes of time-series models to TimescaleDB
        """
        if model._meta.model_name.lower() in self.timeseries_models:
            return 'timescaledb'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between models in the same database
        """
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)

        if db1 and db2:
            return db1 == db2
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Ensure time-series models are only migrated to TimescaleDB
        """
        if model_name and model_name.lower() in self.timeseries_models:
            return db == 'timescaledb'

        if app_label == self.timeseries_app:
            # Non-time-series models in oee_analytics app
            if model_name and model_name.lower() not in self.timeseries_models:
                return db == 'default'

        # Other apps use default database
        return db == 'default'


class ReadReplicaRouter:
    """
    Optional: Route read queries to read replicas for load balancing
    """

    def db_for_read(self, model, **hints):
        """
        Read from replica if available
        """
        # Could add logic to select read replicas here
        return None  # Use default routing

    def db_for_write(self, model, **hints):
        """
        All writes go to primary
        """
        return None  # Use default routing

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Migrations only on primary
        """
        return db == 'default' or db == 'timescaledb'
