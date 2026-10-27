"""Armazenamento seguro dos anexos recebidos no sandbox da conversa."""

import asyncio
import base64
import binascii
import os
from pathlib import Path
from uuid import uuid4

from src.tools.eureca.eureca_bash.workdir import _extrai_sandbox_dir


MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_BASE64_CHARS = 7_000_000
ALLOWED_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".csv",
    ".txt",
    ".json",
    ".xlsx",
)


def _validar_nome_arquivo(filename: object) -> str:
    nome = str(filename or "").strip()
    if (
        not nome
        or "\x00" in nome
        or "/" in nome
        or "\\" in nome
        or Path(nome).name != nome
    ):
        raise ValueError("Nome de arquivo inválido.")

    extensao = Path(nome).suffix.lower()
    if extensao not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValueError(f"Formato de arquivo não permitido: {extensao or '(sem extensão)'}.")
    return nome


def _decodificar_conteudo(content: str) -> bytes:
    valor = content.strip()
    if valor.startswith("data:") and "," in valor:
        valor = valor.split(",", 1)[1]
    if len(valor) > MAX_ATTACHMENT_BASE64_CHARS:
        raise ValueError("Arquivo maior que o limite permitido.")

    try:
        dados = base64.b64decode(valor, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Conteúdo Base64 inválido.") from exc

    if not dados:
        raise ValueError("Arquivo vazio.")
    if len(dados) > MAX_ATTACHMENT_BYTES:
        raise ValueError("Arquivo maior que o limite permitido.")
    return dados


def _nome_disponivel(sandbox_dir: Path, filename: str) -> Path:
    destino = sandbox_dir / filename
    if not destino.exists() and not destino.is_symlink():
        return destino

    caminho = Path(filename)
    return sandbox_dir / f"{caminho.stem}_{uuid4().hex[:8]}{caminho.suffix}"


def _salvar_arquivos(sandbox_dir: Path, arquivos: list[dict]) -> list[dict]:
    anexos_dir = sandbox_dir / ".attachments"
    anexos_dir.mkdir(exist_ok=True)
    anexos_dir.chmod(0o700)
    salvos = []
    try:
        for arquivo in arquivos:
            nome_original = _validar_nome_arquivo(arquivo.get("filename"))
            content = arquivo.get("content")
            if not isinstance(content, str):
                raise ValueError(f"Conteúdo inválido para {nome_original}.")

            dados = _decodificar_conteudo(content)
            destino = _nome_disponivel(anexos_dir, nome_original)
            temporario = anexos_dir / f".upload_{uuid4().hex}.tmp"
            try:
                temporario.write_bytes(dados)
                temporario.chmod(0o600)
                os.replace(temporario, destino)
                destino.chmod(0o600)
            finally:
                temporario.unlink(missing_ok=True)

            salvos.append(
                {
                    "nome_original": nome_original,
                    "nome_salvo": destino.name,
                    "caminho_workspace": f"/workspace/.attachments/{destino.name}",
                    "tamanho": len(dados),
                }
            )
    except Exception:
        for arquivo_salvo in salvos:
            (anexos_dir / arquivo_salvo["nome_salvo"]).unlink(missing_ok=True)
        raise

    return salvos


async def salvar_arquivos_no_sandbox(
    thread_id: str,
    arquivos: list[dict],
) -> list[dict]:
    """Decodifica e salva anexos no sandbox privado da conversa."""
    if not thread_id:
        raise ValueError("A conversa não possui um identificador válido.")

    sandbox_dir = Path(
        await _extrai_sandbox_dir(
            {"configurable": {"thread_id": str(thread_id)}}
        )
    )
    return await asyncio.to_thread(_salvar_arquivos, sandbox_dir, arquivos)
