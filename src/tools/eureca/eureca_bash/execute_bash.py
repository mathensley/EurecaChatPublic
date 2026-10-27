"""Execução de comandos do agente em uma microVM descartável."""

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path
from uuid import uuid4

from microsandbox import ExecTimeoutError, Network, PullPolicy, Sandbox, SecurityProfile, Volume

from langchain_core.runnables import RunnableConfig

from ..emit_front import emit_front
from .workdir import (
    _extrai_exports_dir,
    _extrai_sandbox_dir,
    criar_url_download,
    finalizar_execucao,
    registrar_execucao,
)

SANDBOX_IMAGE = "eureca-sandbox:0.1.0"
COMMAND_TIMEOUT_SECONDS = 120
SANDBOX_MAX_DURATION_SECONDS = 180
logger = logging.getLogger("tool")


async def _publicar_arquivos_gerados(work_dir: str, config: RunnableConfig) -> list[dict]:
    """Publica somente CSVs e PDFs do workspace na área de downloads."""
    sandbox_dir = Path(work_dir).resolve()
    exports_dir = Path(await _extrai_exports_dir(config))
    publicados = []

    prefixos = {".csv": "eureca_csv_", ".pdf": "eureca_pdf_"}
    for origem in sorted(sandbox_dir.iterdir()):
        extensao = origem.suffix.lower()
        if extensao not in prefixos or origem.is_symlink() or not origem.is_file():
            continue

        nome_seguro = "".join(
            caractere if caractere.isalnum() or caractere in {".", "-", "_"} else "_"
            for caractere in origem.name
        )
        nome_arquivo = f"{prefixos[extensao]}{nome_seguro}"
        destino = exports_dir / nome_arquivo
        shutil.copyfile(origem, destino)
        destino.chmod(0o600)
        publicados.append(
            {
                "tipo": "arquivo",
                "nome_arquivo": nome_arquivo,
                "extensao": extensao,
                "url_download": criar_url_download(exports_dir.parent, nome_arquivo),
            }
        )

    return publicados


def _resultado_erro(mensagem: str) -> str:
    return json.dumps(
        {
            "stdout": "",
            "stderr": mensagem,
            "returncode": -1,
            "sucesso": False,
            "arquivos_publicados": [],
        },
        ensure_ascii=False,
    )


async def execute_bash(config: RunnableConfig, comando: str) -> str:
    """
    Executa um comando shell restrito ao diretório de trabalho do projeto
    e retorna o resultado estruturado. Você pode usar para criar codigo python para
    manipular CSVs através de comando bash ou usar comandos bash em geral.

    Para gerar PDFs, escreva um script Python usando a biblioteca
    reportlab e execute-o com esta mesma ferramenta (não existe uma
    ferramenta separada para PDF). O módulo `/skills/pdf_helpers.py` já está
    disponível para import (cuida de tipografia, tabelas, cores e rodapé
    numerado) — consulte a skill "/skills/geracao_pdf.md" dentro do diretório skills
    para o fluxo recomendado e exemplos antes de escrever o script do zero (siga as instruções).
    CSVs gerados anteriormente ficam disponíveis em /exports, somente leitura;
    use esse caminho para ler o arquivo completo, não a URL /downloads.
    Grave scripts e arquivos de saída em /workspace (ou em caminhos relativos,
    pois o diretório atual é /workspace). Esse diretório persiste entre chamadas
    da tool; /tmp é descartado com a microVM. PDFs e CSVs criados na raiz de
    /workspace são publicados automaticamente. Não grave em /exports nem use
    /home/oai/share, que não faz parte deste ambiente.
    Além disso, você também pode usar a biblioteca matplotlib para gerar gráficos e salvar
    como imagens, que podem ser incluídas no PDF.
    Arquivos enviados como imagens, CSVs e PDFs pelo usuário estão dentro do subdiretório privado
    em .attachments/ e você pode lê-los caso necessário.

    Args:
        comando (str): Comando a ser executado no shell (ex: "ls -la", "python3 teste.py").

    Returns:
        str: JSON com stdout, stderr, returncode, sucesso e arquivos_publicados.
    """
    try:
        work_dir = await _extrai_sandbox_dir(config)
        exports_dir = await _extrai_exports_dir(config)
    except (ValueError, RuntimeError, OSError) as exc:
        return _resultado_erro(str(exc))

    registrar_execucao(work_dir)
    nome_sandbox = f"eureca-{uuid4().hex}"
    log_extra = {"thread_id": config.get("configurable", {}).get("thread_id"), "sandbox_id": nome_sandbox}

    try:
        await emit_front(config=config, mensagem="Executando script")
        
        async with asyncio.timeout(SANDBOX_MAX_DURATION_SECONDS + 30):
            async with await Sandbox.create(
                nome_sandbox,
                image=SANDBOX_IMAGE,
                pull_policy=PullPolicy.NEVER,
                cpus=1,
                memory=1024,
                workdir="/workspace",
                security=SecurityProfile.RESTRICTED,
                network=Network.none(),
                max_duration=SANDBOX_MAX_DURATION_SECONDS,
                ephemeral=True,
                env={
                    "HOME": "/workspace",
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "PYTHONPATH": "/skills",
                    "MPLBACKEND": "Agg",
                },
                volumes={
                    "/workspace": Volume.bind(work_dir, nosuid=True, nodev=True),
                    "/exports": Volume.bind(exports_dir, readonly=True, noexec=True, nosuid=True, nodev=True),
                },
            ) as sandbox:
                inicio = time.monotonic()
                logger.info("sandbox_created", extra=log_extra)
                saida = await sandbox.exec("bash", ["-c", comando], cwd="/workspace", timeout=COMMAND_TIMEOUT_SECONDS)
            logger.info("sandbox_removed", extra={**log_extra, "elapsed_ms": round((time.monotonic() - inicio) * 1000)})

        resultado = {
            "stdout": saida.stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": saida.stderr_bytes.decode("utf-8", errors="replace"),
            "returncode": saida.exit_code,
            "sucesso": saida.exit_code == 0,
            "arquivos_publicados": [],
        }
        if resultado["sucesso"]:
            resultado["arquivos_publicados"] = await _publicar_arquivos_gerados(work_dir, config)
        return json.dumps(resultado, ensure_ascii=False)
    except ExecTimeoutError:
        return _resultado_erro(f"Comando excedeu o tempo limite ({COMMAND_TIMEOUT_SECONDS}s)")
    except TimeoutError:
        return _resultado_erro("A inicialização ou execução do sandbox excedeu o tempo limite")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return _resultado_erro(str(exc))
    finally:
        finalizar_execucao(work_dir)
