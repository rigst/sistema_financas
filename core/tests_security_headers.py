"""Cabeçalhos de segurança aplicados por core.security_headers."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.testing import SENHA_TESTE

POLITICA_PADRAO = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
CABECALHO = "Permissions-Policy"


class PermissionsPolicyTests(TestCase):
    def test_padrao_nega_recursos_que_o_app_nao_usa(self):
        from django.conf import settings

        self.assertEqual(settings.PERMISSIONS_POLICY, POLITICA_PADRAO)

    def test_rota_publica_tem_o_cabecalho(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    def test_login_tem_o_cabecalho(self):
        resposta = self.client.get("/login/")

        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    def test_admin_tem_o_cabecalho(self):
        get_user_model().objects.create_superuser(
            username="admin-pp", email="admin-pp@example.com", password=SENHA_TESTE
        )
        self.client.login(username="admin-pp", password=SENHA_TESTE)

        resposta = self.client.get("/admin/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    @override_settings(ENABLE_CSP=False)
    def test_vale_mesmo_com_a_csp_desligada(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.headers.get(CABECALHO), POLITICA_PADRAO)

    @override_settings(PERMISSIONS_POLICY="camera=(self)")
    def test_valor_vem_do_settings(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.headers.get(CABECALHO), "camera=(self)")

    @override_settings(PERMISSIONS_POLICY="")
    def test_vazio_desliga_o_cabecalho(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertNotIn(CABECALHO, resposta.headers)
