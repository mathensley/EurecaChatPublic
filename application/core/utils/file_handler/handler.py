import logging
from langchain_core.messages import HumanMessage

from .read_pdf import ler_pdf
from .read_img import ler_imagens


def realizar_tratamento_dos_arquivos(arquivos):
    try:
        messages = []
        
        pdfs = [arquivo for arquivo in arquivos if arquivo["filename"].lower().endswith(".pdf")]
        if len(pdfs) > 0:
            texto_pdf = ler_pdf(pdfs)
            if texto_pdf.strip():
                messages.append(f"O PDF enviado tem o seguinte texto: {texto_pdf}")

        imagens_dataurls = ler_imagens([arquivo for arquivo in arquivos if arquivo["filename"].lower().endswith((".jpg", ".jpeg", ".png"))])
        
        messages.extend(imagens_dataurls)

        return messages
    except:
        print("Ocorreu um erro ao ler os arquivos")
        logging.exception(f"Ocorreu um erro ao ler os arquivos")

        return ["Ocorreu um erro na leitura dos dados do arquivo. Por favor, informe isso ao usuário."]


def construir_mensagem_com_arquivos(pergunta: str, arquivos: list[dict]) -> HumanMessage:
    pdfs = [arquivo for arquivo in arquivos if arquivo["filename"].lower().endswith(".pdf")]
    imagens = [
        arquivo
        for arquivo in arquivos
        if arquivo["filename"].lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    texto = pergunta
    if pdfs:
        blocos_pdf = []
        for pdf in pdfs:
            nome_pdf = pdf.get("filename", "desconhecido.pdf")
            conteudo_pdf = ler_pdf([pdf]).strip()
            if not conteudo_pdf:
                conteudo_pdf = "(Nenhum texto foi extraído deste PDF.)"
            blocos_pdf.append(
                f"Nome do PDF: {nome_pdf}\n"
                f"Conteúdo:\n{conteudo_pdf}"
            )

        texto = "\n\n".join(blocos_pdf)
        texto = "\n\n Estes arquivos estão dentro do diretório .attachments/"
        texto += f"\n\nPergunta:\n{pergunta}"

    blocos = [{"type": "text", "text": texto}, *ler_imagens(imagens)]
    return HumanMessage(content=blocos)
