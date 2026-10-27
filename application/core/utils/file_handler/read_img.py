def ler_imagens(arquivos):
    mensagens = []

    for img in arquivos:
        try:
            filename = img.get("filename", "desconhecido.png")
            b64_data = img.get("content", "")

            if not b64_data.strip():
                continue

            extension = filename.lower().rsplit(".", 1)[-1]
            mime_type = "image/jpeg" if extension in {"jpg", "jpeg"} else "image/png"
            mensagens.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
            })
        except Exception as e:
            print(f"Erro ao processar imagem {filename}: {e}")

    return mensagens
