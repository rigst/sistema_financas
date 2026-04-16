from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orcamentos", "0002_alter_itemorcamento_unidade_medida_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="orcamento",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
    ]
