from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from .models import CompartilhamentoDespesa, Despesa, ParticipanteCompartilhamentoDespesa, Receita, Reserva
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

    def test_despesa_compartilhada_so_computa_quando_todos_aceitam(self):
        outro = get_user_model().objects.create_user(username="outro_model")
        terceiro = get_user_model().objects.create_user(username="terceiro_model")
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Compra compartilhada",
            valor=Decimal("100.00"),
            data=date(2026, 4, 10),
            categoria="Casa",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("300.00"),
            modo_divisao="igual",
            pagador=self.user,
        )
        participante_1 = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=outro,
            valor=Decimal("100.00"),
            status="aceito",
        )
        ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=terceiro,
            valor=Decimal("100.00"),
            status="pendente",
        )

        fluxo_criador = resumo_fluxo_periodo(self.user, date(2026, 4, 1), date(2026, 4, 30))
        fluxo_participante = resumo_fluxo_periodo(outro, date(2026, 4, 1), date(2026, 4, 30))

        self.assertEqual(compartilhamento.status_geral, "aguardando")
        self.assertEqual(fluxo_criador["despesas_pendentes"], Decimal("0.00"))
        self.assertEqual(fluxo_participante["despesas_pendentes"], Decimal("0.00"))
        self.assertEqual(participante_1.despesa_gerada, None)


class FinanceiroSimplificadoViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="fin_view", password="senha-forte-123")
        self.outro_user = get_user_model().objects.create_user(username="outro_fin", password="senha-forte-123")
        self.terceiro_user = get_user_model().objects.create_user(username="terceiro_fin", password="senha-forte-123")
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

    def test_despesa_compartilhada_fica_pendente_ate_aceite(self):
        response = self.client.post(
            reverse("financeiro:despesa_criar"),
            {
                "tipo": "parcelada",
                "descricao": "Viagem",
                "valor": "900,00",
                "data": "2026-04-20",
                "competencia": "2026-04",
                "categoria": "Lazer",
                "parcelas": "3",
                "parcela_atual": "1",
                "status": "pendente",
                "observacoes": "",
                "compartilhar": "on",
                "participantes": "outro_fin",
                "modo_divisao": "igual",
                "valores_participantes": "",
                "pagador": "fin_view",
                "data_prevista_ressarcimento": "2026-05-10",
            },
        )

        self.assertEqual(response.status_code, 302)
        despesa = Despesa.objects.get(descricao="Viagem", criado_por=self.user)
        compartilhamento = CompartilhamentoDespesa.objects.get(despesa=despesa)
        participante = ParticipanteCompartilhamentoDespesa.objects.get(compartilhamento=compartilhamento, usuario=self.outro_user)
        self.assertEqual(compartilhamento.valor_total, Decimal("900.00"))
        self.assertEqual(despesa.valor, Decimal("450.00"))
        self.assertEqual(participante.valor, Decimal("450.00"))
        self.assertEqual(participante.status, "pendente")
        self.assertIsNone(participante.despesa_gerada)

        self.client.force_login(self.outro_user)
        response_lista = self.client.get(reverse("financeiro:despesa_lista"))
        self.assertContains(response_lista, "Nenhuma despesa encontrada.")
        self.assertFalse(Despesa.objects.filter(descricao="Viagem", criado_por=self.outro_user).exists())
        response_notificacao = self.client.get(reverse("financeiro:despesa_lista"))
        self.assertContains(response_notificacao, "Viagem")
        self.assertContains(response_notificacao, "450,00")
        self.assertContains(response_notificacao, "Compartilhadas com você")

        response_aceite = self.client.post(reverse("financeiro:despesa_compartilhada_aceitar", args=[participante.pk]))
        participante.refresh_from_db()
        self.assertEqual(response_aceite.status_code, 302)
        self.assertEqual(participante.status, "aceito")
        self.assertIsNotNone(participante.despesa_gerada)
        self.assertEqual(participante.despesa_gerada.valor, Decimal("450.00"))
        self.assertEqual(participante.despesa_gerada.parcelas, 3)

    def test_edicao_de_compartilhada_atualiza_despesa_aceita(self):
        despesa = Despesa.objects.create(
            tipo="fixa",
            descricao="Internet",
            valor=Decimal("50.00"),
            data=date(2026, 4, 10),
            categoria="Casa",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("100.00"),
            modo_divisao="igual",
            pagador=self.user,
            data_prevista_ressarcimento=date(2026, 5, 5),
        )
        participante = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.outro_user,
            valor=Decimal("50.00"),
            status="aceito",
        )
        self.client.force_login(self.outro_user)
        self.client.post(reverse("financeiro:despesa_compartilhada_aceitar", args=[participante.pk]))
        participante.refresh_from_db()

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("financeiro:despesa_editar", args=[despesa.pk]),
            {
                "tipo": "fixa",
                "descricao": "Internet fibra",
                "valor": "120,00",
                "data": "2026-04-10",
                "competencia": "2026-04",
                "categoria": "Casa",
                "status": "pendente",
                "observacoes": "",
                "compartilhar": "on",
                "participantes": "outro_fin",
                "modo_divisao": "fixo",
                "valores_participantes": "70,00",
                "pagador": "outro_fin",
                "data_prevista_ressarcimento": "2026-05-20",
            },
        )

        self.assertEqual(response.status_code, 302)
        despesa.refresh_from_db()
        participante.refresh_from_db()
        participante.despesa_gerada.refresh_from_db()
        compartilhamento.refresh_from_db()
        self.assertEqual(despesa.descricao, "Internet fibra")
        self.assertEqual(despesa.valor, Decimal("50.00"))
        self.assertEqual(compartilhamento.valor_total, Decimal("120.00"))
        self.assertEqual(compartilhamento.pagador, self.outro_user)
        self.assertEqual(participante.valor, Decimal("70.00"))
        self.assertEqual(participante.despesa_gerada.descricao, "Internet fibra")
        self.assertEqual(participante.despesa_gerada.valor, Decimal("70.00"))

        response_pagar = self.client.post(reverse("financeiro:despesa_marcar_paga", args=[despesa.pk]))
        self.assertEqual(response_pagar.status_code, 302)
        participante.despesa_gerada.refresh_from_db()
        self.assertEqual(participante.despesa_gerada.status, "paga")

    def test_menu_mostra_pendencias_na_aba_de_despesas(self):
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Jantar",
            valor=Decimal("80.00"),
            data=date(2026, 4, 10),
            categoria="Lazer",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("160.00"),
            modo_divisao="igual",
            pagador=self.user,
        )
        ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.outro_user,
            valor=Decimal("80.00"),
            status="pendente",
        )

        self.client.force_login(self.outro_user)
        response = self.client.get(reverse("financeiro:despesa_lista"))

        self.assertContains(response, "Despesas<span class=\"nav-badge\">1</span>", html=True)
        self.assertNotContains(response, 'href="/financeiro/despesas/compartilhadas/"')

    def test_formulario_de_despesa_oculta_campos_de_compartilhamento_por_padrao(self):
        response = self.client.get(reverse("financeiro:despesa_criar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-shared-toggle")
        self.assertContains(response, "data-shared-fields")
        self.assertContains(response, "data-shared-values-field")
        self.assertContains(response, "usuarios-sistema")

    def test_compartilhamento_confirmado_nao_fica_em_destaque_na_lista(self):
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Mercado dividido",
            valor=Decimal("60.00"),
            data=date(2026, 4, 10),
            categoria="Casa",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("120.00"),
            modo_divisao="igual",
            pagador=self.user,
        )
        ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.outro_user,
            valor=Decimal("60.00"),
            status="aceito",
            ressarcimento_confirmado=True,
        )

        self.client.force_login(self.outro_user)
        response = self.client.get(reverse("financeiro:despesa_lista"))

        self.assertNotContains(response, "Compartilhadas com você")
        self.assertNotContains(response, "Mercado dividido")

    def test_recusa_notifica_criador_e_edicao_reenvia_convite(self):
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Conta dividida",
            valor=Decimal("50.00"),
            data=date(2026, 4, 10),
            categoria="Casa",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("100.00"),
            modo_divisao="igual",
            pagador=self.user,
        )
        participante = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.outro_user,
            valor=Decimal("50.00"),
            status="pendente",
        )

        self.client.force_login(self.outro_user)
        response_recusa = self.client.post(reverse("financeiro:despesa_compartilhada_recusar", args=[participante.pk]))
        self.assertEqual(response_recusa.status_code, 302)
        participante.refresh_from_db()
        compartilhamento.refresh_from_db()
        self.assertEqual(participante.status, "recusado")
        self.assertEqual(compartilhamento.recusado_por, self.outro_user)

        self.client.force_login(self.user)
        response_lista = self.client.get(reverse("financeiro:despesa_lista"))
        self.assertContains(response_lista, "Despesas<span class=\"nav-badge\">1</span>", html=True)
        self.assertContains(response_lista, "shared-status-recusado")
        self.assertContains(response_lista, "Recusado")
        self.assertContains(response_lista, "outro_fin recusou o compartilhamento.")
        self.assertContains(response_lista, "Editar e reenviar")
        self.assertContains(response_lista, "Excluir")

        response_edicao = self.client.post(
            reverse("financeiro:despesa_editar", args=[despesa.pk]),
            {
                "tipo": "variavel",
                "descricao": "Conta dividida ajustada",
                "valor": "120,00",
                "data": "2026-04-10",
                "competencia": "2026-04",
                "categoria": "Casa",
                "status": "pendente",
                "observacoes": "",
                "compartilhar": "on",
                "participantes": "outro_fin",
                "modo_divisao": "igual",
                "pagador": "fin_view",
            },
        )

        self.assertEqual(response_edicao.status_code, 302)
        participante.refresh_from_db()
        compartilhamento.refresh_from_db()
        self.assertEqual(participante.status, "pendente")
        self.assertEqual(participante.valor, Decimal("60.00"))
        self.assertIsNone(compartilhamento.recusado_por)

    def test_recusa_de_um_participante_recusa_para_todos(self):
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Pizza compartilhada",
            valor=Decimal("30.00"),
            data=date(2026, 4, 10),
            categoria="Lazer",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("90.00"),
            modo_divisao="igual",
            pagador=self.user,
        )
        recusador = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.outro_user,
            valor=Decimal("30.00"),
            status="pendente",
        )
        outro_participante = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.terceiro_user,
            valor=Decimal("30.00"),
            status="pendente",
        )

        self.client.force_login(self.outro_user)
        response_recusa = self.client.post(reverse("financeiro:despesa_compartilhada_recusar", args=[recusador.pk]))

        self.assertEqual(response_recusa.status_code, 302)
        recusador.refresh_from_db()
        outro_participante.refresh_from_db()
        compartilhamento.refresh_from_db()
        self.assertEqual(recusador.status, "recusado")
        self.assertEqual(outro_participante.status, "recusado")
        self.assertEqual(compartilhamento.recusado_por, self.outro_user)

        self.client.force_login(self.terceiro_user)
        response_terceiro = self.client.get(reverse("financeiro:despesa_lista"))

        self.assertContains(response_terceiro, "outro_fin recusou o compartilhamento.")
        self.assertContains(response_terceiro, "Pizza compartilhada")

    def test_aceite_parcial_de_multiplos_participantes_fica_aguardando(self):
        despesa = Despesa.objects.create(
            tipo="variavel",
            descricao="Hospedagem",
            valor=Decimal("100.00"),
            data=date(2026, 4, 10),
            categoria="Viagem",
            status="pendente",
            criado_por=self.user,
        )
        compartilhamento = CompartilhamentoDespesa.objects.create(
            despesa=despesa,
            criado_por=self.user,
            valor_total=Decimal("300.00"),
            modo_divisao="igual",
            pagador=self.user,
        )
        participante_1 = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.outro_user,
            valor=Decimal("100.00"),
            status="pendente",
        )
        participante_2 = ParticipanteCompartilhamentoDespesa.objects.create(
            compartilhamento=compartilhamento,
            usuario=self.terceiro_user,
            valor=Decimal("100.00"),
            status="pendente",
        )

        self.client.force_login(self.outro_user)
        self.client.post(reverse("financeiro:despesa_compartilhada_aceitar", args=[participante_1.pk]))
        participante_1.refresh_from_db()
        compartilhamento.refresh_from_db()

        self.assertEqual(compartilhamento.status_geral, "aguardando")
        self.assertIsNone(participante_1.despesa_gerada)
        self.client.force_login(self.user)
        response_criador = self.client.get(reverse("financeiro:despesa_lista"))
        self.assertContains(response_criador, "Aguardando")

        self.client.force_login(self.terceiro_user)
        self.client.post(reverse("financeiro:despesa_compartilhada_aceitar", args=[participante_2.pk]))
        participante_1.refresh_from_db()
        participante_2.refresh_from_db()
        compartilhamento.refresh_from_db()

        self.assertEqual(compartilhamento.status_geral, "aceito")
        self.assertIsNotNone(participante_1.despesa_gerada)
        self.assertIsNotNone(participante_2.despesa_gerada)

    def test_lista_filtra_apenas_despesas_compartilhadas(self):
        Despesa.objects.create(
            tipo="variavel",
            descricao="Padaria comum",
            valor=Decimal("30.00"),
            data=date(2026, 4, 10),
            status="pendente",
            criado_por=self.user,
        )
        compartilhada = Despesa.objects.create(
            tipo="variavel",
            descricao="Assinatura dividida",
            valor=Decimal("40.00"),
            data=date(2026, 4, 11),
            status="pendente",
            criado_por=self.user,
        )
        CompartilhamentoDespesa.objects.create(
            despesa=compartilhada,
            criado_por=self.user,
            valor_total=Decimal("80.00"),
            modo_divisao="igual",
            pagador=self.user,
        )

        response = self.client.get(reverse("financeiro:despesa_lista"), {"compartilhamento": "compartilhadas"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assinatura dividida")
        self.assertNotContains(response, "Padaria comum")
        self.assertContains(response, '<option value="compartilhadas" selected>Compartilhadas</option>', html=False)

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
