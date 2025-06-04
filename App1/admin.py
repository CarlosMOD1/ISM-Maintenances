from django.contrib import admin
from .models import LogMessage, Station, MaintenanceRecord, MantenimientoChecklist, MaintenanceChecklistRecord

admin.site.register(LogMessage)
admin.site.register(Station)
admin.site.register(MaintenanceRecord)
admin.site.register(MantenimientoChecklist)
admin.site.register(MaintenanceChecklistRecord)
