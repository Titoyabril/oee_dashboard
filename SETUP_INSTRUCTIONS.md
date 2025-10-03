# PLC Configuration UI Setup Instructions

## Overview
This system provides a comprehensive web-based interface for configuring Allen-Bradley ControlLogix PLC connections with an easy-to-use UI featuring dropdowns, forms, and templates.

## Files Created

### 1. Django Models (`oee_analytics/models_plc_config.py`)
- `PLCConnection`: Stores PLC connection settings
- `PLCTag`: Stores individual tag configurations
- `PLCConnectionTemplate`: Pre-configured templates for common setups

### 2. Django Admin (`oee_analytics/admin_plc_config.py`)
- Admin interface with inline tag editing
- Connection testing from admin
- Bulk actions (enable/disable/test/export)
- Color-coded status badges

### 3. Custom Views (`oee_analytics/views_plc_config.py`)
- Dashboard view
- Create/Edit/Delete connections
- Test connections (AJAX)
- Import/Export JSON configurations
- Clone connections
- Apply templates

### 4. Forms (`oee_analytics/forms_plc_config.py`)
- `PLCConnectionForm`: Bootstrap-styled form with validation
- `PLCTagForm`: Tag configuration form
- `PLCTagFormSet`: Inline formset for managing multiple tags

### 5. HTML Templates
- `plc_config_dashboard.html`: Main dashboard with statistics and cards
- `plc_connection_form.html`: Create/edit form with sections
- `plc_connection_confirm_delete.html`: Delete confirmation
- `plc_config_import.html`: Import configuration file

### 6. URLs (`oee_analytics/urls_plc_config.py`)
- Routes for all PLC config operations

## Installation Steps

### Step 1: Update Django Settings
Add to `oee_analytics/models.py`:
```python
# Import PLC configuration models
from .models_plc_config import PLCConnection, PLCTag, PLCConnectionTemplate
```

### Step 2: Register Admin
Add to `oee_analytics/admin.py`:
```python
from .admin_plc_config import *
```

### Step 3: Add URLs
Update `oee_dashboard/urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    path('plc-config/', include('oee_analytics.urls_plc_config')),
    path('admin/', admin.site.urls),
]
```

### Step 4: Create Database Migrations
```bash
py manage.py makemigrations oee_analytics
py manage.py migrate
```

### Step 5: Create Superuser (if not already created)
```bash
py manage.py createsuperuser
```

### Step 6: Load Initial Templates (Optional)
Create a data fixture or add via Django shell:
```python
from oee_analytics.models_plc_config import PLCConnectionTemplate

template = PLCConnectionTemplate.objects.create(
    name="Standard Assembly Line",
    description="Standard OEE tracking for assembly lines",
    plc_type="ALLEN_BRADLEY",
    plc_family="CONTROLLOGIX",
    default_port=44818,
    default_slot=0,
    default_timeout=5.0,
    default_polling_interval=1000,
    template_tags=[
        {
            "name": "ProductionCount",
            "address": "Program:MainProgram.ProductionCount",
            "data_type": "DINT",
            "description": "Total production count",
            "sparkplug_metric": "production_count"
        },
        {
            "name": "OEE",
            "address": "Program:MainProgram.OEE",
            "data_type": "REAL",
            "description": "Overall Equipment Effectiveness",
            "sparkplug_metric": "oee",
            "units": "%"
        },
        # Add more tags...
    ]
)
```

## Usage

### Access Points

1. **Custom Web UI**: `http://localhost:8000/plc-config/`
   - Modern dashboard with statistics
   - Card-based interface for each connection
   - Test connections with one click
   - Import/Export JSON configurations

2. **Django Admin**: `http://localhost:8000/admin/oee_analytics/plcconnection/`
   - Full admin interface with inline tag editing
   - Bulk actions
   - Advanced filtering and search

### Creating a New PLC Connection

#### Via Web UI:
1. Navigate to `http://localhost:8000/plc-config/`
2. Click "New Connection"
3. Fill in the form sections:
   - **Basic Information**: Name, type, family
   - **Connection Settings**: IP address, port, slot, timeout
   - **Polling Configuration**: Interval, batch size
   - **Metadata**: Site, area, line information
   - **Tags**: Add multiple tags with addresses

4. Click "Save Connection"

#### Via Django Admin:
1. Navigate to Django admin
2. Go to "PLC Connections"
3. Click "Add PLC Connection"
4. Fill in fields and add tags inline
5. Save

### Testing Connections

**Web UI:**
- Click the lightning bolt icon on any connection card
- Status updates automatically

**Django Admin:**
- Click "Test" button next to connection
- Or select connections and choose "Test selected connections" action

### Import/Export

**Export Single Connection:**
- Click download icon on connection card
- Or use "Export" button in admin

**Export All Connections:**
- Click "Export All" on dashboard
- Or use admin action "Export to JSON config"

**Import Configuration:**
- Click "Import" on dashboard
- Select JSON file
- Existing connections with same name will be updated
- New connections will be created

### Connection Dropdowns

The UI features dropdown selections for:
- **PLC Type**: Allen-Bradley, Siemens S7, Modbus TCP, OPC UA
- **PLC Family**: ControlLogix, CompactLogix, MicroLogix, Micro800, SLC-500, PLC-5
- **Tag Data Types**: BOOL, INT, DINT, REAL, STRING, etc.

## Features

### Dashboard
- **Statistics Cards**: Total connections, enabled connections, total tags, simulators
- **Connection Cards**: Visual cards showing connection status
- **Quick Actions**: Edit, Test, Clone, Export, Delete
- **Bulk Operations**: Import multiple connections

### Connection Form
- **Sectioned Layout**: Organized into logical sections
- **Validation**: Client and server-side validation
- **Help Text**: Contextual help for each field
- **Tag Management**: Add/edit/delete multiple tags inline

### Testing
- **AJAX Testing**: Test connections without page reload
- **Status Display**: Color-coded status badges (Connected/Error/Unknown)
- **Tag Reading**: Tests actually read a tag value if configured

### Templates
- **Pre-configured Setups**: Create templates for common configurations
- **Quick Application**: Apply template to connection with one click
- **Tag Presets**: Templates include standard tag configurations

## Configuration Options

### PLC Connection Settings
- **Name**: Unique identifier
- **PLC Type**: Type of PLC (Allen-Bradley, Siemens, etc.)
- **PLC Family**: Specific family (ControlLogix, CompactLogix, etc.)
- **IP Address**: Hostname or IP
- **Port**: Communication port (default 44818)
- **Slot**: Rack slot number (0-17)
- **Timeout**: Connection timeout in seconds
- **Simulator Mode**: Use simulator instead of real hardware
- **Polling Interval**: How often to poll (milliseconds)
- **Batch Size**: Tags per batch read

### Tag Configuration
- **Name**: Friendly name
- **Address**: PLC tag address
- **Data Type**: BOOL, INT, DINT, REAL, STRING, etc.
- **Description**: What the tag represents
- **Sparkplug Metric**: MQTT Sparkplug B metric name
- **Units**: Engineering units (%, parts, seconds)
- **Scale Factor**: Multiply value
- **Offset**: Add to value

### Metadata
- **Site ID**: Site identifier
- **Area ID**: Area within site
- **Line ID**: Production line
- **Machine Type**: Type of equipment
- **Manufacturer**: PLC manufacturer
- **Model**: PLC model number
- **Location**: Physical location

## API Integration

The configurations are automatically available via:

```python
from oee_analytics.models_plc_config import PLCConnection

# Get all enabled connections
connections = PLCConnection.objects.filter(enabled=True)

# Create connector from configuration
for conn in connections:
    from oee_analytics.sparkplug.connectors.allen_bradley import AllenBradleyConnector, AllenBradleyConfig

    config = AllenBradleyConfig(
        host=conn.ip_address,
        port=conn.port,
        plc_family=conn.plc_family,
        slot=conn.slot,
        timeout=conn.timeout,
        simulator_mode=conn.simulator_mode
    )

    connector = AllenBradleyConnector(config)
    # Use connector...
```

## Troubleshooting

### Migrations Not Working
```bash
py manage.py makemigrations oee_analytics --name plc_config_models
py manage.py migrate oee_analytics
```

### Templates Not Loading
- Ensure `oee_analytics/templates/oee_analytics/` directory exists
- Check `TEMPLATES` setting in settings.py includes app directories

### Admin Not Showing
- Verify admin is registered in `admin.py`
- Clear browser cache
- Check Django admin is accessible at `/admin/`

### Connection Test Fails
- Verify PLC simulator is running (for simulator mode)
- Check IP address and port are correct
- Ensure firewall allows connections
- Check PLC is powered on and network reachable

## Next Steps

1. **Add More Templates**: Create templates for different machine types
2. **Bulk Import**: Import existing configurations from JSON
3. **Live Monitoring**: Add real-time status updates using WebSockets
4. **Tag Discovery**: Implement auto-discovery of tags from PLC
5. **Validation Rules**: Add custom validation for addresses
6. **User Permissions**: Add role-based access control

## Security Considerations

- Use HTTPS in production
- Implement proper authentication
- Validate all user inputs
- Sanitize file uploads
- Use environment variables for sensitive data
- Implement rate limiting for connection tests

## Support

For issues or questions:
1. Check Django logs: `py manage.py runserver --verbosity 3`
2. Review browser console for JavaScript errors
3. Test connection from command line
4. Verify database migrations are current
