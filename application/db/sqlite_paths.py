import os
from pathlib import Path


SQLITE_DIR = Path(os.getenv("SQLITE_DIR", Path.cwd() / "sqlite"))
