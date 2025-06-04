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
from datetime import timedelta
from django.core.paginator import Paginator
from App1.forms import STATIONS_MINIWHITE, STATIONS_SPSF, STATIONS_TAPES, STATIONS_SNIFFERS


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
    for base_name, config in {**STATIONS_SPSF, **STATIONS_TAPES, **STATIONS_MINIWHITE, **STATIONS_SNIFFERS}.items():
        if station_name.startswith(config["prefix"]):
            base_station_name = base_name
            break

    # Inicializar los formularios
    form = MaintenanceRecordForm(request.POST or None, request.FILES or None)
    checklist_form = MantenimientoForm(station_name, request.POST or None)

    # Obtener la URL anterior desde el parámetro 'next' o usar '/' como respaldo
    previous_url = request.GET.get('next', request.POST.get('next', '/'))

    # --- VALIDACIÓN DE DUPLICADOS ---
    error_message = None
    edit_mode = request.GET.get('edit') == '1'
    maintenance_record = None

    if edit_mode:
        # Busca el registro más reciente para editar
        if base_station_name in STATIONS_SPSF or base_station_name in STATIONS_TAPES:
            current_week = timezone.now().isocalendar()[1]
            maintenance_record = MaintenanceRecord.objects.filter(
                station=station,
                log_date__week=current_week
            ).order_by('-log_date').first()
        elif base_station_name in STATIONS_MINIWHITE or base_station_name in STATIONS_SNIFFERS:
            today = timezone.now().date()
            maintenance_record = MaintenanceRecord.objects.filter(
                station=station,
                log_date__date=today
            ).order_by('-log_date').first()

    # --- CORRIGE AQUÍ: Usa la instancia en el formulario si es edición ---
    if request.method == "POST":
        # Obtén el tipo de mantenimiento del formulario POST
        tipo_mantenimiento = request.POST.get("tipo_mantenimiento", "Preventivo")

        if edit_mode and maintenance_record:
            form = MaintenanceRecordForm(request.POST, request.FILES, instance=maintenance_record)
            checklist_form = MantenimientoForm(station_name, request.POST, maintenance_record=maintenance_record)
        else:
            form = MaintenanceRecordForm(request.POST, request.FILES)
            checklist_form = MantenimientoForm(station_name, request.POST)

        # Solo aplica la restricción si es preventivo
        if tipo_mantenimiento == "Preventivo":
            # SPSF y ATE: solo uno por semana
            if base_station_name in STATIONS_SPSF or base_station_name in STATIONS_TAPES:
                current_week = timezone.now().isocalendar()[1]
                qs = MaintenanceRecord.objects.filter(
                    station=station,
                    log_date__week=current_week,
                    tipo_mantenimiento="Preventivo"
                )
                if edit_mode and maintenance_record:
                    qs = qs.exclude(pk=maintenance_record.pk)
                exists = qs.exists()
                if exists:
                    error_message = "Ya existe un mantenimiento preventivo registrado para esta estación en la semana actual."
            # MiniWhite y Sniffers: solo uno por día
            elif base_station_name in STATIONS_MINIWHITE or base_station_name in STATIONS_SNIFFERS:
                today = timezone.now().date()
                qs = MaintenanceRecord.objects.filter(
                    station=station,
                    log_date__date=today,
                    tipo_mantenimiento="Preventivo"
                )
                if edit_mode and maintenance_record:
                    qs = qs.exclude(pk=maintenance_record.pk)
                exists = qs.exists()
                if exists:
                    error_message = "Ya existe un mantenimiento preventivo registrado para esta estación en el día de hoy."

        if error_message:
            return render(request, "App1/log_maintenance.html", {
                "form": form,
                "checklist_form": checklist_form,
                "next": previous_url,
                "station_name": station_name,
                "error_message": error_message,
            })

        if form.is_valid() and checklist_form.is_valid():
            maintenance_record = form.save(commit=False)
            maintenance_record.station = station

            # Asignar automáticamente la unidad de trabajo
            if base_station_name in STATIONS_SPSF:
                maintenance_record.unidad_de_trabajo = "SPSF"
            elif base_station_name in STATIONS_TAPES:
                maintenance_record.unidad_de_trabajo = "TAPES"
            elif base_station_name in STATIONS_MINIWHITE:
                maintenance_record.unidad_de_trabajo = "MiniWhite"

            # ← AQUÍ AGREGA EL CÓDIGO PARA MINIWHITE
            if "cells_active" in checklist_form.cleaned_data:
                maintenance_record.cells_active = checklist_form.cleaned_data["cells_active"]

            # Verificar si todos los elementos de la checklist están marcados
            task_fields = [value for field_name, value in checklist_form.cleaned_data.items() if field_name.startswith("task_")]
            all_tasks_completed = all(task_fields)

            # Si es MiniWhite, también requiere que cells_active > 0
            if "cells_active" in checklist_form.cleaned_data:
                maintenance_record.completed = all_tasks_completed and (maintenance_record.cells_active and maintenance_record.cells_active > 0)
            else:
                maintenance_record.completed = all_tasks_completed

            maintenance_record.save()

            # Procesar los datos de la checklist
            checklist_form = MantenimientoForm(station_name, request.POST, maintenance_record=maintenance_record)
            if checklist_form.is_valid():
                checklist_form.save_checklist()

            # Redirigir a la página anterior
            return redirect(previous_url)

    else:
        # GET: muestra el formulario con la instancia si es edición
        if maintenance_record:
            form = MaintenanceRecordForm(instance=maintenance_record)
            checklist_form = MantenimientoForm(station_name, maintenance_record=maintenance_record)
        else:
            form = MaintenanceRecordForm()
            checklist_form = MantenimientoForm(station_name)

    return render(request, "App1/log_maintenance.html", {
        "form": form,
        "checklist_form": checklist_form,
        "next": previous_url,
        "station_name": station_name,
    })


def maintenances_history(request):
    form = MaintenanceHistoryForm(request.GET or None)
    maintenance_records = None
    page_obj = None

    if form.is_valid():
        week_number = form.cleaned_data['week_number']
        year = form.cleaned_data['year']
        familia = form.cleaned_data['familia']
        estacion = form.cleaned_data['station']

        filters = {
            'unidad_de_trabajo': familia
        }
        if week_number:
            filters['log_date__week'] = week_number
        if year:
            filters['log_date__year'] = year

        # Nuevo: filtrar por prefijo si se seleccionó estación base
        if estacion:
            prefix = None
            for d in (STATIONS_SPSF, STATIONS_MINIWHITE, STATIONS_TAPES):
                if estacion in d:
                    prefix = d[estacion]['prefix']
                    break
            if prefix:
                filters['station__name__startswith'] = prefix

        maintenance_records = MaintenanceRecord.objects.filter(
            **filters
        ).exclude(aprobado="Rechazado").prefetch_related('checklist_records').order_by('-log_date')

        # PAGINACIÓN: 30 registros por página
        paginator = Paginator(maintenance_records, 30)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

    return render(request, "App1/maintenances_history.html", {
        "form": form,
        "maintenance_records": page_obj,
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

def user_dashboard(request):
    background_image = None
    if request.user.username == "Jonatan":
        background_image = "/static/images/jonatan_background.jpg"  # Ruta de la imagen específica para Jonatan
    else:
        background_image = "/static/images/default_background.jpg"  # Imagen de fondo predeterminada para otros usuarios

    return render(request, "dashboard.html", {
        "background_image": background_image,
    })

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

    # Lógica para MiniWhite: usa las últimas 16 horas
    time_threshold = timezone.now() - timedelta(hours=16)
    miniwhite_records = MaintenanceRecord.objects.filter(log_date__gte=time_threshold)
    miniwhite_completed = miniwhite_records.values_list('station__name', flat=True)
    has_incomplete_miniwhite = has_incomplete_stations(STATIONS_MINIWHITE, miniwhite_completed)

    # Lógica para Sniffers: usa las últimas 16 horas
    sniffers_records = MaintenanceRecord.objects.filter(log_date__gte=time_threshold)
    sniffers_completed = sniffers_records.values_list('station__name', flat=True)
    has_incomplete_sniffers = has_incomplete_stations(STATIONS_SNIFFERS, sniffers_completed)

    return render(request, 'App1/home.html', {
        "has_incomplete_spsf": has_incomplete_spsf,
        "has_incomplete_tapes": has_incomplete_tapes,
        "has_incomplete_miniwhite": has_incomplete_miniwhite,
        "has_incomplete_sniffers": has_incomplete_sniffers,  # <-- Agrega esta línea
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

def miniwhite_view(request):
    time_threshold = timezone.now() - timedelta(hours=16)
    maintenance_records = MaintenanceRecord.objects.filter(
        log_date__gte=time_threshold
    )
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    all_completed_stations = {}
    for section_name, config in STATIONS_MINIWHITE.items():
        all_completed_stations[section_name] = are_all_status_completed(
            station_prefix=config["prefix"],
            completed_stations=completed_stations,
            total_stations=config["total"]
        )

    return render(request, "App1/MiniWhite.html", {
        "all_completed_stations": all_completed_stations,
    })

def miniwhite_station_view(request, section_name):
    time_threshold = timezone.now() - timedelta(hours=16)
    maintenance_records = MaintenanceRecord.objects.filter(
        log_date__gte=time_threshold
    )
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    return render(request, f"App1/Estaciones_templates/{section_name}.html", {
        "section_name": section_name,
        "completed_stations": completed_stations,
    })

def sniffers_view(request):
    time_threshold = timezone.now() - timedelta(hours=16)
    maintenance_records = MaintenanceRecord.objects.filter(
        log_date__gte=time_threshold
    )
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    all_completed_stations = {}
    for section_name, config in STATIONS_SNIFFERS.items():
        all_completed_stations[section_name] = are_all_status_completed(
            station_prefix=config["prefix"],
            completed_stations=completed_stations,
            total_stations=config["total"]
        )

    return render(request, "App1/sniffers.html", {
        "all_completed_stations": all_completed_stations,
    })

def sniffers_station_view(request, section_name):
    time_threshold = timezone.now() - timedelta(hours=16)
    maintenance_records = MaintenanceRecord.objects.filter(
        log_date__gte=time_threshold
    )
    completed_stations = maintenance_records.values_list('station__name', flat=True)

    return render(request, f"App1/Estaciones_templates/{section_name}.html", {
        "section_name": section_name,
        "completed_stations": completed_stations,
    })
