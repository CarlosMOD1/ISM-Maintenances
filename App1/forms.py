import os
import json
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from App1.models import LogMessage
from App1.models import MaintenanceRecord, MantenimientoChecklist
from App1.models import MaintenanceChecklistRecord
from App1.models import Station
from django.utils import timezone


STATIONS_SPSF = {
    "programacion": {"prefix": "programacion_est_", "total": 4},
    "gps3": {"prefix": "GPS3_est_", "total": 1},
    "burn_in": {"prefix": "Burn-in_est_", "total": 1},
    "cell": {"prefix": "cell_est_", "total": 1},
    "funcional1": {"prefix": "functional_est_", "total": 1},
    "hmi": {"prefix": "HMI_est_", "total": 4},
    "performance": {"prefix": "Performance_est_", "total": 2},
    "power_on": {"prefix": "power-on_est_", "total": 6},
    "som_programacion": {"prefix": "som-programming_est_", "total": 2},
}

STATIONS_MINIWHITE = {
    "MiniWhite-Mañana": {"prefix": "MiniWhite-Mañana_est_", "total": 6},
    "MiniWhite-Tarde": {"prefix": "MiniWhite-Tarde_est_", "total": 6},
}

STATIONS_TAPES = {
    "ATE": {"prefix": "ATE_est_", "total": 6},
}

STATIONS_SNIFFERS = {
    "sniffers": {"prefix": "Sniffer_est_", "total": 5},
    "gps": {"prefix": "GPS_est_", "total": 2},
    "cellular": {"prefix": "GPS_est_", "total": 2},
}

est = list(STATIONS_MINIWHITE.keys()) + list(STATIONS_SPSF.keys()) + list(STATIONS_TAPES.keys())
estaciones =[('', 'Todas')] + [(est, est) for est in list(STATIONS_MINIWHITE.keys()) + list(STATIONS_SPSF.keys()) + list(STATIONS_TAPES.keys())]
class LogMessageForm(forms.ModelForm):
    class Meta:
        model = LogMessage
        fields = ("message","componente",)   # NOTE: the trailing comma is required

class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = ("nombre_tecnico", "nombre_ingeniero", "comentarios", "tipo_mantenimiento", "imagen")  
        widgets = {
            'nombre_tecnico': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_ingeniero': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_mantenimiento': forms.Select(attrs={'class': 'form-control'}),
            'comentarios': forms.Textarea(attrs={'class': 'form-control'}),
        }
        labels = {
            'nombre_tecnico': 'Técnico Responsable',
            'nombre_ingeniero': 'Ingeniero Responsable',
            'comentarios': 'Reemplazos y reparaciones',
            'tipo_mantenimiento': 'Tipo de Mantenimiento',
            'imagen': 'Evidencia fotográfica',
        }

class MaintenanceHistoryForm(forms.Form):
    week_number = forms.IntegerField(
        label="Número de Semana", min_value=1, max_value=52,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control week-number'})
    )
    year = forms.IntegerField(
        label="Año", min_value=2000, max_value=2100,
        required=False, 
        widget=forms.NumberInput(attrs={'class': 'form-control year'})
    )
    familia = forms.ChoiceField(
        label="Familia", choices=MaintenanceRecord.FAMILIA_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control familia'})
    )

    # Construir la lista de nombres base
    BASE_STATION_CHOICES = [('', 'Todas')]
    for d in (STATIONS_SPSF, STATIONS_MINIWHITE, STATIONS_TAPES):
        BASE_STATION_CHOICES += [(k, k) for k in d.keys()]

    station = forms.ChoiceField(
        label="Estación",
        choices=BASE_STATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control estacion'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_date = timezone.now()
        self.fields['week_number'].initial = current_date.isocalendar()[1]
        self.fields['year'].initial = current_date.year

class MantenimientoForm(forms.Form):
    def __init__(self, station_name, *args, **kwargs):
        self.maintenance_record = kwargs.pop('maintenance_record', None)
        super().__init__(*args, **kwargs)

        # Siempre intenta cargar el checklist del JSON
        json_file_path = os.path.join('App1/static/App1/mantenimientos', f"{station_name.split('_')[0]}.json")
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for idx, mantenimiento in enumerate(data.get("mantenimientos", [])):
                    self.fields[f"task_{idx}"] = forms.BooleanField(
                        label=mantenimiento,
                        required=False,
                        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                    )
        except FileNotFoundError:
            self.fields["error"] = forms.CharField(
                initial=f"No se encontró el archivo JSON para la estación: {json_file_path}",
                widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'})
            )

        # Si la estación es MiniWhite, agrega el campo especial
        if station_name.lower().startswith("miniwhite"):
            self.fields["cells_active"] = forms.IntegerField(
                label="Cantidad de celdas que detectan MAC",
                min_value=0,
                max_value=20,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )

    def save_checklist(self):
        """
        Guarda todos los datos del checklist en el modelo MaintenanceChecklistRecord.
        """
        if not self.maintenance_record:
            raise ValueError("Se requiere un registro de mantenimiento para guardar el checklist.")

        for field_name, value in self.cleaned_data.items():
            if field_name.startswith("task_"):  # Procesar todos los elementos del checklist
                checklist_item_label = self.fields[field_name].label
                MaintenanceChecklistRecord.objects.create(
                    maintenance_record=self.maintenance_record,
                    checklist_item=checklist_item_label,
                    is_completed=value  # Guardar el estado (True o False)
                )

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña'}),
        label="Contraseña"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmar Contraseña'}),
        label="Confirmar Contraseña"
    )

    class Meta:
        model = User
        fields = ['username', 'password']
        labels = {
            'username': 'Nombre de Usuario',
        }
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Nombre de Usuario'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Las contraseñas no coinciden.")




