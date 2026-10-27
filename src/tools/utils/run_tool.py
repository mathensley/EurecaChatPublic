import importlib
from application.http_client import init_client, close_client

async def run_tool(tool_path, *args, **kwargs):
    await init_client()
    try:
        module_name, func_name = tool_path.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        result = await func(*args, **kwargs)
        print(result)
    finally:
        await close_client()