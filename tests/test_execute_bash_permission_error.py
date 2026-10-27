import asyncio
from unittest.mock import AsyncMock, patch

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.eureca.eureca_bash import execute_bash


async def _run_permission_error_case():
    with patch(
        "src.tools.eureca.eureca_bash.execute_bash._extrai_sandbox_dir",
        new_callable=AsyncMock,
        side_effect=PermissionError("EACCES: permission denied"),
    ):
        return await execute_bash.execute_bash({"configurable": {"thread_id": "abc"}}, "echo ok")


def test_execute_bash_handles_permission_error():
    result = asyncio.run(_run_permission_error_case())
    assert result["sucesso"] is False
    assert "EACCES" in result["stderr"]
