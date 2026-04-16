from django.db import migrations


NOVA_COR = "#475569"
COR_ANTIGA = "#FFFFFF"


def substituir_cor_branca(apps, schema_editor):
    CategoriaItem = apps.get_model("catalogo", "CategoriaItem")
    CategoriaItem.objects.filter(cor=COR_ANTIGA).update(cor=NOVA_COR)


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0003_categoriaitem_empresa_itemcatalogo_empresa_and_more"),
    ]

    operations = [
        migrations.RunPython(substituir_cor_branca, migrations.RunPython.noop),
    ]
