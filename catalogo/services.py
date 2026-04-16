from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import logging
import os
from time import monotonic
import unicodedata
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CategoriaItem, ItemCatalogo


XLSX_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DUAS_CASAS = Decimal("0.01")
COLUNAS_IMPORTACAO = 6
MAX_XLSX_ENTRADAS = 200
MAX_XLSX_RAZAO_COMPRESSAO = 100
MAX_XLSX_DESCOMPACTADO_BYTES = 20 * 1024 * 1024
MAX_XLSX_IMPORT_ROWS = 5000
MAX_XLSX_NON_EMPTY_CELLS = 30000
MAX_XLSX_PARSE_SECONDS = 15

logger = logging.getLogger(__name__)


def _texto_planilha(shared_strings, cell):
    cell_type = cell.attrib.get("t")
    value = cell.findtext("main:v", default="", namespaces=XLSX_NS)
    if cell_type == "s" and value:
        return shared_strings[int(value)]
    if cell_type == "inlineStr":
        return "".join(cell.itertext()).strip()
    return value.strip()


def _carregar_shared_strings(zip_file):
    if "xl/sharedStrings.xml" not in zip_file.namelist():
        return []
    root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    strings = []
    for si in root.findall("main:si", XLSX_NS):
        strings.append("".join(si.itertext()).strip())
    return strings


def _indice_coluna(ref):
    letras = "".join(char for char in str(ref or "") if char.isalpha()).upper()
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return max(indice - 1, 0)


def _linhas_xlsx(arquivo):
    try:
        conteudo = arquivo.read()
        max_upload_bytes = max(int(os.getenv("DJANGO_MAX_CATALOGO_UPLOAD_BYTES", str(5 * 1024 * 1024))), 1)
        if len(conteudo) > max_upload_bytes:
            raise ValueError("Arquivo .xlsx excede o tamanho máximo permitido.")

        with ZipFile(BytesIO(conteudo)) as zip_file:
            _validar_zip_xlsx_seguro(zip_file)
            shared_strings = _carregar_shared_strings(zip_file)
            workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
            rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
            first_sheet = workbook.find("main:sheets/main:sheet", XLSX_NS)
            if first_sheet is None:
                raise ValueError("A planilha não possui abas.")
            relationship_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = None
            for rel in rels:
                if rel.attrib.get("Id") == relationship_id:
                    target = rel.attrib.get("Target")
                    break
            if not target:
                raise ValueError("Não foi possível localizar a primeira aba da planilha.")
            if ".." in target:
                raise ValueError("A aba principal da planilha é inválida.")

            sheet_path = target.lstrip("/")
            if not sheet_path.startswith("xl/"):
                sheet_path = f"xl/{sheet_path}"
            if sheet_path not in zip_file.namelist():
                raise ValueError("A primeira aba da planilha não foi encontrada no arquivo.")

            sheet = ET.fromstring(zip_file.read(sheet_path))
            total_linhas = 0
            total_celulas_nao_vazias = 0
            inicio_parse = monotonic()
            limite_segundos = max(int(os.getenv("DJANGO_MAX_XLSX_PARSE_SECONDS", str(MAX_XLSX_PARSE_SECONDS))), 1)
            limite_celulas = max(int(os.getenv("DJANGO_MAX_XLSX_NON_EMPTY_CELLS", str(MAX_XLSX_NON_EMPTY_CELLS))), 10)
            for row in sheet.findall("main:sheetData/main:row", XLSX_NS):
                if monotonic() - inicio_parse > limite_segundos:
                    raise ValueError("A planilha demorou além do permitido para processar.")
                total_linhas += 1
                if total_linhas > MAX_XLSX_IMPORT_ROWS:
                    raise ValueError(f"A planilha excede o limite de {MAX_XLSX_IMPORT_ROWS} linhas.")
                cells = [""] * COLUNAS_IMPORTACAO
                for cell in row.findall("main:c", XLSX_NS):
                    indice = _indice_coluna(cell.attrib.get("r"))
                    if indice >= COLUNAS_IMPORTACAO:
                        continue
                    cells[indice] = _texto_planilha(shared_strings, cell)
                total_celulas_nao_vazias += sum(1 for valor in cells if valor)
                if total_celulas_nao_vazias > limite_celulas:
                    raise ValueError("A planilha excede o limite de células preenchidas.")
                yield cells
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Envie um arquivo .xlsx válido.") from exc


def _validar_zip_xlsx_seguro(zip_file):
    informacoes = zip_file.infolist()
    if len(informacoes) > MAX_XLSX_ENTRADAS:
        raise ValueError("Arquivo .xlsx inválido: número de entradas acima do permitido.")

    total_descompactado = 0
    for info in informacoes:
        total_descompactado += info.file_size
        if total_descompactado > MAX_XLSX_DESCOMPACTADO_BYTES:
            raise ValueError("Arquivo .xlsx inválido: conteúdo descompactado muito grande.")

        if info.compress_size <= 0 and info.file_size > 0:
            raise ValueError("Arquivo .xlsx inválido: entrada compactada inconsistente.")

        if info.compress_size > 0:
            razao = info.file_size / info.compress_size
            if razao > MAX_XLSX_RAZAO_COMPRESSAO:
                raise ValueError("Arquivo .xlsx inválido: taxa de compressão suspeita.")


def _decimal(valor):
    texto = str(valor or "").strip()
    if not texto:
        return Decimal("0.00")
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto:
        if "." in texto:
            normalizado = texto.replace(".", "").replace(",", ".")
        else:
            normalizado = texto.replace(",", ".")
    else:
        normalizado = texto
    try:
        return Decimal(normalizado).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Valor inválido na importação: {valor}") from exc


def _slug_unidade(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").strip())
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return texto.casefold().replace(" ", "").replace(".", "")


def _normalizar_unidade(unidade):
    unidade_original = str(unidade or "").strip()
    unidade_slug = _slug_unidade(unidade_original)

    unidades = {
        "": "un",
        "-": "-",
        "un": "un",
        "unid": "un",
        "unidade": "un",
        "unidades": "un",
        "hr": "hr",
        "hora": "hr",
        "horas": "hr",
        "dia": "dia",
        "diaria": "dia",
        "diarias": "dia",
        "m": "m",
        "metro": "m",
        "metros": "m",
        "m2": "m2",
        "m²": "m2",
        "metroquadrado": "m2",
        "metrosquadrados": "m2",
        "m3": "m3",
        "m³": "m3",
        "metrocubico": "m3",
        "metroscubicos": "m3",
        "kg": "kg",
        "quilo": "kg",
        "quilos": "kg",
        "cx": "cx",
        "caixa": "cx",
        "caixas": "cx",
        "pct": "pct",
        "pacote": "pct",
        "pacotes": "pct",
        "sv": "sv",
        "servico": "sv",
        "servicos": "sv",
        "serviço": "sv",
        "serviços": "sv",
    }
    unidade_normalizada = unidades.get(unidade_slug) or unidades.get(unidade_original.casefold())
    if unidade_normalizada:
        return unidade_normalizada
    raise ValueError(f"Unidade inválida na importação: {unidade_original}")


def exportar_catalogo_excel(itens) -> bytes:
    linhas_itens = []
    itens_iteraveis = itens.select_related("categoria") if hasattr(itens, "select_related") else itens
    for item in itens_iteraveis:
        linhas_itens.append(
            f"""
            <Row>
                <Cell><Data ss:Type="String">{escape(item.categoria.nome if item.categoria else "")}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.nome)}</Data></Cell>
                <Cell><Data ss:Type="Number">{item.valor_unitario_padrao}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.unidade_medida)}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.descricao_padrao or "")}</Data></Cell>
                <Cell><Data ss:Type="String">{escape(item.observacoes or "")}</Data></Cell>
            </Row>
            """
        )

    xml = f"""<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Header">
   <Font ss:Bold="1"/>
   <Interior ss:Color="#DCE9FF" ss:Pattern="Solid"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="Catalogo">
  <Table>
   <Row ss:StyleID="Header">
    <Cell><Data ss:Type="String">CATEGORIA</Data></Cell>
    <Cell><Data ss:Type="String">ITEM</Data></Cell>
    <Cell><Data ss:Type="String">VALOR</Data></Cell>
    <Cell><Data ss:Type="String">UNIDADE</Data></Cell>
    <Cell><Data ss:Type="String">DESCRIÇÃO</Data></Cell>
    <Cell><Data ss:Type="String">OBSERVAÇÃO</Data></Cell>
   </Row>
   {''.join(linhas_itens)}
  </Table>
 </Worksheet>
</Workbook>
"""
    return xml.encode("utf-8")


def _formatar_erro_validacao(exc):
    if hasattr(exc, "message_dict"):
        mensagens = []
        for campo, erros in exc.message_dict.items():
            rotulo = campo.replace("_", " ")
            mensagens.extend(f"{rotulo}: {erro}" for erro in erros)
        return "; ".join(mensagens)
    if hasattr(exc, "messages"):
        return "; ".join(exc.messages)
    return str(exc)


def importar_catalogo_excel(arquivo, empresa):
    iter_linhas = _linhas_xlsx(arquivo)
    try:
        next(iter_linhas)
    except StopIteration as exc:
        raise ValueError("A planilha precisa ter cabeçalho e ao menos uma linha de dados.") from exc

    categorias_cache = {
        categoria.nome.strip().casefold(): categoria
        for categoria in CategoriaItem.objects.filter(empresa=empresa)
    }
    categorias_criadas = 0
    itens_criados = 0
    teve_linha_de_dados = False

    try:
        with transaction.atomic():
            for indice, linha in enumerate(iter_linhas, start=2):
                teve_linha_de_dados = True
                valores = list(linha[:6]) + [""] * max(0, 6 - len(linha))
                categoria_nome, item_nome, valor, unidade, descricao, observacao = [str(v or "").strip() for v in valores[:6]]
                campos_preenchidos = [campo for campo in (categoria_nome, item_nome, valor, unidade, descricao, observacao) if campo]

                if len(campos_preenchidos) <= 1:
                    continue
                if not categoria_nome or not item_nome:
                    raise ValueError(f"Linha {indice}: informe categoria e item.")

                chave_categoria = categoria_nome.casefold()
                categoria = categorias_cache.get(chave_categoria)
                if categoria is None:
                    cor = CategoriaItem.COLOR_SEQUENCE[len(categorias_cache) % len(CategoriaItem.COLOR_SEQUENCE)]
                    categoria = CategoriaItem.objects.create(
                        empresa=empresa,
                        nome=categoria_nome,
                        cor=cor,
                        ativo=True,
                    )
                    categorias_cache[chave_categoria] = categoria
                    categorias_criadas += 1

                try:
                    unidade_normalizada = _normalizar_unidade(unidade)
                    valor_normalizado = _decimal(valor)
                except ValueError as exc:
                    raise ValueError(f"Linha {indice}: {exc}") from exc

                item = ItemCatalogo(
                    empresa=empresa,
                    categoria=categoria,
                    nome=item_nome,
                    unidade_medida=unidade_normalizada,
                    valor_unitario_padrao=valor_normalizado,
                    descricao_padrao=descricao,
                    observacoes=observacao,
                    ativo=True,
                )
                try:
                    item.save()
                except ValidationError as exc:
                    raise ValueError(f"Linha {indice}: {_formatar_erro_validacao(exc)}") from exc
                itens_criados += 1
    except ValueError:
        logger.info("Falha de validação ao importar catálogo", extra={"empresa_id": getattr(empresa, "pk", None)})
        raise
    except Exception as exc:
        logger.exception("Erro inesperado na importação de catálogo")
        raise ValueError(
            "Não foi possível concluir a importação. Revise o arquivo e tente novamente."
        ) from exc

    if not teve_linha_de_dados:
        raise ValueError("A planilha precisa ter cabeçalho e ao menos uma linha de dados.")

    return categorias_criadas, itens_criados
