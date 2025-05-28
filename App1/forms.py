import os
import json
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from App1.models import LogMessage
from App1.models import MaintenanceRecord, MantenimientoChecklist
from App1.models import MaintenanceChecklistRecord
from django.utils import timezone



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
    week_number = forms.IntegerField(label="Número de Semana", min_value=1, max_value=52,widget=forms.NumberInput(attrs={'class': 'form-control week-number'}))
    year = forms.IntegerField(label="Año", min_value=2000, max_value=2100,widget=forms.NumberInput(attrs={'class': 'form-control year'}))
    familia = forms.ChoiceField(label="Familia", choices=MaintenanceRecord.FAMILIA_CHOICES,widget=forms.Select(attrs={'class': 'form-control familia'}))
    

    def __init__(self, *args, **kwargs):
        super(MaintenanceHistoryForm, self).__init__(*args, **kwargs)
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




