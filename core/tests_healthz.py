"""Sonda /healthz/: 200 com banco e cache de pé, 503 quando um deles cai."""

from unittest import mock

from django.core.cache import cache
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from core import healthz as modulo

TOKEN = "segredo-monitoramento"


class HealthzTests(TestCase):
    def test_200_com_banco_e_cache_ok(self):
        resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 200)
        self.assertJSONEqual(resposta.content, {"status": "ok"})
        self.assertIn("no-cache", resposta.headers.get("Cache-Control", ""))

    def test_503_quando_o_banco_falha(self):
        with (
            mock.patch.object(
                modulo.connection, "cursor", side_effect=OperationalError("banco fora")
            ),
            self.assertLogs("core.healthz", level="ERROR") as logs,
        ):
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 503)
        self.assertJSONEqual(resposta.content, {"status": "indisponivel"})
        self.assertIn("banco", logs.output[0])

    def test_503_quando_o_cache_falha(self):
        with (
            mock.patch.object(cache, "set", side_effect=ConnectionError("redis fora")),
            self.assertLogs("core.healthz", level="ERROR") as logs,
        ):
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 503)
        self.assertIn("cache", logs.output[0])

    def test_503_quando_o_cache_nao_devolve_o_valor(self):
        with (
            mock.patch.object(cache, "get", return_value=None),
            self.assertLogs("core.healthz", level="ERROR"),
        ):
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 503)

    @override_settings(HEALTHZ_TOKEN=TOKEN)
    def test_404_sem_token_e_sem_tocar_no_banco(self):
        with mock.patch.object(modulo, "_banco") as banco:
            resposta = self.client.get(reverse("healthz"))

        self.assertEqual(resposta.status_code, 404)
        banco.assert_not_called()

    @override_settings(HEALTHZ_TOKEN=TOKEN)
    def test_token_correto_ainda_checa_o_banco(self):
        with (
            mock.patch.object(
                modulo.connection, "cursor", side_effect=OperationalError("banco fora")
            ),
            self.assertLogs("core.healthz", level="ERROR"),
        ):
            resposta = self.client.get(reverse("healthz"), HTTP_X_HEALTHZ_TOKEN=TOKEN)

        self.assertEqual(resposta.status_code, 503)

    def test_post_nao_e_permitido(self):
        self.assertEqual(self.client.post(reverse("healthz")).status_code, 405)
