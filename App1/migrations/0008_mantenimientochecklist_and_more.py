# Generated by Django 5.1.7 on 2025-04-01 15:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('App1', '0007_alter_maintenancerecord_unidad_de_trabajo'),
    ]

    operations = [
        migrations.CreateModel(
            name='MantenimientoChecklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.AlterField(
            model_name='maintenancerecord',
            name='unidad_de_trabajo',
            field=models.CharField(choices=[('tapes', 'tapes'), ('SPSF', 'SPSF')], default='--', max_length=100),
        ),
    ]
