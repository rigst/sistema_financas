import os
from io import BytesIO
from pathlib import Path

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from PIL import ImageOps

from core.concurrency import OptimisticLockModelFormMixin
from core.form_fields import configurar_campo_mascarado
from core.formatting import formatar_cep_br, formatar_cpf_cnpj_br, formatar_telefone_br
from core.validators import (
    validar_cep_basico,
    validar_cpf_cnpj_basico,
    validar_telefone_basico,
    validar_uf,
)
from .models import ConfiguracaoEmpresa


class ConfiguracaoEmpresaForm(OptimisticLockModelFormMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoEmpresa
        fields = [
            "nome_empresa",
            "nome_fantasia",
            "cpf_cnpj",
            "email",
            "telefone",
            "site",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "dados_bancarios",
            "chave_pix",
            "validade_padrao_proposta",
            "assinatura_nome",
            "assinatura_cargo",
            "assinatura_contato",
            "texto_institucional_memorial",
            "rodape_relatorio",
            "logo",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ativo"].widget = forms.HiddenInput()
        self.fields["ativo"].initial = True if not getattr(self.instance, "pk", None) else self.instance.ativo
        self.fields["nome_empresa"].error_messages["required"] = "Informe o nome da empresa."
        configurar_campo_mascarado(self, "cpf_cnpj", "cpf_cnpj", placeholder="00.000.000/0000-00")
        configurar_campo_mascarado(self, "telefone", "phone", placeholder="(00) 00000-0000")
        configurar_campo_mascarado(self, "cep", "cep", placeholder="00000-000")
        self.fields["estado"].widget.attrs["data-force-uppercase"] = "1"
        self.fields["rodape_relatorio"].widget.attrs["rows"] = 3
        self.fields["dados_bancarios"].widget.attrs["rows"] = 3
        self.fields["texto_institucional_memorial"].widget.attrs["rows"] = 4

    def clean_nome_empresa(self):
        valor = (self.cleaned_data.get("nome_empresa") or "").strip()
        if not valor:
            raise forms.ValidationError("Informe o nome da empresa.")
        return valor

    def clean_cpf_cnpj(self):
        valor = (self.cleaned_data.get("cpf_cnpj") or "").strip()
        validar_cpf_cnpj_basico(valor)
        return formatar_cpf_cnpj_br(valor)

    def clean_telefone(self):
        valor = (self.cleaned_data.get("telefone") or "").strip()
        validar_telefone_basico(valor, campo="Telefone")
        return formatar_telefone_br(valor)

    def clean_cep(self):
        valor = (self.cleaned_data.get("cep") or "").strip()
        validar_cep_basico(valor)
        return formatar_cep_br(valor)

    def clean_estado(self):
        valor = (self.cleaned_data.get("estado") or "").strip().upper()
        validar_uf(valor)
        return valor

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo

        max_bytes = max(int(os.getenv("DJANGO_MAX_LOGO_UPLOAD_BYTES", str(2 * 1024 * 1024))), 1)
        if logo.size > max_bytes:
            raise forms.ValidationError("Logo excede o tamanho máximo permitido (2 MB).")

        max_width = max(int(os.getenv("DJANGO_MAX_LOGO_WIDTH", "2000")), 64)
        max_height = max(int(os.getenv("DJANGO_MAX_LOGO_HEIGHT", "2000")), 64)

        try:
            with Image.open(logo) as imagem:
                formato = (imagem.format or "").upper()
                imagem = ImageOps.exif_transpose(imagem)
                imagem.load()

                if formato not in {"PNG", "JPEG", "WEBP"}:
                    raise forms.ValidationError("Formato de logo inválido. Use PNG, JPEG ou WEBP.")

                imagem.thumbnail((max_width, max_height))
                if formato == "JPEG":
                    imagem = imagem.convert("RGB")

                buffer = BytesIO()
                save_kwargs = {"optimize": True}
                extensao = ".png"
                content_type = "image/png"

                if formato == "JPEG":
                    save_kwargs["quality"] = 88
                    extensao = ".jpg"
                    content_type = "image/jpeg"
                elif formato == "WEBP":
                    save_kwargs["quality"] = 88
                    extensao = ".webp"
                    content_type = "image/webp"

                imagem.save(buffer, format=formato, **save_kwargs)
                conteudo = buffer.getvalue()
        except forms.ValidationError:
            raise
        except Exception as exc:
            raise forms.ValidationError("Envie uma imagem válida para o logo.") from exc

        if len(conteudo) > max_bytes:
            raise forms.ValidationError("Logo excede o tamanho máximo permitido após processamento.")

        nome_base = Path(getattr(logo, "name", "logo")).stem or "logo"
        return SimpleUploadedFile(
            name=f"{nome_base}{extensao}",
            content=conteudo,
            content_type=content_type,
        )
