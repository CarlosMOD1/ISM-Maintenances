# Generated by Django 5.1.7 on 2025-04-08 17:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App1', '0010_maintenancerecord_aprobado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='maintenancerecord',
            name='aprobado',
            field=models.CharField(choices=[('No aprobado', 'No aprobado'), ('Aprobado', 'Aprobado'), ('Rechazado', 'Rechazado')], default='No aprobado', max_length=20),
        ),
    ]
