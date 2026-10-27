'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle,
  Download,
  FileSpreadsheet,
  LoaderCircle,
  Maximize2,
  Minimize2,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

const MAX_PREVIEW_ROWS = 1000

export interface CsvFileInfo {
  url: string
  filename: string
  displayName: string
}

interface CsvPreview {
  headers: string[]
  rows: string[][]
  truncated: boolean
}

type PreviewState =
  | { status: 'idle' | 'loading' }
  | { status: 'success'; data: CsvPreview }
  | { status: 'error'; message: string }

function detectDelimiter(content: string) {
  const candidates = [',', ';', '\t']
  const counts = new Map(candidates.map((candidate) => [candidate, 0]))
  let inQuotes = false

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index]

    if (character === '"') {
      if (inQuotes && content[index + 1] === '"') {
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (!inQuotes && (character === '\n' || character === '\r')) break
    if (!inQuotes && counts.has(character)) {
      counts.set(character, (counts.get(character) ?? 0) + 1)
    }
  }

  return candidates.reduce((best, candidate) => (
    (counts.get(candidate) ?? 0) > (counts.get(best) ?? 0) ? candidate : best
  ), ',')
}

function parseCsv(source: string): CsvPreview {
  const content = source.replace(/^\uFEFF/, '')
  const delimiter = detectDelimiter(content)
  const parsedRows: string[][] = []
  let currentRow: string[] = []
  let currentField = ''
  let inQuotes = false
  let truncated = false

  const finishRow = () => {
    currentRow.push(currentField)
    currentField = ''
    parsedRows.push(currentRow)
    currentRow = []

    if (parsedRows.length > MAX_PREVIEW_ROWS + 1) {
      parsedRows.pop()
      truncated = true
      return false
    }
    return true
  }

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index]

    if (character === '"') {
      if (inQuotes && content[index + 1] === '"') {
        currentField += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (!inQuotes && character === delimiter) {
      currentRow.push(currentField)
      currentField = ''
      continue
    }

    if (!inQuotes && (character === '\n' || character === '\r')) {
      if (character === '\r' && content[index + 1] === '\n') index += 1
      if (!finishRow()) break
      continue
    }

    currentField += character
  }

  if (!truncated && (currentField.length > 0 || currentRow.length > 0)) finishRow()

  while (
    parsedRows.length > 0
    && parsedRows.at(-1)?.every((field) => field.length === 0)
  ) {
    parsedRows.pop()
  }

  if (parsedRows.length === 0) {
    throw new Error('O arquivo CSV está vazio.')
  }

  const [rawHeaders, ...rows] = parsedRows
  const columnCount = Math.max(rawHeaders.length, ...rows.map((row) => row.length), 1)
  const headers = Array.from({ length: columnCount }, (_, index) => (
    rawHeaders[index]?.trim() || `Coluna ${index + 1}`
  ))

  return { headers, rows, truncated }
}

function CsvTable({ preview }: { preview: CsvPreview }) {
  return (
    <div className="min-h-0 flex-1 overflow-auto bg-background">
      <table className="w-max min-w-full border-separate border-spacing-0 text-left text-sm">
        <thead className="sticky top-0 z-20 bg-muted text-foreground shadow-[0_1px_0_var(--border)]">
          <tr>
            <th className="sticky left-0 z-30 w-14 min-w-14 border-r border-border bg-muted px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">
              #
            </th>
            {preview.headers.map((header, index) => (
              <th
                key={`${header}-${index}`}
                className="min-w-32 border-r border-border px-4 py-2.5 font-semibold last:border-r-0"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="even:bg-muted/30 hover:bg-brand-accent/5">
              <th className="sticky left-0 z-10 border-r border-t border-border bg-background px-3 py-2 text-right text-xs font-normal text-muted-foreground [tr:nth-child(even)_&]:bg-muted">
                {rowIndex + 1}
              </th>
              {preview.headers.map((_, columnIndex) => (
                <td
                  key={columnIndex}
                  className="max-w-lg whitespace-pre-wrap border-r border-t border-border px-4 py-2 align-top last:border-r-0"
                >
                  {row[columnIndex] ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function CsvDownloadCard({ file }: { file: CsvFileInfo }) {
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [preview, setPreview] = useState<PreviewState>({ status: 'idle' })

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) setExpanded(false)
  }

  useEffect(() => {
    if (!open) return

    const controller = new AbortController()
    setPreview({ status: 'loading' })

    void fetch(file.url, {
      credentials: 'include',
      signal: controller.signal,
      headers: { Accept: 'text/csv,text/plain;q=0.9,*/*;q=0.1' },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Não foi possível abrir o arquivo (erro ${response.status}).`)
        }
        return response.text()
      })
      .then((content) => setPreview({ status: 'success', data: parseCsv(content) }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setPreview({
          status: 'error',
          message: error instanceof Error
            ? error.message
            : 'Não foi possível visualizar este arquivo.',
        })
      })

    return () => controller.abort()
  }, [file.url, open])

  return (
    <Sheet open={open} onOpenChange={changeOpen}>
      <span className="group/download my-3 flex w-full max-w-xl items-center gap-2 rounded-xl border border-border bg-muted/45 p-2.5 text-foreground shadow-soft transition-all hover:border-brand-accent/55 hover:bg-muted/75 hover:shadow-card">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={`Visualizar ${file.displayName}`}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent"
        >
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-emerald-500/12 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-400">
            <FileSpreadsheet className="size-5" strokeWidth={1.9} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold" title={file.displayName}>
              {file.displayName}
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              Planilha CSV · Clique para visualizar
            </span>
          </span>
        </button>

        <a
          href={file.url}
          download={file.filename}
          aria-label={`Baixar ${file.filename}`}
          title="Baixar arquivo"
          className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground no-underline transition-colors hover:bg-background/70 hover:text-brand-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent"
        >
          <Download className="size-4" aria-hidden />
        </a>
      </span>

      <SheetContent
        side="right"
        showCloseButton={false}
        className={cn(
          'w-full max-w-none gap-0 overflow-hidden border-border p-0 data-[side=right]:w-full data-[side=right]:max-w-none data-[side=right]:sm:max-w-none',
          expanded
            ? 'sm:w-full data-[side=right]:sm:w-full'
            : 'sm:w-1/2 data-[side=right]:sm:w-1/2',
        )}
      >
        <SheetHeader className="flex-row items-center gap-3 border-b border-border px-4 py-3 sm:px-5">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-emerald-500/12 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-400">
            <FileSpreadsheet className="size-5" strokeWidth={1.9} />
          </span>
          <div className="min-w-0 flex-1">
            <SheetTitle className="truncate" title={file.displayName}>
              {file.displayName}
            </SheetTitle>
            <SheetDescription>Visualização do arquivo CSV</SheetDescription>
          </div>
          <a
            href={file.url}
            download={file.filename}
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-brand-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent"
            aria-label="Baixar arquivo CSV"
            title="Baixar"
          >
            <Download className="size-4" />
          </a>
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="hidden size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent sm:grid"
            aria-label={expanded ? 'Restaurar tamanho do visualizador' : 'Expandir visualizador para tela cheia'}
            title={expanded ? 'Restaurar tamanho' : 'Tela cheia'}
          >
            {expanded
              ? <Minimize2 className="size-4" />
              : <Maximize2 className="size-4" />}
          </button>
          <SheetClose
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent"
            aria-label="Fechar visualizador"
            title="Fechar"
          >
            <X className="size-4" />
          </SheetClose>
        </SheetHeader>

        {preview.status === 'success' && preview.data.truncated && (
          <div className="border-b border-border bg-brand-accent/8 px-4 py-2 text-xs text-muted-foreground sm:px-5">
            Exibindo as primeiras {MAX_PREVIEW_ROWS.toLocaleString('pt-BR')} linhas. Baixe o arquivo para consultar o conteúdo completo.
          </div>
        )}

        {(preview.status === 'idle' || preview.status === 'loading') && (
          <div className="grid min-h-0 flex-1 place-items-center bg-background p-6 text-center">
            <div>
              <LoaderCircle className="mx-auto size-7 animate-spin text-brand-accent" />
              <p className="mt-3 text-sm font-medium">Carregando planilha...</p>
            </div>
          </div>
        )}

        {preview.status === 'error' && (
          <div className="grid min-h-0 flex-1 place-items-center bg-background p-6 text-center">
            <div className="max-w-sm">
              <AlertCircle className="mx-auto size-8 text-destructive" />
              <p className="mt-3 font-semibold">Não foi possível abrir a prévia</p>
              <p className="mt-1 text-sm text-muted-foreground">{preview.message}</p>
              <a
                href={file.url}
                download={file.filename}
                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground no-underline transition-colors hover:bg-brand/90"
              >
                <Download className="size-4" />
                Baixar arquivo
              </a>
            </div>
          </div>
        )}

        {preview.status === 'success' && <CsvTable preview={preview.data} />}
      </SheetContent>
    </Sheet>
  )
}
