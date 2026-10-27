from ..tools.estudante.aux_estudantes_ufcg import aux_estudantes_ufcg
from ..tools.disciplina.aux_matriculas_ufcg import aux_matriculas_ufcg
from ..tools.estudante.aux_estagios_ufcg import aux_estagios
from ..tools.curso.buscar_calendarios import buscar_calendarios
from ..tools.utils.run_tool import run_tool
from application.config import URL_SIG
from langchain_core.runnables import RunnableConfig
from datetime import datetime
import json, os, asyncio
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from application.core.google_credentials import load_service_account_credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
PASTA_DRIVE_ID = "1PeTRourlA2IpnVRri2KmPN_Icf078ljF"
ROOT_DIR = Path(__file__).resolve().parents[2]

caminho_estudantes = ROOT_DIR / "estudantes_ufcg.sqlite"
caminho_matriculas = ROOT_DIR / "matriculas_ufcg.sqlite"


# ================== GOOGLE DRIVE ==================

def get_drive_service():
    creds = load_service_account_credentials(SCOPES)
    return build("drive", "v3", credentials=creds)


def buscar_arquivo(service, nome):
    query = f"name='{nome}' and '{PASTA_DRIVE_ID}' in parents and trashed=false"
    res = service.files().list(q=query, fields="files(id,name)").execute()
    files = res.get("files", [])
    return files[0] if files else None


def renomear(service, file_id, novo_nome):
    service.files().update(
        fileId=file_id,
        body={"name": novo_nome}
    ).execute()


def upload(service, caminho, nome):
    media = MediaFileUpload(caminho, resumable=True)

    service.files().create(
        body={"name": nome, "parents": [PASTA_DRIVE_ID]},
        media_body=media,
        fields="id"
    ).execute()


def atualizar_arquivo(service, file_id, caminho):
    media = MediaFileUpload(caminho, resumable=True)

    service.files().update(
        fileId=file_id,
        media_body=media
    ).execute()


def subir_com_backup(service, caminho, nome):
    existente = buscar_arquivo(service, nome)

    if existente:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        backup_nome = f"{nome}_backup_{timestamp}"
        print(f"Criando backup: {backup_nome}")
        renomear(service, existente["id"], backup_nome)

    print(f"Enviando novo arquivo: {nome}")
    upload(service, caminho, nome)


# ================== UTILS ==================

def get_base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def get_file_path():
    return os.path.join(get_base_dir(), "download_info.json")


def parse_datetime(value):
    return datetime.fromisoformat(value) if value else datetime.min


def parse_periodo(periodo: str):
    if not periodo:
        return (0, 0)
    ano, semestre = periodo.split(".")
    return int(ano), int(semestre)


def deve_atualizar(periodo_atual, periodo_salvo, inicio_aulas, ultima_atualizacao):
    return (periodo_atual > periodo_salvo or inicio_aulas > ultima_atualizacao)


def load_json(filename):
    if not os.path.exists(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_json(filename, data):
    temp = filename + ".tmp"

    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    os.replace(temp, filename)


# ================== MAIN ==================

async def make_database(dados_a_baixar=None):
    dados_a_baixar = {} if dados_a_baixar is None else dados_a_baixar

    calendarios = await buscar_calendarios(
        config=RunnableConfig(),
        periodo="",
        todos_calendarios=False,
        proximo_periodo=False,
    )
    filename = get_file_path()
    json_info = load_json(filename)
    now_iso = datetime.now().isoformat()

    calendario = calendarios[-1]
    periodo_atual = parse_periodo(calendario["periodo"])
    inicio_aulas = datetime.fromisoformat(calendario["inicio_das_aulas"])

    # ================== ESTUDANTES ==================
    periodo_salvo_estudantes = parse_periodo(json_info.get("periodo_salvo_estudantes"))
    data_estudantes = parse_datetime(json_info.get("estudantes_atualizados_em"))

    status = dados_a_baixar.get("estudantes", "")
    if status == "download" or (status == "atualizar" and deve_atualizar(
        periodo_atual, periodo_salvo_estudantes, inicio_aulas, data_estudantes
    )):
        print("Processando estudantes...")
        aux_estudantes_ufcg(URL_SIG, None)

        json_info["estudantes_atualizados_em"] = now_iso
        json_info["periodo_salvo_estudantes"] = calendario["periodo"]

    # ================== MATRÍCULAS ==================
    periodo_salvo_matriculas = parse_periodo(json_info.get("periodo_salvo_matriculas"))
    data_matriculas = parse_datetime(json_info.get("matriculas_atualizados_em"))

    status = dados_a_baixar.get("matriculas", "")
    if status == "download" or (status == "atualizar" and deve_atualizar(
        periodo_atual, periodo_salvo_matriculas, inicio_aulas, data_matriculas
    )):
        print("Processando matrículas...")
        aux_matriculas_ufcg(URL_SIG, None)

        json_info["matriculas_atualizados_em"] = now_iso
        json_info["periodo_salvo_matriculas"] = calendario["periodo"]

    # ================== ESTÁGIOS ==================
    periodo_salvo_estagios = parse_periodo(json_info.get("periodo_salvo_estagios"))
    data_estagios = parse_datetime(json_info.get("estagios_atualizados_em"))

    status = dados_a_baixar.get("estagios", "")
    if status == "download" or (status == "atualizar" and deve_atualizar(
        periodo_atual, periodo_salvo_estagios, inicio_aulas, data_estagios
    )):
        print("Processando estágios...")
        aux_estagios(URL_SIG, None)

        json_info["estagios_atualizados_em"] = now_iso
        json_info["periodo_salvo_estagios"] = calendario["periodo"]

    # ================== SALVAR JSON ==================
    save_json(filename, json_info)

    print("\nEstado final:")
    print(json.dumps(json_info, indent=4))

    # ================== GOOGLE DRIVE ==================
    service = get_drive_service()

    if caminho_estudantes.exists():
        subir_com_backup(service, str(caminho_estudantes), "estudantes_ufcg.sqlite")
    else:
        print(f"Arquivo não encontrado: {caminho_estudantes}")

    if caminho_matriculas.exists():
        subir_com_backup(service, str(caminho_matriculas), "matriculas_ufcg.sqlite")
    else:
        print(f"Arquivo não encontrado: {caminho_matriculas}")


# ================== EXEC ==================

if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.database.download.make_database",
            dados_a_baixar={
                "estudantes": "download",
                "matriculas": "download",
                "estagios": "download"
            }
        )
    )
