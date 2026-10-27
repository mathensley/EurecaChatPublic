---
nome: geracao_pdf
quando_usar: >
  O usuário pede um PDF, relatório, documento formatado,
  proposta, ficha, comprovante ou qualquer arquivo para "baixar",
  "imprimir" ou "enviar" que não seja apenas uma resposta de texto no chat.
---

# Como gerar PDFs com boa aparência

Você tem acesso à ferramenta `execute_bash`, que executa comandos num sandbox
Python. Para criar PDFs, escreva um script Python usando `reportlab` e
execute-o com essa ferramenta. Não existe uma ferramenta separada de
"criar PDF" — o fluxo é sempre: **escrever o script → rodar com bash →
conferir que o arquivo foi gerado**.

Para não ter que desenhar tipografia/tabela/cores do zero a cada pedido,
importe o módulo `pdf_helpers`, que já está disponível no ambiente
(`from pdf_helpers import ...`). Ele resolve a "forma"; você só decide o
"conteúdo" (quais seções, quais dados entram).

## Fluxo recomendado

O diretório atual é `/workspace`, que permite escrita e persiste entre chamadas
de `execute_bash`. Escreva scripts e PDFs nele, usando nomes relativos simples.
`/exports` contém arquivos publicados anteriormente, mas é **somente leitura**;
leia dados de lá, nunca tente salvar o PDF nesse caminho. Cada chamada usa uma
microVM nova: `/tmp` é descartado ao final e `/home/oai/share` não existe aqui.
PDFs e CSVs gerados na raiz de `/workspace` são publicados automaticamente,
sem precisar copiá-los para outro diretório.

1. Escreva o script Python completo num arquivo (`cat > relatorio.py <<'EOF' ... EOF`).
2. Rode com `python3 relatorio.py`.
3. Rode `ls -la *.pdf` para confirmar que o arquivo existe e tem tamanho > 0.
4. Se dependência faltando, o comando falha com `ModuleNotFoundError` —
   isso indica um problema de ambiente (não há internet no sandbox), não
   tente `pip install` no meio do script.

## Dimensões da página e largura útil (A4)

Todo documento gerado por este skill usa **A4 retrato por padrão**:

| Medida                           | Valor           |
|----------------------------------|-----------------|
| Página A4 (largura × altura)     | 21 cm × 29,7 cm |
| Margens (todas as bordas)        | 2,2 cm          |
| **Largura útil (retrato)**       | **16,6 cm**     |
| **Altura útil (retrato)**        | **25,3 cm**     |

A largura útil é o número que importa na prática: **16,6 cm**, não
"~17 cm" — em documentos com várias colunas essa diferença de meio
centímetro é o que faz uma tabela estourar a margem direita.

As larguras passadas em `col_widths` são expressas em centímetros. Use
16,6 cm como largura útil no retrato e 25,3 cm na paisagem; não use nomes
de constantes que não estejam definidos em `pdf_helpers.py`.

**Regra de ouro para `col_widths`:** a soma de todas as larguras de
coluna deve bater com a largura útil da orientação escolhida — nem mais
(estoura a página), nem muito menos (tabela sobra com espaço em branco
esquisito à direita). Antes de rodar o script, some as larguras na
cabeça:

```python
# Retrato: soma deve ser ≈ 16.6
col_widths=[6, 5.6, 5]   # 6 + 5.6 + 5 = 16.6 ✓

# Isso aqui estoura a margem em retrato (soma = 19):
col_widths=[7, 7, 5]     # ✗ não cabe em retrato — ou reduz, ou vai de paisagem
```

Se não passar `col_widths`, o reportlab distribui a largura útil
igualmente entre as colunas — o que é aceitável para tabelas de 2-3
colunas com conteúdo parecido, mas costuma ficar ruim com colunas de
tamanhos de conteúdo muito diferentes (ex.: "Código" vs "Descrição").
Nesses casos, sempre especifique `col_widths` manualmente.

### Quando usar paisagem em vez de retrato

Se a tabela tem muitas colunas (tipicamente 6+) ou colunas com texto
longo, e a soma mínima legível das larguras passa de 16,6 cm, mude o
documento inteiro para paisagem em vez de espremer o conteúdo:

```python
from pdf_helpers import construir_documento
from reportlab.lib.pagesizes import A4, landscape

construir_documento(
    "relatorio.pdf",
    elementos,
    titulo_doc="Título do Documento",
    pagesize=landscape(A4),   # usa 29.7 x 21 cm, largura útil = 25.3 cm
)
```

Não é preciso girar elementos manualmente — `pagesize=landscape(A4)` já
ajusta a página, as margens e a largura útil disponível para
`tabela_estilizada`. Mantenha **um único documento com uma orientação
só**; não misture páginas retrato e paisagem no mesmo PDF a menos que o
usuário peça explicitamente.

## Exemplo completo

```python
from pdf_helpers import (
    obter_estilos, paragrafo_capa, tabela_estilizada,
    construir_documento,
)
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm

estilos = obter_estilos()
elementos = []

# Capa (opcional — só use em documentos de 2+ páginas)
elementos += paragrafo_capa("Título do Documento", "Subtítulo ou data", "Autor/Origem")

# Seções usam H1/H2, corpo de texto usa "Corpo"
elementos.append(Paragraph("Nome da Seção", estilos["H1"]))
elementos.append(Paragraph("Texto corrido normal.", estilos["Corpo"]))

# Tabelas já saem com cabeçalho colorido e linhas zebradas.
# col_widths em cm — a soma deve bater com a largura útil (16.6 em retrato)
elementos.append(tabela_estilizada(
    cabecalho=["Coluna 1", "Coluna 2", "Coluna 3"],
    linhas=[["a", "b", "c"], ["d", "e", "f"]],
    col_widths=[6.6, 5, 5],  # 6.6 + 5 + 5 = 16.6 ✓
))

elementos.append(Spacer(1, 0.5 * cm))

construir_documento(
    "relatorio.pdf",
    elementos,
    titulo_doc="Título do Documento",
    pagesize=landscape(A4),
)
print("PDF gerado: relatorio.pdf")
```

### Texto longo dentro de células de tabela

Strings simples em `linhas` não quebram automaticamente — se uma célula
tiver uma frase longa, ela pode estourar a coluna ou ser cortada. Para
qualquer coluna com texto corrido (descrições, observações, endereços),
passe um `Paragraph` no lugar da string crua, usando o estilo `Corpo`:

```python
from reportlab.platypus import Paragraph

linhas=[
    ["001", Paragraph("Descrição bem longa que precisa quebrar linha dentro da célula.", estilos["Corpo"])],
]
```

Isso vale sempre que a coluna tiver largura menor que o texto que ela
recebe — colunas curtas (códigos, datas, valores) podem continuar como
string simples.

## Imagens dentro do PDF

Existem três origens possíveis pra uma imagem no PDF — cada uma com um caminho diferente:

**1. Gráfico a partir de dados** (o mais comum): gere o PNG com
matplotlib dentro do próprio script, ANTES de montar o PDF, e depois
embuta com `imagem_ajustada`:

```python
import matplotlib
matplotlib.use("Agg")  # sem isso, dá erro por falta de display no sandbox
import matplotlib.pyplot as plt
from pdf_helpers import imagem_ajustada

plt.figure(figsize=(6, 3))
plt.bar(["Mai", "Jun", "Jul"], [6, 9, 11], color="#1F3A5F")
plt.tight_layout()
plt.savefig("grafico.png", dpi=150)

elementos.append(imagem_ajustada("grafico.png"))
```

**2. Imagem/foto que o usuário já enviou** (já existe no work_dir): só
chame `imagem_ajustada("nome_do_arquivo.png")` direto — não precisa
recriar nada.

**3. Imagem que precisa ser criada por IA a partir de uma descrição**
(logo, ilustração, ícone — algo que não existe e não é um gráfico de
dados): isso NÃO é feito dentro do execute_bash, porque o sandbox não
tem rede. Use a ferramenta `gerar_imagem(prompt=...)` primeiro — ela
roda fora do sandbox e devolve o nome do arquivo já salvo no work_dir —
e só depois chame execute_bash pra montar o PDF:

```
1. gerar_imagem(prompt="ícone minimalista de frasco de perfume, fundo branco")
   -> {"caminho": "icone_frasco_de_perfume.png", "sucesso": true}
2. execute_bash com um script que faz:
   elementos.append(imagem_ajustada("icone_frasco_de_perfume.png"))
```

Sempre use `imagem_ajustada(...)` em vez de `Image(caminho, width=X, height=Y)`
direto — largura/altura chutadas na mão esticam ou achatam a imagem
quando a proporção não bate. `imagem_ajustada` já respeita a largura
útil da orientação atual (retrato ou paisagem) automaticamente.

## Princípios de design (por que o resultado fica bom)

- **Paleta curta**: `pdf_helpers.PALETA` já define 2 cores principais
  (uma para títulos/cabeçalho de tabela, outra pra acentos) + tons de
  cinza. Não introduza cores novas ad-hoc — poucas cores bem usadas
  parecem mais profissionais do que muitas cores soltas.
- **Hierarquia tipográfica clara**: título (24pt) > seção H1 (16pt) >
  subseção H2 (12.5pt) > corpo (10.5pt). Use sempre os estilos prontos
  (`estilos["H1"]`, `estilos["Corpo"]` etc.) em vez de criar
  `ParagraphStyle` novos no meio do script.
- **Espaço em branco generoso**: margens de 2,2cm já configuradas em
  `construir_documento`. Não tente espremer conteúdo — se não couber,
  é melhor quebrar em mais páginas (o Platypus faz isso sozinho) ou
  mudar para paisagem (veja seção acima).
- **Tabelas com hierarquia visual**: cabeçalho com fundo colorido +
  texto branco + negrito, linhas de dados alternando branco/cinza claro
  (zebra), sem grade pesada. Use sempre `tabela_estilizada(...)`, com
  `col_widths` somando exatamente a largura útil.
- **Rodapé consistente**: `construir_documento` já adiciona numeração de
  página automática — não implemente rodapé manualmente.

## Armadilhas comuns (evite estes erros)

- **Larguras de coluna que não batem com a página**: sempre some
  `col_widths` de cabeça antes de rodar. Em retrato a soma-alvo é
  **16,6 cm**; em paisagem, **25,3 cm**. Se a soma passar disso, ou
  reduza as colunas ou mude a orientação — nunca deixe o reportlab
  "se virar" com colunas maiores que a página.
- **Texto longo em célula sem `Paragraph`**: strings cruas em células de
  tabela não quebram linha. Use `Paragraph(texto, estilos["Corpo"])`
  em qualquer coluna de texto corrido (ver exemplo acima).
- **Misturar retrato e paisagem no mesmo PDF**: escolha uma orientação
  para o documento inteiro; não gire páginas individualmente a menos
  que o usuário peça isso especificamente.
- **Nunca** use caracteres unicode de subscrito/sobrescrito (₀₁₂, ⁰¹²) —
  as fontes core não têm esses glifos e viram um quadrado preto. Dentro
  de um `Paragraph`, use as tags `<sub>` e `<super>`
  (ex.: `"H<sub>2</sub>O"`, `"x<super>2</super>"`).
- **Nunca** use `canvas.drawString` cru para blocos de texto longos —
  ele não quebra linha automaticamente e o texto some da página. Use
  sempre Platypus (`Paragraph`, `Table`, `SimpleDocTemplate`), que é o
  que `pdf_helpers` já usa por baixo.
- **Só fontes core**: `Helvetica`, `Helvetica-Bold`, `Helvetica-Oblique`,
  `Times-Roman`, `Courier` e variantes. Qualquer outro nome de fonte
  falha ou é ignorado silenciosamente, a menos que você registre uma
  fonte TTF explicitamente com `pdfmetrics.registerFont`.
- **Acentuação (português)**: escreva o script sempre em UTF-8 (é o
  padrão do `cat > arquivo.py <<'EOF'`) — as fontes core do reportlab
  cobrem ç, ã, õ, á, é, etc. normalmente. Se algum acento aparecer
  trocado no PDF final, o problema quase sempre é o script salvo com
  encoding errado, não o reportlab.
- **Arquivo de saída**: sempre passe um caminho relativo simples (ex.:
  `"relatorio.pdf"`) — o script já roda dentro do diretório de trabalho
  isolado do usuário. Use o mesmo nome de arquivo do início ao fim do
  script para não se perder em qual PDF é o final.
- **Tamanho do PDF**: prefira `dpi=150` (não 300+) em gráficos matplotlib
  e reduza fotos muito grandes antes de incorporá-las ao documento.
