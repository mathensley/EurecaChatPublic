import asyncio
import logging
import shutil, os
from pathlib import Path
from urllib.parse import quote
from langchain_core.runnables import RunnableConfig

BASE_WORKDIRS = (Path(__file__).resolve().parent.parent.parent.parent / "workdirs").resolve()
logger = logging.getLogger(__name__)
_execucoes_ativas: dict[Path, set[asyncio.Task]] = {}


def registrar_execucao(work_dir: str) -> None:
    """Associa a tool em andamento à conversa."""
    tarefa = asyncio.current_task()
    if tarefa is not None:
        conversa = _validar_work_dir(Path(work_dir).resolve().parent)
        _execucoes_ativas.setdefault(conversa, set()).add(tarefa)


def finalizar_execucao(work_dir: str) -> None:
    tarefa = asyncio.current_task()
    conversa = _validar_work_dir(Path(work_dir).resolve().parent)
    tarefas = _execucoes_ativas.get(conversa)
    if tarefas is not None:
        tarefas.discard(tarefa)
        if not tarefas:
            _execucoes_ativas.pop(conversa, None)


def _validar_work_dir(work_dir: str | os.PathLike[str]) -> Path:
    """Resolves e valida um diretório isolado imediatamente abaixo de workdirs/."""
    work_dir_resolvido = Path(work_dir).resolve()
    try:
        relativo = work_dir_resolvido.relative_to(BASE_WORKDIRS)
    except ValueError as exc:
        raise ValueError(f"work_dir resolvido fora da base permitida: {work_dir_resolvido}") from exc

    if len(relativo.parts) != 1 or relativo.parts[0] in {"", ".", ".."}:
        raise ValueError("work_dir deve identificar uma única conversa diretamente abaixo de workdirs/")
    return work_dir_resolvido


def criar_url_download(work_dir: str | os.PathLike[str], filename: str) -> str:
    """Cria a URL pública sem expor um caminho absoluto do servidor."""
    if Path(filename).name != filename:
        raise ValueError("filename deve conter apenas o nome do arquivo")

    work_dir_resolvido = _validar_work_dir(work_dir)
    identificador = work_dir_resolvido.relative_to(BASE_WORKDIRS).name
    return f"/downloads/{quote(identificador, safe='')}/{quote(filename, safe='')}"


async def _extrai_work_dir(config: RunnableConfig) -> str:
    configurable = config.get("configurable", {})
    work_dir = configurable.get("work_dir")

    if not work_dir:
        thread_id = configurable.get("thread_id") or configurable.get("user_id")
        if not thread_id:
            raise ValueError("Nem work_dir nem thread_id/user_id foram fornecidos em config['configurable']")
        work_dir = BASE_WORKDIRS / str(thread_id)

    work_dir_resolvido = _validar_work_dir(work_dir)
    work_dir_resolvido.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        # A raiz da conversa pertence à aplicação. Apenas sandbox/ será montado na microVM.
        work_dir_resolvido.chmod(0o700)
    return str(work_dir_resolvido)


async def _extrai_sandbox_dir(config: RunnableConfig) -> str:
    """Retorna a área gravável pelo processo isolado da conversa."""
    work_dir = Path(await _extrai_work_dir(config))
    sandbox_dir = work_dir / "sandbox"
    sandbox_dir.mkdir(exist_ok=True)

    if os.name == "posix":
        app_uid, app_gid = os.geteuid(), os.getegid()
        stat = sandbox_dir.stat()
        if stat.st_uid != app_uid or stat.st_gid != app_gid:
            try:
                os.chown(sandbox_dir, app_uid, app_gid)
            except PermissionError as exc:
                raise RuntimeError("A aplicação não possui permissão para preparar o diretório do sandbox") from exc

        # O diretório permanece privado no backend; a microVM recebe somente este bind mount.
        sandbox_dir.chmod(0o700)

    return str(sandbox_dir.resolve())


async def _extrai_exports_dir(config: RunnableConfig) -> str:
    """Retorna a área privada onde somente a aplicação grava exportações."""
    work_dir = Path(await _extrai_work_dir(config))
    exports_dir = work_dir / "exports"
    exports_dir.mkdir(exist_ok=True)
    if os.name == "posix":
        exports_dir.chmod(0o700)
    return str(exports_dir.resolve())


async def remover_work_dir(thread_id: str | None) -> bool:
    """Remove os arquivos associados à conversa."""
    if not thread_id:
        return False

    try:
        work_dir = _validar_work_dir(BASE_WORKDIRS / str(thread_id))
        tarefas = [
            tarefa for tarefa in _execucoes_ativas.get(work_dir, ())
            if tarefa is not asyncio.current_task()
        ]
        for tarefa in tarefas:
            tarefa.cancel()
        if tarefas:
            await asyncio.gather(*tarefas, return_exceptions=True)
        if not work_dir.exists():
            return False
        await asyncio.to_thread(shutil.rmtree, work_dir)
        return True
    except (OSError, ValueError):
        logger.exception("Não foi possível remover o workdir da conversa %s", thread_id)
        return False
