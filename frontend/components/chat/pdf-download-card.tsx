'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle,
  Download,
  FileText,
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

export interface PdfFileInfo {
  url: string
  filename: string
  displayName: string
}

type PreviewState =
  | { status: 'idle' | 'loading' }
  | { status: 'success'; url: string }
  | { status: 'error'; message: string }

export function PdfDownloadCard({ file }: { file: PdfFileInfo }) {
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
    let previewUrl: string | null = null
    setPreview({ status: 'loading' })

    void fetch(file.url, {
      credentials: 'include',
      signal: controller.signal,
      headers: { Accept: 'application/pdf,*/*;q=0.1' },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Não foi possível abrir o arquivo (erro ${response.status}).`)
        }

        const content = await response.arrayBuffer()
        return new Blob([content], { type: 'application/pdf' })
      })
      .then((pdf) => {
        if (controller.signal.aborted) return
        previewUrl = URL.createObjectURL(pdf)
        setPreview({ status: 'success', url: previewUrl })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setPreview({
          status: 'error',
          message: error instanceof Error
            ? error.message
            : 'Não foi possível visualizar este arquivo.',
        })
      })

    return () => {
      controller.abort()
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [file.url, open])

  return (
    <Sheet open={open} onOpenChange={changeOpen}>
      <span className="group/download my-3 flex w-full max-w-xl items-center gap-2 rounded-xl border border-border bg-muted/45 p-2.5 text-foreground shadow-soft transition-all hover:border-red-500/45 hover:bg-muted/75 hover:shadow-card">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={`Visualizar ${file.displayName}`}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60"
        >
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-red-500/12 text-red-600 dark:bg-red-400/15 dark:text-red-400">
            <FileText className="size-5" strokeWidth={1.9} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold" title={file.displayName}>
              {file.displayName}
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              Documento PDF · Clique para visualizar
            </span>
          </span>
        </button>

        <a
          href={file.url}
          download={file.filename}
          aria-label={`Baixar ${file.filename}`}
          title="Baixar arquivo"
          className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground no-underline transition-colors hover:bg-background/70 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60 dark:hover:text-red-400"
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
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-red-500/12 text-red-600 dark:bg-red-400/15 dark:text-red-400">
            <FileText className="size-5" strokeWidth={1.9} />
          </span>
          <div className="min-w-0 flex-1">
            <SheetTitle className="truncate" title={file.displayName}>
              {file.displayName}
            </SheetTitle>
            <SheetDescription>Visualização do arquivo PDF</SheetDescription>
          </div>
          <a
            href={file.url}
            download={file.filename}
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60 dark:hover:text-red-400"
            aria-label="Baixar arquivo PDF"
            title="Baixar"
          >
            <Download className="size-4" />
          </a>
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="hidden size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60 sm:grid"
            aria-label={expanded ? 'Restaurar tamanho do visualizador' : 'Expandir visualizador para tela cheia'}
            title={expanded ? 'Restaurar tamanho' : 'Tela cheia'}
          >
            {expanded
              ? <Minimize2 className="size-4" />
              : <Maximize2 className="size-4" />}
          </button>
          <SheetClose
            className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60"
            aria-label="Fechar visualizador"
            title="Fechar"
          >
            <X className="size-4" />
          </SheetClose>
        </SheetHeader>

        {(preview.status === 'idle' || preview.status === 'loading') && (
          <div className="grid min-h-0 flex-1 place-items-center bg-muted/30 p-6 text-center">
            <div>
              <LoaderCircle className="mx-auto size-7 animate-spin text-red-600 dark:text-red-400" />
              <p className="mt-3 text-sm font-medium">Carregando documento...</p>
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

        {preview.status === 'success' && (
          <iframe
            src={preview.url}
            title={`Visualização de ${file.filename}`}
            className="min-h-0 flex-1 border-0 bg-muted/30"
          />
        )}
      </SheetContent>
    </Sheet>
  )
}
