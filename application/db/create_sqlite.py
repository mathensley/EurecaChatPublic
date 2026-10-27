import io, logging, json

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from application.core.google_credentials import load_service_account_credentials
from application.db.sqlite_paths import SQLITE_DIR


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
PASTA_DRIVE_ID = "1PeTRourlA2IpnVRri2KmPN_Icf078ljF"

MANIFEST_PATH = SQLITE_DIR / "manifest.json"

ARQUIVOS = [
    "ufcg.sqlite"
]


def formatar_modified_time(modified_time: str | None) -> str:
    if not modified_time:
        return "desconhecida"

    try:
        dt_utc = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
        return dt_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return modified_time


def autenticar():
    creds = load_service_account_credentials(SCOPES)
    return build("drive", "v3", credentials=creds)


def carregar_manifesto() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def salvar_manifesto(manifesto: dict) -> None:
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifesto, f, indent=2, ensure_ascii=False)


def listar_arquivos_drive(service) -> list[dict]:
    query = f"'{PASTA_DRIVE_ID}' in parents and trashed=false"
    response = service.files().list(
        q=query,
        fields="files(id,name,mimeType,modifiedTime,md5Checksum,size)",
        pageSize=100,
    ).execute()

    arquivos = []
    for item in response.get("files", []):
        if item["mimeType"].endswith("folder"):
            continue
        if item["name"] not in ARQUIVOS:
            continue
        arquivos.append(item)

    return arquivos


def precisa_baixar(item: dict, manifesto_local: dict) -> bool:
    nome = item["name"]
    destino = SQLITE_DIR / nome

    if not destino.exists():
        return True

    metadata_local = manifesto_local.get(nome)
    if not metadata_local:
        return True

    campos = ["id", "modifiedTime", "md5Checksum", "size"]
    return any(metadata_local.get(campo) != item.get(campo) for campo in campos)


def baixar_arquivo(service, file_id: str, destino: Path) -> None:
    temp_path = destino.with_suffix(destino.suffix + ".tmp")
    request = service.files().get_media(fileId=file_id)

    with io.FileIO(temp_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    temp_path.replace(destino)


def sincronizar_sqlites() -> None:
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)

    service = autenticar()
    manifesto_local = carregar_manifesto()
    arquivos_drive = listar_arquivos_drive(service)

    novo_manifesto = {}
    houve_download = False

    for item in arquivos_drive:
        nome = item["name"]
        destino = SQLITE_DIR / nome

        if precisa_baixar(item, manifesto_local):
            ultima_modificacao = formatar_modified_time(item.get("modifiedTime"))
            print(f"Baixando/atualizando {nome} | ultima modificacao no Drive: {ultima_modificacao}")
            baixar_arquivo(service, item["id"], destino)
            houve_download = True
        else:
            print(f"Arquivo atual: {nome}")

        novo_manifesto[nome] = {
            "id": item.get("id"),
            "modifiedTime": item.get("modifiedTime"),
            "md5Checksum": item.get("md5Checksum"),
            "size": item.get("size"),
        }

    salvar_manifesto(novo_manifesto)

    if houve_download:
        print("Sincronizacao dos SQLite concluida com atualizacoes.")
    else:
        print("Sincronizacao concluida sem alteracoes.")


if __name__ == "__main__":
    sincronizar_sqlites()
