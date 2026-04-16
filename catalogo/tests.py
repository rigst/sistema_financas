from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CategoriaItem, ItemCatalogo
from .services import importar_catalogo_excel


class CatalogoPermissaoTests(TestCase):
    def test_orcamentista_nao_pode_criar_item_catalogo(self):
        user = get_user_model().objects.create_user(
            username="orcamentista",
            password="senha-forte-123",
            perfil="orcamentista",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("catalogo:item_criar"))

        self.assertEqual(response.status_code, 403)

    def test_admin_pode_criar_item_catalogo(self):
        user = get_user_model().objects.create_user(
            username="admin",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("catalogo:item_criar"))

        self.assertEqual(response.status_code, 200)

    def test_visualizador_pode_visualizar_item_catalogo(self):
        user = get_user_model().objects.create_user(
            username="visualizador_catalogo",
            password="senha-forte-123",
            perfil="visualizador",
        )
        item = ItemCatalogo.objects.create(
            codigo="VIS-01",
            nome="Item visivel",
            unidade_medida="un",
            valor_unitario_padrao="10.00",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("catalogo:item_visualizar", args=[item.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item visivel")


class CatalogoValidacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_item_catalogo_invalido_exibe_erros(self):
        response = self.client.post(
            reverse("catalogo:item_criar"),
            {
                "nome": "",
                "unidade_medida": "un",
                "valor_unitario_padrao": "-1",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe o nome do item.")
        self.assertContains(response, "Informe um valor maior ou igual a zero.")
        self.assertEqual(ItemCatalogo.objects.count(), 0)

    def test_item_catalogo_aceita_valor_formatado_em_pt_br(self):
        response = self.client.post(
            reverse("catalogo:item_criar"),
            {
                "codigo": "",
                "nome": "Servico premium",
                "unidade_medida": "un",
                "valor_unitario_padrao": "R$ 15.000,00",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = ItemCatalogo.objects.get(nome="Servico premium")
        self.assertEqual(item.codigo, "CAT-ITEM-0001")
        self.assertEqual(str(item.valor_unitario_padrao), "15000.00")

    def test_codigo_do_catalogo_e_mantido_na_edicao(self):
        item = ItemCatalogo.objects.create(
            codigo="IGNORAR",
            nome="Servico base",
            unidade_medida="un",
            valor_unitario_padrao="10.00",
        )

        response = self.client.post(
            reverse("catalogo:item_editar", args=[item.pk]),
            {
                "codigo": "TENTATIVA-MUDANCA",
                "nome": "Servico base ajustado",
                "unidade_medida": "un",
                "valor_unitario_padrao": "12.00",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.codigo, "CAT-ITEM-0001")

    def test_categoria_aceita_cor_predefinida(self):
        response = self.client.post(
            reverse("catalogo:categoria_criar"),
            {
                "nome": "Categoria colorida",
                "descricao": "Teste",
                "cor": "#EA580C",
                "ativo": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        categoria = CategoriaItem.objects.get(nome="Categoria colorida")
        self.assertEqual(categoria.cor, "#EA580C")

    def test_formularios_de_categoria_e_item_exibem_botoes_com_icone_e_texto(self):
        categoria_response = self.client.get(reverse("catalogo:categoria_criar"))
        item_response = self.client.get(reverse("catalogo:item_criar"))

        self.assertEqual(categoria_response.status_code, 200)
        self.assertContains(categoria_response, ">Voltar<", html=False)
        self.assertContains(categoria_response, "Salvar categoria")

        self.assertEqual(item_response.status_code, 200)
        self.assertContains(item_response, ">Voltar<", html=False)
        self.assertContains(item_response, "Salvar item")


class CatalogoListaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="lista_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)
        categoria_a = CategoriaItem.objects.create(nome="Categoria A")
        categoria_b = CategoriaItem.objects.create(nome="Categoria B")
        ItemCatalogo.objects.create(
            codigo="B-01",
            nome="Item caro",
            categoria=categoria_b,
            unidade_medida="un",
            valor_unitario_padrao="100.00",
            ativo=True,
        )
        ItemCatalogo.objects.create(
            codigo="A-01",
            nome="Item barato",
            categoria=categoria_a,
            unidade_medida="un",
            valor_unitario_padrao="10.00",
            ativo=False,
        )

    def test_lista_filtra_por_categoria_e_ativo(self):
        categoria = CategoriaItem.objects.get(nome="Categoria B")
        response = self.client.get(
            reverse("catalogo:item_lista"),
            {"categoria": categoria.pk, "ativo": "ativos"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item caro")
        self.assertNotContains(response, "Item barato")

    def test_lista_ordena_por_preco_maior(self):
        response = self.client.get(reverse("catalogo:item_lista"), {"sort": "preco_maior"})

        self.assertEqual(response.status_code, 200)
        itens = list(response.context["itens"])
        self.assertEqual(itens[0].nome, "Item caro")

    def test_lista_de_itens_e_paginada(self):
        categoria = CategoriaItem.objects.get(nome="Categoria A")
        for indice in range(26):
            ItemCatalogo.objects.create(
                codigo=f"EXTRA-{indice:02d}",
                nome=f"Extra {indice:02d}",
                categoria=categoria,
                unidade_medida="un",
                valor_unitario_padrao="1.00",
            )

        response = self.client.get(reverse("catalogo:item_lista"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_previous())
        self.assertEqual(response.context["page_obj"].paginator.per_page, 25)
        self.assertContains(response, "Extra 25")

    def test_lista_exibe_unidade_m2_com_rotulo_curto(self):
        categoria = CategoriaItem.objects.create(nome="Medidas")
        ItemCatalogo.objects.create(
            codigo="M2-01",
            nome="Piso",
            categoria=categoria,
            unidade_medida="m2",
            valor_unitario_padrao="5.00",
        )

        response = self.client.get(reverse("catalogo:item_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">m2<", html=False)
        self.assertNotContains(response, "Metro quadrado")

    def test_lista_exibe_categoria_com_cor(self):
        categoria = CategoriaItem.objects.create(nome="Colorida", cor="#DB2777")
        ItemCatalogo.objects.create(
            codigo="COR-01",
            nome="Item colorido",
            categoria=categoria,
            unidade_medida="un",
            valor_unitario_padrao="5.00",
        )

        response = self.client.get(reverse("catalogo:item_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Colorida")
        self.assertContains(response, "#DB2777")

    def test_lista_exibe_botoes_principais_com_texto_e_ordem_de_importacao_antes_da_exportacao(self):
        response = self.client.get(reverse("catalogo:item_lista"))

        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode("utf-8")
        self.assertIn("Importar Excel", conteudo)
        self.assertIn("Exportar Excel", conteudo)
        self.assertIn("Novo item", conteudo)
        self.assertLess(conteudo.index("Importar Excel"), conteudo.index("Exportar Excel"))

    def test_lista_de_categorias_exibe_botao_principal_com_texto(self):
        response = self.client.get(reverse("catalogo:categoria_lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nova categoria")

    def test_lista_de_categorias_exibe_botoes_de_importacao_e_exportacao(self):
        response = self.client.get(reverse("catalogo:categoria_lista"))

        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode("utf-8")
        self.assertIn("Importar Excel", conteudo)
        self.assertIn("Exportar Excel", conteudo)
        self.assertIn("Nova categoria", conteudo)
        self.assertLess(conteudo.index("Importar Excel"), conteudo.index("Exportar Excel"))

    def test_exportacao_excel_do_catalogo_usa_colunas_do_importador(self):
        categoria = CategoriaItem.objects.create(nome="Exportacao")
        ItemCatalogo.objects.create(
            codigo="EXP-01",
            nome="Painel",
            categoria=categoria,
            unidade_medida="-",
            valor_unitario_padrao="25.00",
            descricao_padrao="Descricao exportada",
            observacoes="Observacao exportada",
        )

        response = self.client.get(reverse("catalogo:item_exportar_excel"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertIn('attachment; filename="catalogo-itens.xls"', response["Content-Disposition"])
        conteudo = response.content.decode("utf-8")
        self.assertIn("CATEGORIA", conteudo)
        self.assertIn("ITEM", conteudo)
        self.assertIn("UNIDADE", conteudo)
        self.assertIn("Exportacao", conteudo)
        self.assertIn("Painel", conteudo)
        self.assertIn(">-<", conteudo)


class CatalogoInativacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_toggle_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_item_pode_ser_inativado(self):
        item = ItemCatalogo.objects.create(
            codigo="INAT-01",
            nome="Item ativo",
            unidade_medida="un",
            valor_unitario_padrao="15.00",
        )

        response = self.client.post(reverse("catalogo:item_excluir", args=[item.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Item inativado com sucesso.")
        item.refresh_from_db()
        self.assertFalse(item.ativo)

    def test_categoria_pode_ser_inativada(self):
        categoria = CategoriaItem.objects.create(nome="Categoria ativa")

        response = self.client.post(reverse("catalogo:categoria_excluir", args=[categoria.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Categoria inativada com sucesso.")
        categoria.refresh_from_db()
        self.assertFalse(categoria.ativo)


class CatalogoAtualizacaoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_edita_categoria",
            password="senha-forte-123",
            perfil="admin",
        )
        self.client.force_login(self.user)

    def test_formulario_de_edicao_de_categoria_exibe_aviso(self):
        categoria = CategoriaItem.objects.create(nome="Categoria Base", descricao="Inicial")

        response = self.client.get(reverse("catalogo:categoria_editar", args=[categoria.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "itens do catálogo vinculados")

    def test_edicao_de_categoria_sem_troca_de_cor_exibe_mensagem_de_propagacao(self):
        categoria = CategoriaItem.objects.create(nome="Categoria Base", descricao="Inicial")

        response = self.client.post(
            reverse("catalogo:categoria_editar", args=[categoria.pk]),
            {
                "nome": "Categoria Atualizada",
                "descricao": "Descrição ajustada",
                "cor": categoria.cor,
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Os itens do catálogo e os orçamentos ainda não enviados passam a usar os dados mais recentes desta categoria.",
        )


class CatalogoImportacaoExcelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_importacao_catalogo",
            password="senha-forte-123",
            perfil="admin",
        )
        self.empresa = self.user.groups.get()
        self.client.force_login(self.user)

    def criar_xlsx(self, rows):
        sheet_rows = []
        for indice, row in enumerate(rows, start=1):
            cells = []
            for coluna, valor in zip(("A", "B", "C", "D", "E", "F"), row):
                ref = f"{coluna}{indice}"
                if valor is None:
                    continue
                if isinstance(valor, (int, float, Decimal)):
                    cells.append(f'<c r="{ref}"><v>{valor}</v></c>')
                else:
                    texto = (
                        str(valor)
                        .replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{texto}</t></is></c>')
            sheet_rows.append(f'<row r="{indice}">{"".join(cells)}</row>')

        workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Planilha1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
        rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
   Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
   Target="worksheets/sheet1.xml"/>
</Relationships>
"""
        sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {''.join(sheet_rows)}
  </sheetData>
</worksheet>
"""
        content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
        root_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
   Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
   Target="xl/workbook.xml"/>
</Relationships>
"""

        arquivo = BytesIO()
        with ZipFile(arquivo, "w") as zip_file:
            zip_file.writestr("[Content_Types].xml", content_types)
            zip_file.writestr("_rels/.rels", root_rels)
            zip_file.writestr("xl/workbook.xml", workbook)
            zip_file.writestr("xl/_rels/workbook.xml.rels", rels)
            zip_file.writestr("xl/worksheets/sheet1.xml", sheet)
        arquivo.seek(0)
        return arquivo

    def test_importacao_normaliza_unidades_e_arredonda_valores_do_excel(self):
        arquivo = self.criar_xlsx([
            ("CATEGORIA", "ITEM", "VALOR", "UNIDADE", "DESCRIÇÃO", "OBSERVAÇÃO"),
            ("PISO", "Brita", 85.7142857142857, "m²", "", ""),
            ("MONTAGEM", "Recepcionista", 1, "unid.", "Atendimento", ""),
            ("EXTRAS", "Sem piso", 0, "-", "", "Sem cobrança"),
        ])

        categorias_criadas, itens_criados = importar_catalogo_excel(arquivo, self.empresa)

        self.assertEqual(categorias_criadas, 3)
        self.assertEqual(itens_criados, 3)
        self.assertEqual(ItemCatalogo.objects.get(nome="Brita").unidade_medida, "m2")
        self.assertEqual(ItemCatalogo.objects.get(nome="Brita").valor_unitario_padrao, Decimal("85.71"))
        self.assertEqual(ItemCatalogo.objects.get(nome="Recepcionista").unidade_medida, "un")
        self.assertEqual(ItemCatalogo.objects.get(nome="Sem piso").unidade_medida, "-")

    def test_importacao_ignora_linhas_de_secao_com_texto_fora_da_coluna_categoria(self):
        arquivo = self.criar_xlsx([
            ("CATEGORIA", "ITEM", "VALOR", "UNIDADE", "DESCRIÇÃO", "OBSERVAÇÃO"),
            ("PISO", "Brita", 85.7142857142857, "m²", "", ""),
            (None, "TAPETE", None, None, None, None),
            ("PISO", "Deck", 10, "m²", "", ""),
        ])

        categorias_criadas, itens_criados = importar_catalogo_excel(arquivo, self.empresa)

        self.assertEqual(categorias_criadas, 1)
        self.assertEqual(itens_criados, 2)
        self.assertFalse(ItemCatalogo.objects.filter(nome="TAPETE").exists())

    def test_importacao_rejeita_unidade_desconhecida(self):
        arquivo = self.criar_xlsx([
            ("CATEGORIA", "ITEM", "VALOR", "UNIDADE", "DESCRIÇÃO", "OBSERVAÇÃO"),
            ("PISO", "Item inválido", 10, "litro", "", ""),
        ])

        with self.assertRaisesMessage(ValueError, "Unidade inválida na importação: litro"):
            importar_catalogo_excel(arquivo, self.empresa)

    def test_importacao_cancela_tudo_quando_encontra_erro(self):
        arquivo = self.criar_xlsx([
            ("CATEGORIA", "ITEM", "VALOR", "UNIDADE", "DESCRIÇÃO", "OBSERVAÇÃO"),
            ("PISO", "Item válido", 10, "m2", "", ""),
            ("PISO", "Item inválido", 10, "litro", "", ""),
        ])

        with self.assertRaisesMessage(ValueError, "Unidade inválida na importação: litro"):
            importar_catalogo_excel(arquivo, self.empresa)

        self.assertEqual(CategoriaItem.objects.filter(empresa=self.empresa).count(), 0)
        self.assertEqual(ItemCatalogo.objects.filter(empresa=self.empresa).count(), 0)

    def test_tela_de_importacao_exibe_mensagem_amigavel_sem_quebrar_fluxo(self):
        arquivo = self.criar_xlsx([
            ("CATEGORIA", "ITEM", "VALOR", "UNIDADE", "DESCRIÇÃO", "OBSERVAÇÃO"),
            ("PISO", "Item inválido", 10, "litro", "", ""),
        ])

        response = self.client.post(
            reverse("catalogo:item_importar_excel"),
            {"arquivo": arquivo},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linha 2: Unidade inválida na importação: litro")
        self.assertEqual(CategoriaItem.objects.filter(empresa=self.empresa).count(), 0)
        self.assertEqual(ItemCatalogo.objects.filter(empresa=self.empresa).count(), 0)

    def test_tela_de_importacao_exibe_voltar_antes_do_botao_importar(self):
        response = self.client.get(reverse("catalogo:item_importar_excel"))

        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode("utf-8")
        self.assertLess(conteudo.index(">Voltar<"), conteudo.index(">Importar<"))
