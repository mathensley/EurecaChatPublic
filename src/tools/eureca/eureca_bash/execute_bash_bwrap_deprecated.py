import json
import asyncio
import os
import shutil
from ..emit_front import emit_front
from .workdir import _extrai_exports_dir, _extrai_sandbox_dir, criar_url_download
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(override=True)

SKILLS_DIR = Path(__file__).resolve().parent.parent / "sandbox_files"


async def _publicar_arquivos_gerados(work_dir: str, config: RunnableConfig) -> list[dict]:
    """Publica somente CSVs e PDFs do sandbox na área de downloads."""
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


def _montar_comando_sandboxed(comando: str, work_dir: str) -> list:
    """
    Monta o comando real a ser executado, envolto em bubblewrap.
    O processo dentro do sandbox só enxerga:
      - /usr, /usr/local, /lib, /lib64, /bin (somente leitura)
      - work_dir montado como /workspace, com escrita liberada
      - exports da conversa montado como /exports, somente leitura
    Sem rede, sem acesso ao resto do filesystem do host.
    """
    comando_com_limites = f"ulimit -u 64 -v 2097152 -f 20480; {comando}"
    montagem_skills = []
    if SKILLS_DIR.is_dir():
        montagem_skills = ["--ro-bind", str(SKILLS_DIR), "/skills"]

    montagem_venv = []
    if Path("/EurecaAI/.venv").is_dir():
        montagem_venv = ["--ro-bind", "/EurecaAI/.venv", "/eureca-venv"]

    exports_dir = Path(work_dir).resolve().parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.chmod(0o700)
    montagem_exports = ["--ro-bind", str(exports_dir), "/exports"]
    
    return [
        "bwrap",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/usr/local", "/usr/local",
        *montagem_venv,
        *montagem_exports,
        *montagem_skills,
        "--bind", work_dir, "/workspace",
        "--chdir", "/workspace",
        "--unshare-all",          # rede + user + ipc + uts, tudo isolado
        "--die-with-parent",
        "--new-session",          # mitiga TIOCSTI injection
        # O Docker bloqueia a criação de uma nova montagem proc sem
        # privileged. Reutilizamos o proc do container somente para leitura.
        "--ro-bind", "/proc", "/proc",
        "--dev", "/dev",
        "--clearenv",             # não herda env do host
        "--setenv", "PATH", "/eureca-venv/bin:/usr/local/bin:/usr/bin:/bin",
        "--setenv", "VIRTUAL_ENV", "/eureca-venv",
        "--setenv", "HOME", "/workspace",
        "--setenv", "PYTHONPATH", "/skills",
        "--cap-drop", "ALL",
        "--uid", "65534", "--gid", "65534",   # nobody, não root
        "bash", "-c", comando_com_limites,
    ]


#@tool
async def execute_bash(config: RunnableConfig, comando):
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
    Além disso, você também pode usar a biblioteca matplotlib para gerar gráficos e salvar 
    como imagens, que podem ser incluídas no PDF.
    Arquivos enviados como imagens, CSVs e PDFs pelo usuário estã dentro do subdiretório privado
    em .attachments/ e que você pode usá-lo e ler os arquivos caso necessário.

    Args:
        comando (str): Comando a ser executado no shell (ex: "ls -la", echo "print('Python rodando!)" > teste.py, python3 teste.py).

    Returns:
        dict: {
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "sucesso": bool,
            "arquivos_publicados": list[dict]
        }
    """

    try:
        work_dir = await _extrai_sandbox_dir(config)
    except (ValueError, RuntimeError) as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1, "sucesso": False}
    
    try:
        await emit_front(config=config, mensagem="Executando script")
        comando_sandbox = _montar_comando_sandboxed(comando, work_dir)
        processo = await asyncio.create_subprocess_exec(*comando_sandbox, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(processo.communicate(), timeout=120)
        except TimeoutError:
            processo.kill()
            await processo.communicate()
            return {"stdout": "", "stderr": "Comando excedeu o tempo limite (30s)", "returncode": -1, "sucesso": False}

        resultado = {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": processo.returncode,
            "sucesso": processo.returncode == 0,
            "arquivos_publicados": [],
        }

        if processo.returncode == 0:
            resultado["arquivos_publicados"] = await _publicar_arquivos_gerados(work_dir, config)

        return json.dumps(resultado, ensure_ascii=False)

    
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1, "sucesso": False}


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    config_teste: RunnableConfig = {"configurable": { "thread_id": "teste-usuario-123", "callbacks_sio": [] }}

    testes_bloqueio = [
    "cat ../../etc/passwd",
    "cat /etc/passwd",
    "ls /root",
    "ls /home",
    "cat ~/.ssh/id_rsa",
    "cd .. && ls",
    "ls /proc/1/environ",
    ]

    '''
    for cmd in testes_bloqueio:
        resultado = asyncio.run(execute_bash(config=config_teste, comando=cmd))
        print(resultado)
        status = "BLOQUEADO ✅" if not resultado["sucesso"] else "PASSOU ⚠️ FALHA DE SEGURANÇA"
        print(f"{cmd!r:40} -> {status} | stderr={resultado['stderr'][:60]}")
    

    # Prepara um arquivo que ficará disponível apenas em workdirs/<thread>/sandbox.
    csv_teste = (
        "nome,idade,cidade,curso\n"
        "Ana,21,Campina Grande,Ciência da Computação\n"
        "Bruno,25,João Pessoa,Engenharia\n"
        "Carla,19,Patos,Administração\n"
        "Diego,30,Sousa,Matemática\n"
        "Aninha,22,Campina Grande,Ciência da Computação\n"
        "Bruna,26,João Pessoa,Engenharia\n"
        "Carlos,20,Patos,Administração\n"
        "Daniela,31,Sousa,Matemática\n"
    )
    csv_literal = csv_teste.replace("'", "'\\''").replace("\n", "\\n")
    asyncio.run(execute_bash(config=config_teste, comando=f"printf '{csv_literal}' > dados_teste.csv",))

    @tool
    async def bash(comando: str) -> str:
        """Executa um comando bash no sandbox. O arquivo dados_teste.csv está disponível."""
        resultado = await execute_bash(config=config_teste, comando=comando)
        return json.dumps(resultado, ensure_ascii=False)

    async def conversar_com_llm() -> None:
        if not os.getenv("OPENAI_API_KEY"): return

        llm = ChatOpenAI(model=os.getenv("AGENT_MODEL", "gpt-5.6-luna"), reasoning={"effort": "low"},).bind_tools([bash])
        mensagens = [HumanMessage(content=(
            "Você é um analista de dados. Use a ferramenta bash quando precisar "
            "ler ou transformar dados. O arquivo dados_teste.csv está no diretório "
            "atual. Nunca tente acessar caminhos fora do sandbox."
        ))]

        print("\nAgente bash pronto. Digite uma tarefa sobre dados_teste.csv (ou 'sair').")
        while True:
            pedido = await asyncio.to_thread(input, "\nVocê> ")
            if pedido.strip().lower() in {"sair", "exit", "quit"}: break
            mensagens.append(HumanMessage(content=pedido))

            while True:
                resposta = await llm.ainvoke(mensagens)
                mensagens.append(resposta)
                chamadas = getattr(resposta, "tool_calls", [])
                if not chamadas:
                    print(f"LLM> {resposta.content[0]["text"]}")
                    break
                for chamada in chamadas:
                    argumentos = chamada.get("args", {})
                    resultado = await bash.ainvoke(argumentos)
                    mensagens.append(ToolMessage(
                        content=resultado,
                        tool_call_id=chamada["id"],
                    ))

    asyncio.run(conversar_com_llm())
    '''
