from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from .models import Despesa, Receita, Reserva
from .planejamento import calcular_planejamento_semanal


class FinanceiroSimplificadoModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fin_user", password="senha-forte-123")

    def test_despesa_parcelada_distribui_ocorrencias_mensais(self):
        despesa = Despesa.objects.create(
            tipo="parcelada",
            descricao="Curso",
            valor=Decimal("600.00"),
            data=date(2026, 4, 20),
            categoria="Educação",
            parcelas=3,
            status="pendente",
            criado_por=self.user,
        )

        ocorrencias = despesa.ocorrencias(date(2026, 4, 1), date(2026, 6, 30))

        self.assertEqual([item["valor"] for item in ocorrencias], [Decimal("200.00"), Decimal("200.00"), Decimal("200.00")])
        self.assertEqual([item["parcela"] for item in ocorrencias], [1, 2, 3])

    def test_planejamento_semanal_mostra_disponivel_e_compromissos(self):
        Receita.objects.create(
            descricao="Salário",
            valor=Decimal("2000.00"),
            data=date(2026, 4, 13),
            categoria="Salário",
            status="recebida",
            criado_por=self.user,
        )
        Despesa.objects.create(
            tipo="variavel",
            descricao="Mercado",
            valor=Decimal("350.00"),
            data=date(2026, 4, 14),
            categoria="Casa",
            status="paga",
            criado_por=self.user,
        )
        Despesa.objects.create(
            tipo="fixa",
            descricao="Aluguel",
            valor=Decimal("900.00"),
            data=date(2026, 4, 17),
            categoria="Moradia",
            status="pendente",
            criado_por=self.user,
        )
        Despesa.objects.create(
            tipo="parcelada",
            descricao="Notebook",
            valor=Decimal("600.00"),
            data=date(2026, 4, 18),
            categoria="Trabalho",
            parcelas=3,
            status="pendente",
            criado_por=self.user,
        )

        planejamento = calcular_planejamento_semanal(self.user, date(2026, 4, 16), quantidade=1)
        semana = planejamento["semana_atual"]

        self.assertEqual(planejamento["saldo_total"], Decimal("1650.00"))
        self.assertEqual(semana["fixos"], Decimal("900.00"))
        self.assertEqual(semana["parcelas"], Decimal("200.00"))
        self.assertEqual(semana["disponivel"], Decimal("550.00"))


class FinanceiroSimplificadoViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fin_view", password="senha-forte-123")
        self.client.force_login(self.user)

    def test_fluxo_de_receita_despesa_reserva_e_controle(self):
        response_receita = self.client.post(
            reverse("financeiro:receita_criar"),
            {
                "descricao": "Freelance",
                "valor": "1500,00",
                "data": "2026-04-16",
                "categoria": "Serviços",
                "status": "recebida",
                "observacoes": "",
            },
        )
        self.assertEqual(response_receita.status_code, 302)
        self.assertTrue(Receita.objects.filter(descricao="Freelance").exists())

        response_despesa = self.client.post(
            reverse("financeiro:despesa_criar"),
            {
                "tipo": "parcelada",
                "descricao": "Curso",
                "valor": "600,00",
                "data": "2026-04-20",
                "categoria": "Educação",
                "parcelas": "3",
                "status": "pendente",
                "observacoes": "",
            },
        )
        self.assertEqual(response_despesa.status_code, 302)
        self.assertEqual(Despesa.objects.filter(descricao="Curso", tipo="parcelada", parcelas=3).count(), 1)

        response_reserva = self.client.post(
            reverse("financeiro:reserva_criar"),
            {
                "nome": "Emergência",
                "valor_atual": "500,00",
                "valor_alvo": "2000,00",
                "observacoes": "",
            },
        )
        self.assertEqual(response_reserva.status_code, 302)
        self.assertTrue(Reserva.objects.filter(nome="Emergência").exists())

        response_controle = self.client.get(reverse("financeiro:controle"))
        self.assertEqual(response_controle.status_code, 200)
        self.assertContains(response_controle, "Planejamento semanal")
        self.assertContains(response_controle, "Emergência")

    def test_acoes_rapidas_atualizam_status_e_csv_exporta_fluxo_simples(self):
        receita = Receita.objects.create(
            descricao="Receita prevista",
            valor=Decimal("900.00"),
            data=date(2026, 4, 16),
            categoria="Serviços",
            status="prevista",
            criado_por=self.user,
        )
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Conta de luz",
            valor=Decimal("150.00"),
            data=date(2026, 4, 16),
            categoria="Casa",
            status="pendente",
            criado_por=self.user,
        )

        response_receita = self.client.post(reverse("financeiro:receita_marcar_recebida", args=[receita.pk]))
        response_despesa = self.client.post(reverse("financeiro:despesa_marcar_paga", args=[despesa.pk]))

        receita.refresh_from_db()
        despesa.refresh_from_db()
        self.assertEqual(response_receita.status_code, 302)
        self.assertEqual(response_despesa.status_code, 302)
        self.assertEqual(receita.status, "recebida")
        self.assertEqual(despesa.status, "paga")

        response_cancelar = self.client.post(reverse("financeiro:despesa_cancelar", args=[despesa.pk]))
        despesa.refresh_from_db()
        self.assertEqual(response_cancelar.status_code, 302)
        self.assertEqual(despesa.status, "cancelada")

        response_csv = self.client.get(reverse("financeiro:exportar_csv"))
        conteudo = response_csv.content.decode("utf-8-sig")
        self.assertEqual(response_csv.status_code, 200)
        self.assertIn("text/csv", response_csv["Content-Type"])
        self.assertIn("tipo,descricao,valor,data,categoria,status,parcelas,observacoes", conteudo)
        self.assertIn("receita,Receita prevista", conteudo)
        self.assertIn("despesa,Conta de luz", conteudo)

    def test_controle_permite_navegar_por_semana(self):
        response = self.client.get(reverse("financeiro:controle"), {"semana": "2026-04-20"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20/04/2026 a 26/04/2026")
        self.assertContains(response, "semana=2026-04-13")
        self.assertContains(response, "semana=2026-04-27")

    def test_lista_de_despesas_filtra_por_tipo(self):
        Despesa.objects.create(
            tipo="fixa",
            descricao="Aluguel",
            valor=Decimal("900.00"),
            data=date(2026, 4, 10),
            status="pendente",
            criado_por=self.user,
        )
        Despesa.objects.create(
            tipo="variavel",
            descricao="Padaria",
            valor=Decimal("30.00"),
            data=date(2026, 4, 11),
            status="pendente",
            criado_por=self.user,
        )

        response = self.client.get(reverse("financeiro:despesa_lista"), {"tipo": "fixa"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aluguel")
        self.assertNotContains(response, "Padaria")

    def test_rotas_burocraticas_foram_removidas(self):
        nomes_removidos = [
            "conta_lista",
            "conta_criar",
            "cartao_lista",
            "fatura_lista",
            "transacao_lista",
            "transacao_criar",
            "relatorio_fluxo_caixa",
            "planejamento_lista",
            "meta_lista",
            "recorrencia_lista",
        ]

        for nome in nomes_removidos:
            with self.subTest(nome=nome):
                with self.assertRaises(NoReverseMatch):
                    reverse(f"financeiro:{nome}")
