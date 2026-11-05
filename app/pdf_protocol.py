"""Protocolo binário limitado entre a API e o leitor isolado."""

import json
import socket
import struct

MAX_PDF_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
SOCKET_PATH = "/run/walleturbo-parser/pdf.sock"


def receive_exact(stream, length):
    chunks = bytearray()
    while len(chunks) < length:
        chunk = stream.recv(min(length - len(chunks), 65536))
        if not chunk:
            raise ValueError("Mensagem incompleta")
        chunks.extend(chunk)
    return bytes(chunks)


def read_packet(stream, maximum):
    length = struct.unpack("!I", receive_exact(stream, 4))[0]
    if length > maximum:
        raise ValueError("Mensagem excessiva")
    return receive_exact(stream, length)


def send_packet(stream, data):
    stream.sendall(struct.pack("!I", len(data)) + data)


def extract_isolated(content):
    if len(content) > MAX_PDF_BYTES:
        raise ValueError("Arquivo excede 2 MB")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(12)
        connection.connect(SOCKET_PATH)
        send_packet(connection, content)
        response = read_packet(connection, MAX_RESPONSE_BYTES)
    return json.loads(response)
