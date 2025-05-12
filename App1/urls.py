from django.urls import path
from App1 import views
from App1.models import LogMessage
from django.contrib.auth.views import LoginView, LogoutView

home_list_view = views.HomeListView.as_view(
    queryset=LogMessage.objects.order_by("-log_date")[:5],  # :5 limits the results to the five most recent
    context_object_name="message_list",
    template_name="App1/home.html",
)
urlpatterns = [
    path("", views.home_view, name="home"),  # Asegúrate de que esta vista esté protegida con @login_required
    path('login/', LoginView.as_view(template_name='App1/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("approve/", views.approve, name="approve"),
    #path("about/", views.about, name="about"),
    #path("contact/", views.contact, name="contact"),
    path("SPSF/", views.spsf_view, name="SPSF"),
    path("SPSF/<str:station_name>/", views.spsf_station_view, name="spsf_station_view"),
    path("tapes/<str:station_name>/", views.tapes_station_view, name="tapes_station_view"),
    path("maintenances", views.MaintenanceListView.as_view(), name="maintenance_list"),
    path("<str:station_name>/log_maintenance/", views.log_maintenance, name="log_maintenance"),
    path("tapes/", views.tapes_view, name="tapes"),
    path("Historial_mantenimientos/", views.maintenances_history, name="Historial_mantenimientos"),
    path("download_maintenance_excel/", views.download_maintenance_excel, name="download_maintenance_excel"),
    path("register/", views.register, name="register"),
]


