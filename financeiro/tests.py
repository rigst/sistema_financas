from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from .models import Despesa, Receita, Reserva
from .planejamento import calcular_planejamento_semanal, resumo_fluxo_periodo, resumo_mensal


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

        despesa.refresh_from_db()
        self.assertEqual(despesa.competencia, date(2026, 4, 1))
        self.assertEqual([item["valor"] for item in ocorrencias], [Decimal("200.00"), Decimal("200.00"), Decimal("200.00")])
        self.assertEqual([item["parcela"] for item in ocorrencias], [1, 2, 3])

    def test_parcelada_pode_comecar_em_parcela_atual_maior_que_um(self):
        despesa = Despesa.objects.create(
            tipo="parcelada",
            descricao="Financiamento",
            valor=Decimal("1200.00"),
            data=date(2026, 4, 10),
            categoria="Casa",
            parcelas=12,
            parcela_atual=5,
            status="pendente",
            criado_por=self.user,
        )
        receita = Receita.objects.create(
            tipo="parcelada",
            descricao="Acordo",
            valor=Decimal("600.00"),
            data=date(2026, 4, 12),
            categoria="Serviços",
            parcelas=6,
            parcela_atual=4,
            status="prevista",
            criado_por=self.user,
        )

        despesas = despesa.ocorrencias(date(2026, 4, 1), date(2026, 6, 30))
        receitas = receita.ocorrencias(date(2026, 4, 1), date(2026, 6, 30))

        self.assertEqual([item["parcela"] for item in despesas], [5, 6, 7])
        self.assertEqual([item["valor"] for item in despesas], [Decimal("100.00"), Decimal("100.00"), Decimal("100.00")])
        self.assertEqual(despesa.parcela_na_data(date(2026, 6, 1)), 7)
        self.assertEqual([item["parcela"] for item in receitas], [4, 5, 6])
        self.assertEqual([item["valor"] for item in receitas], [Decimal("100.00"), Decimal("100.00"), Decimal("100.00")])
        self.assertEqual(receita.parcela_na_data(date(2026, 5, 1)), 5)

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
        self.assertEqual(planejamento["base_mes"]["sobra_mes"], Decimal("550.00"))
        self.assertEqual(semana["cota_semana"], Decimal("300.00"))
        self.assertEqual(semana["gasto_semana"], Decimal("350.00"))
        self.assertEqual(semana["disponivel"], Decimal("-50.00"))

    def test_resumos_separam_pago_pendente_e_parcelas_restantes(self):
        Receita.objects.create(
            descricao="Receita confirmada",
            valor=Decimal("1000.00"),
            data=date(2026, 4, 2),
            categoria="Serviços",
            status="recebida",
            criado_por=self.user,
        )
        Despesa.objects.create(
            tipo="variavel",
            descricao="Mercado",
            valor=Decimal("120.00"),
            data=date(2026, 4, 3),
            categoria="Compras",
            status="paga",
            criado_por=self.user,
        )
        Despesa.objects.create(
            tipo="parcelada",
            descricao="Geladeira",
            valor=Decimal("1200.00"),
            data=date(2026, 4, 5),
            categoria="Casa",
            parcelas=12,
            parcela_atual=5,
            status="pendente",
            criado_por=self.user,
        )

        fluxo = resumo_fluxo_periodo(self.user, date(2026, 4, 1), date(2026, 4, 30))
        mensal = resumo_mensal(self.user, date(2026, 4, 10))

        self.assertEqual(fluxo["despesas_pagas"], Decimal("120.00"))
        self.assertEqual(fluxo["despesas_pendentes"], Decimal("100.00"))
        self.assertEqual(fluxo["saldo_confirmado"], Decimal("880.00"))
        self.assertEqual(fluxo["saldo_planejado"], Decimal("780.00"))
        self.assertEqual(mensal["parcelas"], Decimal("100.00"))
        self.assertEqual(mensal["despesas_pendentes"], Decimal("100.00"))


class FinanceiroSimplificadoViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fin_view", password="senha-forte-123")
        self.client.force_login(self.user)

    def test_fluxo_de_receita_despesa_reserva_e_controle(self):
        response_receita = self.client.post(
            reverse("financeiro:receita_criar"),
            {
                "descricao": "Freelance",
                "tipo": "variavel",
                "valor": "1500,00",
                "data": "2026-04-16",
                "competencia": "2026-04",
                "categoria": "Serviços",
                "status": "recebida",
                "observacoes": "",
            },
        )
        self.assertEqual(response_receita.status_code, 302)
        receita = Receita.objects.get(descricao="Freelance")
        self.assertEqual(receita.competencia, date(2026, 4, 1))

        response_despesa = self.client.post(
            reverse("financeiro:despesa_criar"),
            {
                "tipo": "parcelada",
                "descricao": "Curso",
                "valor": "600,00",
                "data": "2026-04-20",
                "competencia": "2026-04",
                "categoria": "Educação",
                "parcelas": "3",
                "parcela_atual": "2",
                "observacoes": "",
            },
        )
        self.assertEqual(response_despesa.status_code, 302)
        despesa = Despesa.objects.get(descricao="Curso", tipo="parcelada", parcelas=3)
        self.assertEqual(despesa.competencia, date(2026, 4, 1))
        self.assertEqual(despesa.parcela_atual, 2)

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

    def test_despesa_parcelada_pode_ser_informada_pelo_valor_da_parcela(self):
        response = self.client.post(
            reverse("financeiro:despesa_criar"),
            {
                "tipo": "parcelada",
                "descricao": "Celular",
                "valor": "900,00",
                "valor_parcela": "300,00",
                "data": "2026-04-20",
                "competencia": "2026-04",
                "categoria": "Eletrônicos",
                "parcelas": "3",
                "parcela_atual": "2",
                "observacoes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        despesa = Despesa.objects.get(descricao="Celular")
        self.assertEqual(despesa.valor, Decimal("900.00"))
        self.assertEqual(despesa.valor_parcela, Decimal("300.00"))
        self.assertEqual(despesa.parcela_atual, 2)

    def test_acoes_rapidas_e_csv_exportam_fluxo_simples(self):
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

        receita.refresh_from_db()
        despesa.refresh_from_db()
        self.assertEqual(response_receita.status_code, 302)
        self.assertEqual(receita.status, "recebida")
        self.assertIsNotNone(receita.data_recebimento)
        self.assertEqual(despesa.status, "pendente")

        response_pagar = self.client.post(reverse("financeiro:despesa_marcar_paga", args=[despesa.pk]))
        despesa.refresh_from_db()
        self.assertEqual(response_pagar.status_code, 302)
        self.assertEqual(despesa.status, "paga")

        response_cancelar = self.client.post(reverse("financeiro:despesa_cancelar", args=[despesa.pk]))
        despesa.refresh_from_db()
        self.assertEqual(response_cancelar.status_code, 302)
        self.assertEqual(despesa.status, "cancelada")

        response_csv = self.client.get(reverse("financeiro:exportar_csv"))
        conteudo = response_csv.content.decode("utf-8-sig")
        self.assertEqual(response_csv.status_code, 200)
        self.assertIn("text/csv", response_csv["Content-Type"])
        self.assertIn("tipo,descricao,valor,data,competencia,categoria,status,parcelas,parcela_atual,observacoes", conteudo)
        self.assertIn("receita,Receita prevista", conteudo)
        self.assertIn("despesa,Conta de luz", conteudo)
        self.assertIn("2026-04", conteudo)

    def test_controle_permite_navegar_por_semana(self):
        response = self.client.get(reverse("financeiro:controle"), {"semana": "2026-04-20"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20/04 a 26/04")
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
