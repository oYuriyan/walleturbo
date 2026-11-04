"""Executar somente no serviço parser, sem rede e sem credenciais financeiras."""

import io
import json
import logging
import os
import resource
import signal
import socketserver
import subprocess
import sys
from pathlib import Path
from app.pdf_protocol import (
    MAX_PDF_BYTES,
    MAX_RESPONSE_BYTES,
    SOCKET_PATH,
    read_packet,
    send_packet,
)

MAX_PAGES = 30
MAX_TEXT_CHARS = 100000


def extract(content):
    from pypdf import PdfReader

    logging.getLogger("pypdf").disabled = True
    if not content.startswith(b"%PDF-") or len(content) > MAX_PDF_BYTES:
        return {"error": "invalid_pdf"}
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            return {"error": "encrypted"}
        root = reader.trailer["/Root"]
        names = root.get("/Names", {})
        if hasattr(names, "get_object"):
            names = names.get_object()
        if any(key in root for key in ("/OpenAction", "/AA", "/AcroForm")) or any(
            key in names for key in ("/JavaScript", "/EmbeddedFiles")
        ):
            return {"error": "active_content"}
        if len(reader.pages) > MAX_PAGES:
            return {"error": "too_many_pages"}
        pages, total, empty = [], 0, []
        for number, page in enumerate(reader.pages, 1):
            if "/AA" in page:
                return {"error": "active_content"}
            for reference in page.get("/Annots", []):
                annotation = reference.get_object()
                if any(
                    key in annotation for key in ("/A", "/AA", "/FS")
                ) or annotation.get("/Subtype") in (
                    "/RichMedia",
                    "/FileAttachment",
                    "/Screen",
                ):
                    return {"error": "active_content"}
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_TEXT_CHARS:
                return {"error": "too_complex"}
            if not text.strip():
                empty.append(number)
            pages.append({"page": number, "text": text})
        if not total or all(not p["text"].strip() for p in pages):
            return {"error": "ocr_required"}
        return {"pages": pages, "empty_pages": empty}
    except Exception:
        # Não devolver exceções do parser: podem conter conteúdo do documento.
        return {"error": "invalid_pdf"}


def child():
    resource.setrlimit(resource.RLIMIT_AS, (192 * 1024 * 1024, 192 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    content = sys.stdin.buffer.read(MAX_PDF_BYTES + 1)
    result = extract(content)
    output = json.dumps(result, ensure_ascii=False).encode()
    if len(output) > MAX_RESPONSE_BYTES:
        output = b'{"error":"too_complex"}'
    sys.stdout.buffer.write(output)


def bounded_extract(content):
    process = subprocess.Popen(
        [sys.executable, "-m", "app.pdf_worker", "--extract"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        output, _ = process.communicate(content, timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return b'{"error":"too_complex"}'
    if process.returncode != 0 or len(output) > MAX_RESPONSE_BYTES:
        return b'{"error":"too_complex"}'
    return output


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            content = read_packet(self.request, MAX_PDF_BYTES)
            output = bounded_extract(content)
            send_packet(self.request, output)
        except (OSError, ValueError):
            return


class Server(socketserver.UnixStreamServer):
    request_queue_size = 2

    def handle_error(self, request, client_address):
        # Nenhum dado de PDF ou traceback em logs de produção.
        return


def serve():
    path = Path(SOCKET_PATH)
    if path.exists():
        path.unlink()
    os.umask(0o007)
    with Server(SOCKET_PATH, Handler) as server:
        os.chmod(SOCKET_PATH, 0o660)
        server.serve_forever()


if __name__ == "__main__":
    if "--extract" in sys.argv:
        child()
    else:
        serve()
