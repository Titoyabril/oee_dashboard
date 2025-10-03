"""
Django Forms for PLC Configuration
Provides user-friendly forms with dropdowns and validation
"""

from django import forms
from django.forms import inlineformset_factory
from .models_plc_config import PLCConnection, PLCTag


class PLCConnectionForm(forms.ModelForm):
    """Form for creating/editing PLC connections"""

    class Meta:
        model = PLCConnection
        fields = [
            'name', 'description', 'plc_type', 'plc_family', 'enabled',
            'ip_address', 'port', 'slot', 'timeout', 'simulator_mode',
            'polling_interval_ms', 'batch_size',
            'site_id', 'area_id', 'line_id',
            'machine_type', 'manufacturer', 'model', 'location'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., LINE-001-ControlLogix'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description of this PLC connection'
            }),
            'plc_type': forms.Select(attrs={'class': 'form-select'}),
            'plc_family': forms.Select(attrs={'class': 'form-select'}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 192.168.1.10 or plc.example.com'
            }),
            'port': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 65535
            }),
            'slot': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 17
            }),
            'timeout': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 0.1,
                'min': 0.1,
                'max': 60
            }),
            'simulator_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'polling_interval_ms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 100,
                'max': 60000
            }),
            'batch_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100
            }),
            'site_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., SITE-001'
            }),
            'area_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., AREA-A'
            }),
            'line_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., LINE-001'
            }),
            'machine_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Assembly Line'
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Rockwell Automation'
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1756-L73'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Building A - Floor 2'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add help text
        self.fields['port'].help_text = 'Default: 44818 for EtherNet/IP'
        self.fields['slot'].help_text = 'Slot number in rack (usually 0 for CPU)'
        self.fields['timeout'].help_text = 'Connection timeout in seconds'
        self.fields['polling_interval_ms'].help_text = 'How often to poll PLC (milliseconds)'
        self.fields['batch_size'].help_text = 'Number of tags to read per batch'


class PLCTagForm(forms.ModelForm):
    """Form for creating/editing PLC tags"""

    class Meta:
        model = PLCTag
        fields = [
            'name', 'address', 'data_type', 'description',
            'sparkplug_metric', 'units', 'scale_factor', 'offset', 'sort_order'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., ProductionCount'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Program:MainProgram.ProductionCount'
            }),
            'data_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional description'
            }),
            'sparkplug_metric': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., production_count'
            }),
            'units': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., parts, %, seconds'
            }),
            'scale_factor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 0.01,
                'value': 1.0
            }),
            'offset': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 0.01,
                'value': 0.0
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }


# Create formset for managing multiple tags at once
PLCTagFormSet = inlineformset_factory(
    PLCConnection,
    PLCTag,
    form=PLCTagForm,
    extra=3,  # Show 3 empty forms by default
    can_delete=True
)
