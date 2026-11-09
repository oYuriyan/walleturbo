"""Leitor limitado de extratos OFX bancários; sem rede, inferência ou arredondamento."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import unescape
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from app.domain import Entry, suggest_category

MAX_BYTES = 256000
SCHEMA = {
    "OFX": {"SIGNONMSGSRSV1", "BANKMSGSRSV1"},
    "SIGNONMSGSRSV1": {"SONRS"},
    "SONRS": {"STATUS", "DTSERVER", "LANGUAGE", "FI", "INTU.BID"},
    "STATUS": {"CODE", "SEVERITY", "MESSAGE"},
    "FI": {"ORG", "FID"},
    "BANKMSGSRSV1": {"STMTTRNRS"},
    "STMTTRNRS": {"TRNUID", "STATUS", "STMTRS"},
    "STMTRS": {"CURDEF", "BANKACCTFROM", "BANKTRANLIST", "LEDGERBAL", "AVAILBAL"},
    "BANKACCTFROM": {"BANKID", "BRANCHID", "ACCTID", "ACCTTYPE", "ACCTKEY"},
    "BANKTRANLIST": {"DTSTART", "DTEND", "STMTTRN"},
    "STMTTRN": {
        "TRNTYPE",
        "DTPOSTED",
        "DTUSER",
        "DTAVAIL",
        "TRNAMT",
        "FITID",
        "NAME",
        "MEMO",
        "CHECKNUM",
        "REFNUM",
        "SIC",
        "PAYEEID",
        "CORRECTFITID",
        "CORRECTACTION",
    },
    "LEDGERBAL": {"BALAMT", "DTASOF"},
    "AVAILBAL": {"BALAMT", "DTASOF"},
}
TAG = re.compile(r"<(/?)([A-Z][A-Z0-9_.]*)>")
POSTED = re.compile(
    r"(\d{8})(\d{6}(?:\.\d{1,3})?)?(?:\[([+-]?\d{1,2}(?:\.\d{1,2})?)(?::[A-Z]{1,6})?\])?",
    re.ASCII,
)
DEBITS = {"DEBIT", "POS", "CHECK", "FEE", "SRVCHG", "DIRECTDEBIT"}
CREDITS = {"CREDIT", "DEP", "DIRECTDEP", "DIV"}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def unsafe_text(value):
    return "\ufffd" in value or any(
        (ord(c) < 32 and c not in "\r\n\t") or 127 <= ord(c) <= 159 for c in value
    )


def sgml_xml(body):
    output, stack, pending, position = [], [], None, 0
    for match in TAG.finditer(body):
        text = body[position : match.start()]
        closing, tag = match.groups()
        if "<" in text:
            raise ValueError("Marcação OFX não suportada.")
        if pending:
            output.extend([escape(unescape(text.strip())), f"</{pending}>"])
            if closing and tag == pending:
                pending, position = None, match.end()
                continue
            pending = None
        elif text.strip():
            raise ValueError("Texto fora de um campo OFX.")
        if closing:
            if not stack or stack.pop() != tag:
                raise ValueError("Estrutura OFX incompleta ou ambígua.")
            output.append(f"</{tag}>")
        elif tag in SCHEMA:
            stack.append(tag)
            if len(stack) > 24:
                raise ValueError("OFX excede a profundidade permitida.")
            output.append(f"<{tag}>")
        else:
            output.append(f"<{tag}>")
            pending = tag
        position = match.end()
    if stack or pending or body[position:].strip():
        raise ValueError("Estrutura OFX incompleta.")
    return "".join(output)


def tree(content):
    if (
        not content
        or len(content.encode()) > MAX_BYTES
        or "<!" in content
        or unsafe_text(content)
    ):
        raise ValueError(
            "OFX inválido: até 256 KB, sem declarações de entidades, DTD ou caracteres de controle."
        )
    content = content.lstrip("\ufeff \r\n\t")
    if content.startswith("OFXHEADER:"):
        start = content.find("<OFX>")
        if start < 0:
            raise ValueError("Cabeçalho OFX 1.x inválido.")
        headers = {}
        for line in content[:start].splitlines():
            if not line.strip():
                continue
            name, separator, value = line.strip().partition(":")
            if not separator or name in headers:
                raise ValueError("Cabeçalho OFX duplicado ou inválido.")
            headers[name] = value.strip()
        if (
            headers.get("OFXHEADER") != "100"
            or headers.get("DATA") != "OFXSGML"
            or headers.get("VERSION") not in {"102", "103"}
            or headers.get("ENCODING", "UTF-8") not in {"USASCII", "UTF-8"}
            or headers.get("CHARSET", "NONE") not in {"1252", "UTF-8", "NONE"}
            or headers.get("SECURITY", "NONE") != "NONE"
            or headers.get("COMPRESSION", "NONE") != "NONE"
        ):
            raise ValueError("OFX 1.x exige SGML 102/103, sem proteção ou compressão.")
        body, format_name = sgml_xml(content[start:]), "OFX 1.x SGML"
    else:
        while content.startswith("<?"):
            match = re.match(r"<\?(?:xml|OFX)\b[^<>]*\?>\s*", content)
            if not match:
                raise ValueError("Cabeçalho XML OFX inválido.")
            if content.startswith("<?OFX"):
                version = re.search(r'\bVERSION="(\d+)"', match[0])
                if (
                    'OFXHEADER="200"' not in match[0]
                    or 'SECURITY="NONE"' not in match[0]
                ):
                    raise ValueError("Cabeçalho OFX XML exige versão 200 sem proteção.")
                if not version or version[1] not in {
                    "200",
                    "201",
                    "202",
                    "203",
                    "210",
                    "211",
                    "220",
                }:
                    raise ValueError("Versão XML OFX não suportada.")
            else:
                encoding = re.search(
                    r'\bencoding=["\']([^"\']+)["\']', match[0], re.IGNORECASE
                )
                if encoding and encoding[1].lower() not in {
                    "utf-8",
                    "windows-1252",
                    "cp1252",
                }:
                    raise ValueError("Codificação XML OFX não suportada.")
            content = content[match.end() :]
        body, format_name = content, "OFX 2.x XML"
    if "<?" in body or body.count("<") > 20000:
        raise ValueError("OFX excede os limites ou contém instruções não suportadas.")
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise ValueError("OFX malformado. Use o arquivo original do extrato.") from None
    if root.tag != "OFX":
        raise ValueError("O documento não é um extrato OFX.")
    pending = [(root, 1)]
    while pending:
        node, depth = pending.pop()
        if depth > 24 or node.attrib or (node.tail or "").strip():
            raise ValueError("Estrutura OFX não suportada.")
        children, names = list(node), [child.tag for child in node]
        if children:
            if node.tag not in SCHEMA or (node.text or "").strip():
                raise ValueError("Estrutura OFX não suportada.")
            if any(name not in SCHEMA[node.tag] for name in names):
                raise ValueError("Layout OFX fora do formato bancário suportado.")
            for name in set(names):
                if names.count(name) > 1 and (node.tag, name) != (
                    "BANKTRANLIST",
                    "STMTTRN",
                ):
                    raise ValueError(
                        "OFX com contas, respostas ou campos repetidos não é suportado."
                    )
            pending.extend((child, depth + 1) for child in children)
        elif (
            node.tag in SCHEMA
            or len(node.text or "") > 2048
            or unsafe_text(node.text or "")
        ):
            raise ValueError("OFX com estrutura vazia ou campo excessivo.")
    return root, format_name


def field(node, name, required=True, maximum=255):
    value = " ".join((node.findtext(name) or "").split())
    if (required and not value) or len(value) > maximum:
        raise ValueError(f"Campo {name} ausente ou excede o limite suportado.")
    return value


def civil_date(value):
    match = POSTED.fullmatch(value)
    if not match:
        raise ValueError(
            "Data OFX exige AAAAMMDD e horário/fuso válidos quando presentes."
        )
    day, clock, offset = match.groups()
    if offset and not Decimal("-12") <= Decimal(offset) <= Decimal("14"):
        raise ValueError("Fuso OFX fora do intervalo suportado.")
    try:
        parsed = datetime.strptime(
            day + (clock.split(".")[0] if clock else ""),
            "%Y%m%d%H%M%S" if clock else "%Y%m%d",
        ).date()
    except ValueError:
        raise ValueError("Data ou horário OFX inválido.") from None
    if not 1900 <= parsed.year <= 9998:
        raise ValueError("Data OFX fora de 1900–9998.")
    return parsed


@dataclass
class Document:
    format: str
    bank_id: str
    masked_account: str
    entries: list[Entry]
    identities: list[str]
    fingerprints: list[str]


def parse_ofx(content):
    root, format_name = tree(content)
    for status in root.findall(".//STATUS"):
        if field(status, "CODE") != "0" or field(status, "SEVERITY", False) == "ERROR":
            raise ValueError("O OFX informa uma resposta de erro do emissor.")
    response = root.find("BANKMSGSRSV1/STMTTRNRS")
    if response is None or response.find("STATUS") is None:
        raise ValueError("OFX exige uma única resposta de extrato bancário com status.")
    statement = response.find("STMTRS")
    if statement is None or field(statement, "CURDEF") != "BRL":
        raise ValueError("Somente extratos bancários em BRL são suportados.")
    account, transactions = statement.find("BANKACCTFROM"), statement.find(
        "BANKTRANLIST"
    )
    if account is None or transactions is None:
        raise ValueError("Conta bancária ou lista de lançamentos ausente.")
    bank, branch, account_id, account_type = (
        field(account, "BANKID", maximum=64),
        field(account, "BRANCHID", False, 64),
        field(account, "ACCTID", maximum=64),
        field(account, "ACCTTYPE"),
    )
    if account_type not in {"CHECKING", "SAVINGS"}:
        raise ValueError("OFX aceita contas correntes e poupança nesta versão.")
    start, end = civil_date(field(transactions, "DTSTART")), civil_date(
        field(transactions, "DTEND")
    )
    rows = transactions.findall("STMTTRN")
    if start > end or not 1 <= len(rows) <= 500:
        raise ValueError("OFX exige período válido e entre 1 e 500 lançamentos.")
    entries, identities, fingerprints, seen = [], [], [], set()
    for index, row in enumerate(rows, 1):
        identifier = field(row, "FITID")
        if identifier in seen:
            raise ValueError(
                "FITID repetido no arquivo. Reexporte um extrato sem origens ambíguas."
            )
        seen.add(identifier)
        if (
            row.find("CORRECTFITID") is not None
            or row.find("CORRECTACTION") is not None
        ):
            raise ValueError(
                "Comandos de correção OFX exigem revisão externa; não são aplicados automaticamente."
            )
        kind, amount = field(row, "TRNTYPE"), field(row, "TRNAMT")
        if not re.fullmatch(r"[+-]?\d{1,9}(?:\.\d{1,2})?", amount, flags=re.ASCII):
            raise ValueError(
                f"Lançamento {index}: valor OFX inválido, sem arredondamento."
            )
        cents = int(Decimal(amount) * 100)
        if (
            kind not in DEBITS | CREDITS | {"INT"}
            or not cents
            or (kind in DEBITS and cents > 0)
            or (kind in CREDITS and cents < 0)
        ):
            raise ValueError(
                f"Lançamento {index}: tipo/sinal não suportado. Transferências e pagamentos não são inferidos."
            )
        day = civil_date(field(row, "DTPOSTED"))
        if not start <= day <= end:
            raise ValueError(
                f"Lançamento {index}: data fora do período civil declarado."
            )
        description = field(row, "MEMO", False, 160) or field(row, "NAME", maximum=160)
        entry = Entry(
            date=day,
            description=description,
            amount_cents=abs(cents),
            kind="income" if cents > 0 else "expense",
            category="Renda" if cents > 0 else suggest_category(description),
        )
        entries.append(entry)
        identities.append(digest([bank, branch, account_id, account_type, identifier]))
        fingerprints.append(digest([day.isoformat(), cents, kind, description]))
    return Document(
        format_name, bank, "••••" + account_id[-4:], entries, identities, fingerprints
    )
