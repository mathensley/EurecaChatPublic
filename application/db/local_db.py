import sys
import subprocess
from pathlib import Path

def avaliar_banco_dados(deletar_todos=False):
    db_dirs = [
        Path("estudantes_ufcg.sqlite"),
        Path("matriculas_ufcg.sqlite"),
        Path("estagios_ufcg.sqlite"),
    ]

    modulos_criar_banco = [
        "src.tools.estudante.aux_estudantes_ufcg",
        "src.tools.disciplina.aux_matriculas_ufcg",
        "src.tools.estudante.aux_estagios_ufcg",
    ]

    existem_todos = all(db.exists() for db in db_dirs)

    if not existem_todos or deletar_todos:
        for db in db_dirs:
            if db.exists():
                db.unlink()

        for modulo in modulos_criar_banco:
            subprocess.run(
                [sys.executable, "-m", modulo],
                check=True
            )