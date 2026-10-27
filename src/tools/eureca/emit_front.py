async def emit_front(config, mensagem):
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'): await cb.emit("status", {"resposta": mensagem})
            break
    except Exception: pass