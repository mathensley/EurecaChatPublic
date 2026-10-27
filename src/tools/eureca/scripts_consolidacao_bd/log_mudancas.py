import json
import sqlite3
from datetime import datetime
from pathlib import Path


MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

# Mapeia cada script de download -> (tabela afetada, colunas que identificam um
# registro de forma ESTÁVEL entre execuções). Não use colunas tipo "id_xxx" se
# elas forem recriadas a cada consolidação do banco (como id_inscricao é).
#
# Só "download_matriculas" está confirmado. Para ativar os outros, rode:
#   sqlite3 ufcg.sqlite ".schema estudante"   (etc.)
# e preencha a tupla de colunas_chave correspondente antes de descomentar o script.
TABELAS_POR_SCRIPT = {
    "download_matriculas": {
        "tabela": "inscricao",
        "colunas_chave": ("matricula_do_estudante", "codigo_da_disciplina", "periodo", "turma"),
    },
    "download_estudantes": {
        "tabela": "estudante",
        "colunas_chave": ("matricula_do_estudante",),
    },
    "download_estagios": {
        "tabela": "estagio",
        "colunas_chave": ("matricula_do_estudante", "data_inicio_estagio", "agente_integracao"),
    },
    "download_professores": {
        "tabela": "professor",
        "colunas_chave": ("matricula_do_professor",),
    },
    # "download_disciplinas": {"tabela": "curso", "colunas_chave": (...)},
}


def _chave(linha: dict, colunas_chave: tuple[str, ...]) -> str:
    """Monta a chave composta e estável de um registro."""
    return "|".join(str(linha[coluna]) for coluna in colunas_chave)


def _ler_registros(caminho_db: str, tabela: str, colunas_chave: tuple[str, ...]) -> dict[str, dict] | None:
    """Lê os registros da tabela, indexados pela chave composta estável.
    Retorna None se o arquivo do banco ainda não existe (não há "antes" pra comparar)."""
    if not Path(caminho_db).exists():
        return None
    conexao = sqlite3.connect(caminho_db)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.execute(f"SELECT * FROM {tabela}")
    registros = {_chave(dict(linha), colunas_chave): dict(linha) for linha in cursor.fetchall()}
    conexao.close()
    return registros


def registrar_mudancas(
    scripts_executados: list[str],
    caminho_db_antigo: str,
    caminho_db_novo: str,
    caminho_historico: Path,
) -> Path:
    #scripts_executados=["download_matriculas"]
    """
    Compara, para cada script que rodou nesta execução, o banco antigo com o novo,
    e ACRESCENTA o resultado (quem entrou / quem saiu) ao histórico acumulado em JSON.
    Se o banco antigo ainda não existir (primeira execução), total_antes fica None,
    ninguém "saiu" e tudo que está no banco novo entra em "entraram".
    """
    historico: dict[str, list[dict]] = {}
    if caminho_historico.exists():
        with open(caminho_historico, encoding="utf-8") as arquivo:
            historico = json.load(arquivo)


    momento = datetime.now()
    mes = MESES_PT[momento.month]
    data_legivel = f"{momento.day:02d} de {mes} de {momento.year} às {momento.hour:02d}h{momento.minute:02d}"

    tabelas_ja_comparadas: set[str] = set()

    for script in scripts_executados:
        config = TABELAS_POR_SCRIPT.get(script)
        if config is None:
            print(f"  (aviso) '{script}' não tem tabela configurada em TABELAS_POR_SCRIPT — pulado")
            continue

        tabela = config["tabela"]
        if tabela in tabelas_ja_comparadas:
            continue
        tabelas_ja_comparadas.add(tabela)

        colunas_chave = config["colunas_chave"]
        antigos = _ler_registros(caminho_db_antigo, tabela, colunas_chave)
        novos = _ler_registros(caminho_db_novo, tabela, colunas_chave)

        if novos is None:
            print(f"  (aviso) banco novo '{caminho_db_novo}' não encontrado — '{tabela}' pulada")
            continue

        if antigos is None:
            total_antes = None
            entraram_registros = list(novos.values())
            sairam_registros = []
            print(f"  {tabela}: sem banco anterior — {len(novos)} registro(s) contam como entrada")
        else:
            chaves_antigas = set(antigos)
            chaves_novas = set(novos)
            chaves_entraram = chaves_novas - chaves_antigas
            chaves_sairam = chaves_antigas - chaves_novas
            total_antes = len(antigos)
            entraram_registros = [novos[chave] for chave in sorted(chaves_entraram)]
            sairam_registros = [antigos[chave] for chave in sorted(chaves_sairam)]
            print(f"  {tabela}: entraram {len(entraram_registros)} | saíram {len(sairam_registros)}")

        entrada = {
            "data_atualizacao": momento.isoformat(),
            "data_legivel": data_legivel,
            "total_antes": total_antes,
            "total_depois": len(novos),
            "entraram": entraram_registros,
            "sairam": sairam_registros,
        }

        historico.setdefault(tabela, []).append(entrada)

    if not tabelas_ja_comparadas:
        print("  nenhum script com tabela configurada foi executado — histórico não alterado")
        return caminho_historico

    with open(caminho_historico, "w", encoding="utf-8") as arquivo:
        json.dump(historico, arquivo, ensure_ascii=False, indent=2)

    print(f"Histórico atualizado em: {caminho_historico}")
    return caminho_historico