# Patch Notes for oee_dashboard (auto)

- oee_analytics/routing.py: Import fixed: .consumers -> .consumer
- oee_dashboard/settings.py: Added django_plotly_dash Base & ExternalRedirection middleware
- oee_dashboard/settings.py: Added django_plotly_dash context processor
- oee_dashboard/settings.py: Default USE_IN_MEMORY_CHANNELS to true for dev
- oee_analytics/dash_apps/downtime_timeline.py: Replaced requests.get with ORM query; added safe empty figure.
