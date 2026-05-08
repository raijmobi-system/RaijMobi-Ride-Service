
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_rename_departure_time_ride_start_time_ride_end_time'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ride',
            old_name='seats',
            new_name='available_seats',
        ),

        migrations.AddField(
            model_name='ride',
            name='expected_arrival',
            field=models.DateTimeField(
                default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),

        migrations.AddField(
            model_name='vehicle',
            name='seats',
            field=models.IntegerField(
                default=4
            ),
            preserve_default=False,
        ),

        migrations.AlterField(
            model_name='ride',
            name='status',
            field=models.CharField(
                choices=[
                    ('pendente', 'Pendente'),
                    ('confirmada', 'Confirmada'),
                    ('em_andamento', 'Em Andamento'),
                    ('cancelada', 'Cancelada'),
                    ('finalizada', 'Finalizada')
                ],
                max_length=50
            ),
        ),
    ]