from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("relatorios", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaoempresa",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
    ]
