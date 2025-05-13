import re
from django.utils.timezone import datetime
from django.http import HttpResponse
from django.shortcuts import render
from django.shortcuts import redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from App1.forms import LogMessageForm
from App1.models import LogMessage
from django.views.generic import ListView
from App1.forms import MaintenanceRecordForm, MaintenanceHistoryForm, MantenimientoForm
from App1.models import MaintenanceRecord, Station
from django.utils import timezone
import openpyxl
from django.utils.timezone import now
from django.urls import reverse
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import UserRegistrationForm


# Replace the existing home function with the one below

class HomeListView(LoginRequiredMixin, ListView):
    model = LogMessage
    queryset = LogMessage.objects.order_by("-log_date")[:5]
    context_object_name = "message_list"
    template_name = "App1/home.html"

class MaintenanceListView(ListView):
    model = MaintenanceRecord
    context_object_name = "maintenance_records"
    template_name = "App1/maintenance_list.html"

def log_maintenance(request, station_name):
    """
    Vista para registrar el mantenimiento de una estación específica.
    """
    station, created = Station.objects.get_or_create(name=station_name)

    # Extraer el nombre base de la estación
    base_station_name = None
    for base_name, config in {**STATIONS_SPSF, **STATIONS_TAPES}.items():
        if station_name.startswith(config["prefix"]):
            base_station_name = base_name
            break

    # Inicializar los formularios
    form = MaintenanceRecordForm(request.POST or None)
    checklist_form = MantenimientoForm(station_name, request.POST or None)

    # Obtener la URL anterior desde el parámetro 'next' o usar '/' como respaldo
    previous_url = request.GET.get('next', request.POST.get('next', '/'))

    if request.method == "POST":
        if form.is_valid() and checklist_form.is_valid():
            maintenance_record = form.save(commit=False)
            maintenance_record.station = station

            # Asignar automáticamente la unidad de trabajo
            if base_station_name in STATIONS_SPSF:
                maintenance_record.unidad_de_trabajo = "SPSF"
            elif base_station_name in STATIONS_TAPES:
                maintenance_record.unidad_de_trabajo = "TAPES"

            # Verificar si todos los elementos de la checklist están marcados
            all_tasks_completed = all(
                value for field_name, value in checklist_form.cleaned_data.items() if field_name.startswith("task_")
            )
            maintenance_record.completed = all_tasks_completed  # Actualizar el campo 'completed'

            maintenance_record.save()

            # Procesar los datos de la checklist
            checklist_form = MantenimientoForm(station_name, request.POST, maintenance_record=maintenance_record)
            if checklist_form.is_valid():
                checklist_form.save_checklist()

            # Redirigir a la página anterior
            return redirect(previous_url)

    return render(request, "App1/log_maintenance.html", {
        "form": form,
        "checklist_form": checklist_form,
        "next": previous_url,  # Pasar la URL anterior al contexto
        "station_name": station_name,
    })


def maintenances_history(request):
    form = MaintenanceHistoryForm(request.POST or None)
    maintenance_records = None

    if request.method == "POST" and form.is_valid():
        week_number = form.cleaned_data['week_number']
        year = form.cleaned_data['year']
        familia = form.cleaned_data['familia']
        maintenance_records = MaintenanceRecord.objects.filter(
            log_date__week=week_number,
            log_date__year=year,
            unidad_de_trabajo=familia
        ).exclude(aprobado="Rechazado").prefetch_related('checklist_records')  # Excluir registros rechazados

    return render(request, "App1/maintenances_history.html", {
        "form": form,
        "maintenance_records": maintenance_records,
    })

def download_maintenance_excel(request):
    # Obtener la semana, el año y la familia seleccionados
    week_number = request.GET.get('week_number')
    year = request.GET.get('year')
    familia = request.GET.get('familia')

    # Filtrar los registros de mantenimiento completados en la semana, el año y la familia seleccionados
    maintenance_records = MaintenanceRecord.objects.filter(
        log_date__week=week_number,
        log_date__year=year,
        unidad_de_trabajo=familia
    )

    # Crear el libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mantenimientos de la Semana"

    # Escribir los encabezados
    headers = ['Estación', 'Técnico', 'Ingeniero', 'Unidad de Trabajo', 'Comentarios', 'Tipo mantenimiento', 'Fecha']
    ws.append(headers)

    # Escribir los datos
    for record in maintenance_records:
        ws.append([
            record.station.name,
            record.nombre_tecnico,
            record.nombre_ingeniero,
            record.unidad_de_trabajo,
            record.comentarios,
            record.tipo_mantenimiento,
            record.log_date.strftime('%Y-%m-%d %H:%M:%S')
        ])

    # Crear la respuesta HTTP con el archivo Excel
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="mantenimientos_semana.xlsx"'
    wb.save(response)
    return response

def spsf_view(request):
    """
    Vista para manejar la página principal de SPSF con todas las estaciones.
    """
    # Obtener las estaciones completadas desde las plantillas de las estaciones
    current_week = timezone.now().isocalendar()[1]
    maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    # Diccionario para almacenar el estado de completitud de cada estación
    all_completed_stations = {}

    # Iterar sobre las estaciones definidas en STATIONS
    for station_name, config in STATIONS_SPSF.items():
        all_completed_stations[station_name] = are_all_status_completed(
            station_prefix=config["prefix"],
            completed_stations=completed_stations,
            total_stations=config["total"]
        )

    return render(request, "App1/SPSF.html", {
        "all_completed_stations": all_completed_stations,
    })

def tapes_view(request):
    """
    Vista para manejar la página principal de tapes con todas las estaciones.
    """
    # Obtener las estaciones completadas desde las plantillas de las estaciones
    current_week = timezone.now().isocalendar()[1]
    maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    # Diccionario para almacenar el estado de completitud de cada estación
    all_completed_stations = {}

    # Iterar sobre las estaciones definidas en STATIONS
    for station_name, config in STATIONS_TAPES.items():
        all_completed_stations[station_name] = are_all_status_completed(
            station_prefix=config["prefix"],
            completed_stations=completed_stations,
            total_stations=config["total"]
        )

    return render(request, "App1/tapes.html", {
        "all_completed_stations": all_completed_stations,
    })

def are_all_status_completed(station_prefix, completed_stations, total_stations):
    # Generar los nombres de las estaciones esperadas
    expected_stations = [f"{station_prefix}{i}" for i in range(1, total_stations + 1)]

    # Verificar si todas las estaciones esperadas están en la lista de completadas
    return all(station in completed_stations for station in expected_stations)

def spsf_station_view(request, station_name):
    """
    Vista genérica para manejar estaciones.
    """
    current_week = timezone.now().isocalendar()[1]
    maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    # Renderizar la plantilla correspondiente a la estación
    return render(request, f"App1/Estaciones_templates/{station_name}.html", {
        "station_name": station_name,
        "completed_stations": completed_stations,
    })

def tapes_station_view(request, station_name):
    """
    Vista genérica para manejar estaciones.
    """
    current_week = timezone.now().isocalendar()[1]
    maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    # Renderizar la plantilla correspondiente a la estación
    return render(request, f"App1/Estaciones_templates/{station_name}.html", {
        "station_name": station_name,
        "completed_stations": completed_stations,
    })

def redirect_to_log_maintenance(request, station_name):
    """
    Redirige a la vista log_maintenance con la URL anterior como parámetro.
    """
    previous_url = request.META.get('HTTP_REFERER', '/')
    log_maintenance_url = f"{reverse('log_maintenance', args=[station_name])}?next={previous_url}"
    return redirect(log_maintenance_url)

STATIONS_SPSF = {
    "programacion": {"prefix": "programacion_est_", "total": 8},
    "gps3": {"prefix": "GPS3_est_", "total": 1},
    "burn_in": {"prefix": "Burn-in_est_", "total": 1},
    "cell": {"prefix": "cell_est_", "total": 2},
    "funcional1": {"prefix": "functional_est_", "total": 4},
    "hmi": {"prefix": "HMI_est_", "total": 6},
    "performance": {"prefix": "Performance_est_", "total": 3},
    "power_on": {"prefix": "power-on_est_", "total": 6},
    "som_programacion": {"prefix": "som-programming_est_", "total": 2},
}

STATIONS_TAPES = {
    "ATE": {"prefix": "ATE_est_", "total": 6},
}

class CustomLoginView(LoginView):
    template_name = 'App1/login.html'  # Plantilla para el formulario de login

def has_incomplete_stations(stations_config, completed_stations):
    """
    Verifica si hay estaciones incompletas en un conjunto de estaciones.
    """
    for station_name, config in stations_config.items():
        if not are_all_status_completed(
            station_prefix=config["prefix"],
            completed_stations=completed_stations,
            total_stations=config["total"]
        ):
            return True
    return False

@login_required
def home_view(request):
    # Obtener las estaciones completadas desde las plantillas de las estaciones
    current_week = timezone.now().isocalendar()[1]
    maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    # Verificar si hay estaciones incompletas en SPSF y Tapes
    has_incomplete_spsf = has_incomplete_stations(STATIONS_SPSF, completed_stations)
    has_incomplete_tapes = has_incomplete_stations(STATIONS_TAPES, completed_stations)

    return render(request, 'App1/home.html', {
        "has_incomplete_spsf": has_incomplete_spsf,
        "has_incomplete_tapes": has_incomplete_tapes,
    })

@staff_member_required  # Solo accesible para usuarios administradores
def approve(request):
    if request.method == "POST":
        # Obtener el ID del registro enviado en el formulario
        record_id = request.POST.get("record_id")
        action = request.POST.get("action")  # Obtener la acción (aprobado o rechazado)

        if record_id:
            # Buscar el registro
            record = get_object_or_404(MaintenanceRecord, id=record_id)

            if action == "Aprobado":
                record.aprobado = "Aprobado"
            elif action == "Rechazado":
                record.aprobado = "Rechazado"
            record.save()

    # Listar los registros pendientes de aprobación
    pending_records = MaintenanceRecord.objects.filter(aprobado="No aprobado")

    return render(request, "App1/approve.html", {"pending_records": pending_records})

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_staff = False  # Asegurarse de que no sea staff
            user.is_superuser = False  # Asegurarse de que no sea superusuario
            user.save()
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'App1/register.html', {'form': form})

# def about(request):
#     return render(request, "App1/about.html")

# def contact(request):
#     return render(request, "App1/contact.html")

# def SPSF(request):
#     return render(request, "App1/SPSF.html")

# def tapes(request):
#     return render(request, "App1/tapes.html")

# def power_on(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/power-on.html", {"completed_stations": completed_stations})

# def som_programming(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/som_programming.html", {"completed_stations": completed_stations})

# def programacion(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.filter(tipo_mantenimiento='Preventivo').values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/programacion.html", {"completed_stations": completed_stations})

# def hmi(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/hmi.html", {"completed_stations": completed_stations})

# def cell(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/cell.html", {"completed_stations": completed_stations})

# def funcional1(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/funcional1.html", {"completed_stations": completed_stations})

# def performance(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/performance.html", {"completed_stations": completed_stations})

# def burn_in(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/burn-in.html", {"completed_stations": completed_stations})

# def gps3(request):
#     current_week = timezone.now().isocalendar()[1]
#     maintenance_records = MaintenanceRecord.objects.filter(log_date__week=current_week)
#     completed_stations = maintenance_records.values_list('station__name', flat=True)
#     return render(request, "App1/Estaciones_templates/gps3.html", {"completed_stations": completed_stations})

# def log_message(request):
#     form = LogMessageForm(request.POST or None)

#     if request.method == "POST":
#         if form.is_valid():
#             message = form.save(commit(False)
#             message.log_date = datetime.now()
#             message.save()
#             return redirect("home")
#     else:
#         return render(request, "App1/log_message.html", {"form": form})
