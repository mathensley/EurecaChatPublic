"""Teste local da tool, sem depender do agente ou de serviços externos."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from src.tools.eureca.eureca_bash.execute_bash import execute_bash
from src.tools.eureca.eureca_bash.workdir import _extrai_sandbox_dir, remover_work_dir


async def main() -> None:
    thread_id = f"smoke-{uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id, "callbacks_sio": []}}
    try:
        workspace = Path(await _extrai_sandbox_dir(config))
        anexos = workspace / ".attachments"
        anexos.mkdir(mode=0o700)
        (anexos / "entrada.csv").write_text("coluna\nvalor\n", encoding="utf-8")
        (anexos / "entrada.csv").chmod(0o600)

        comando = (
            "python3 - <<'PY'\n"
            "from pathlib import Path\n"
            "import matplotlib, pandas, reportlab, PIL, fitz\n"
            "print(Path('/skills/geracao_pdf.md').is_file())\n"
            "print(Path('/workspace/.attachments/entrada.csv').read_text().strip())\n"
            "Path('/workspace/teste.csv').write_text('coluna\\nvalor\\n')\n"
            "Path('/workspace/script_persistente.py').write_text('print(42)\\n')\n"
            "Path('/tmp/arquivo_temporario').write_text('descartar')\n"
            "PY"
        )
        primeiro = json.loads(await execute_bash(config, comando))
        assert primeiro["sucesso"], primeiro
        assert "True" in primeiro["stdout"] and "valor" in primeiro["stdout"], primeiro
        assert any(item["nome_arquivo"] == "eureca_csv_teste.csv" for item in primeiro["arquivos_publicados"]), primeiro

        segundo = json.loads(await execute_bash(
            config,
            "test ! -e /tmp/arquivo_temporario && python3 script_persistente.py && cat /exports/eureca_csv_teste.csv",
        ))
        assert segundo["sucesso"] and "42" in segundo["stdout"] and "valor" in segundo["stdout"], segundo

        isolamento = json.loads(await execute_bash(config, "test ! -e /EurecaAI/.env"))
        assert isolamento["sucesso"], isolamento

        so_leitura = json.loads(await execute_bash(
            config,
            "python3 - <<'PY'\n"
            "from pathlib import Path\n"
            "try:\n"
            "    Path('/exports/eureca_csv_teste.csv').write_text('alterado')\n"
            "except OSError:\n"
            "    print('exports bloqueado para escrita')\n"
            "else:\n"
            "    raise SystemExit(1)\n"
            "PY",
        ))
        assert so_leitura["sucesso"] and "bloqueado" in so_leitura["stdout"], so_leitura

        sem_rede = json.loads(await execute_bash(
            config,
            "python3 - <<'PY'\n"
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
            "except OSError:\n"
            "    print('rede bloqueada')\n"
            "else:\n"
            "    raise SystemExit(1)\n"
            "PY",
        ))
        assert sem_rede["sucesso"] and "bloqueada" in sem_rede["stdout"], sem_rede
        print("Smoke test do microsandbox passou.")
    finally:
        await remover_work_dir(thread_id)


if __name__ == "__main__":
    asyncio.run(main())
