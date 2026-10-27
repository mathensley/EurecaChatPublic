import os
from pathlib import Path

from quart import Blueprint, abort, send_from_directory

from src.tools.eureca.eureca_bash.workdir import BASE_WORKDIRS


bp = Blueprint("downloads", __name__)


@bp.get("/downloads/<workdir_id>/<filename>")
async def download_export(workdir_id: str, filename: str):
    """Disponibiliza uma exportação somente no workdir da conversa indicada."""
    export_valido = (
        filename.endswith(".csv")
        and filename.startswith(("eureca_query_", "eureca_csv_"))
    ) or (
        filename.endswith(".pdf")
        and filename.startswith(("fluxograma_", "eureca_pdf_"))
    )
    if (
        Path(workdir_id).name != workdir_id
        or Path(filename).name != filename
        or not export_valido
    ):
        abort(404)

    workdir = BASE_WORKDIRS / workdir_id
    exports_dir = workdir / "exports"
    arquivo = exports_dir / filename

    try:
        workdir_resolvido = workdir.resolve(strict=True)
        exports_dir_resolvido = exports_dir.resolve(strict=True)
        arquivo_resolvido = arquivo.resolve(strict=True)
    except (FileNotFoundError, OSError):
        abort(404)

    # Rejeita traversal e também symlinks. Isso é importante porque o mesmo
    # workdir pode ser montado no sandbox de comandos.
    if (
        workdir_resolvido.parent != BASE_WORKDIRS
        or exports_dir_resolvido.parent != workdir_resolvido
        or arquivo_resolvido.parent != exports_dir_resolvido
        or arquivo_resolvido != Path(os.path.abspath(arquivo))
        or not arquivo_resolvido.is_file()
    ):
        abort(404)

    resposta = await send_from_directory(
        exports_dir_resolvido,
        filename,
        as_attachment=True,
        attachment_filename=filename,
    )
    resposta.headers["Cache-Control"] = "private, no-store"
    return resposta
