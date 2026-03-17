from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulator', '0002_add_generar_comparacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='simulationrun',
            name='config_rates_json',
            field=models.JSONField(
                blank=True, null=True,
                help_text='Overrides of rates_dict passed to model.config.actualizar_rates()',
            ),
        ),
        migrations.AddField(
            model_name='simulationrun',
            name='config_light_json',
            field=models.JSONField(
                blank=True, null=True,
                help_text='Overrides of light_dict passed to model.config.actualizar_light()',
            ),
        ),
    ]
