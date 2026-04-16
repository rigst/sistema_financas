from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="categoriaitem",
            name="cor",
            field=models.CharField(
                choices=[
                    ("#2563EB", "Azul"),
                    ("#0F766E", "Verde petróleo"),
                    ("#059669", "Verde"),
                    ("#CA8A04", "Mostarda"),
                    ("#EA580C", "Laranja"),
                    ("#DC2626", "Vermelho"),
                    ("#DB2777", "Rosa"),
                    ("#7C3AED", "Violeta"),
                    ("#4F46E5", "Índigo"),
                    ("#475569", "Grafite"),
                ],
                default="#2563EB",
                max_length=7,
            ),
        ),
    ]
