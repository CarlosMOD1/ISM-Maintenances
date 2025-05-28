from django.db import models
from django.utils import timezone
from django import forms


class LogMessage(models.Model):
    message = models.CharField(max_length=300)
    componente = models.CharField(max_length=300)
    log_date = models.DateTimeField("date logged")

    def __str__(self):
        """Returns a string representation of a message."""
        date = timezone.localtime(self.log_date)
        return f"'{self.message}' logged on {date.strftime('%A, %d %B, %Y at %X')}"
    
class Station(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class MaintenanceRecord(models.Model):
    TIPO_MANTENIMIENTO_CHOICES = [
        ('Correctivo', 'Correctivo'),
        ('Preventivo', 'Preventivo'),
    ]
    FAMILIA_CHOICES = [
        ('TAPES', 'TAPES'),
        ('SPSF', 'SPSF'),
    ]
    APROBADO_CHOICES = [
        ('No aprobado', 'No aprobado'),
        ('Aprobado', 'Aprobado'),
        ('Rechazado', 'Rechazado'),
    ]
    completed = models.BooleanField(default=False) 
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='maintenance_records')
    nombre_tecnico = models.CharField(max_length=100, default=' ')
    nombre_ingeniero = models.CharField(max_length=100, default=' ')
    unidad_de_trabajo = models.CharField(max_length=100, choices=FAMILIA_CHOICES, default='--')
    tipo_mantenimiento = models.CharField(max_length=20, choices=TIPO_MANTENIMIENTO_CHOICES, default='Preventivo')
    comentarios = models.CharField(max_length=300, default=' ', null=True, blank=True)
    log_date = models.DateTimeField("date logged", default=timezone.now)
    week_number = models.PositiveIntegerField(editable=False)
    aprobado = models.CharField(max_length=20, choices=APROBADO_CHOICES, default='No aprobado')
    imagen = models.ImageField(upload_to='mantenimientos/', null=True, blank=True)  # <-- Nuevo campo
    cells_active = models.IntegerField(null=True, blank=True)  

    def save(self, *args, **kwargs):
        self.week_number = self.log_date.isocalendar()[1]
        super().save(*args, **kwargs)

    def __str__(self):
        date = timezone.localtime(self.log_date)
        return f"Maintenance for {self.station.name} on {date.strftime('%A, %d %B, %Y at %X')}"
    
class MantenimientoChecklist(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self):
        return self.name

class MaintenanceChecklistRecord(models.Model):
    maintenance_record = models.ForeignKey(
        MaintenanceRecord, 
        on_delete=models.CASCADE, 
        related_name='checklist_records'
    )
    checklist_item = models.CharField(max_length=300)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.checklist_item} - {'Completed' if self.is_completed else 'Pending'}"

