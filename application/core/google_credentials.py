import base64
import json
import os
from pathlib import Path

from google.oauth2 import service_account


def load_service_account_credentials(scopes: list[str]):
    """Carrega a conta de serviço de variável protegida ou, temporariamente, de arquivo."""
    encoded = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if encoded:
        try:
            raw_json = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON_B64 inválida") from exc

    if raw_json:
        try:
            info = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON inválida") from exc
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    credential_file = Path(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service.json"))
    if credential_file.is_file():
        return service_account.Credentials.from_service_account_file(
            credential_file,
            scopes=scopes,
        )

    raise RuntimeError(
        "Credencial do Google Drive ausente. Configure GOOGLE_SERVICE_ACCOUNT_JSON_B64."
    )
