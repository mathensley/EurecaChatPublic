'use client'

import { Children, isValidElement, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { MermaidDiagram } from './mermaid-diagram'
import {
  Bot,
  Check,
  CircleCheck,
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  FileText,
  LoaderCircle,
  Volume2,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { feedbackService, type FeedbackChoice } from '@/services'
import type { Message } from '@/types'
import { CsvDownloadCard, type CsvFileInfo } from './csv-viewer'
import { PdfDownloadCard } from './pdf-download-card'

const MARKDOWN_REMARK_PLUGINS = [remarkGfm]

// ── Sub-components ──────────────────────────────────────────────────────────

function AssistantAvatar() {
  return (
    <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand text-brand-foreground shadow-soft ring-1 ring-inset ring-white/10 dark:bg-brand-deep">
      <Bot className="size-5 text-brand-accent" strokeWidth={2} />
    </div>
  )
}

interface ActionButtonProps {
  label: string
  active?: boolean
  onClick?: () => void
  children: React.ReactNode
}

function ActionButton({ label, active, onClick, children }: ActionButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            onClick={onClick}
            aria-label={label}
            title={label}
            className={cn(
              'grid size-8 place-items-center rounded-lg text-muted-foreground transition-all duration-150 hover:bg-muted hover:text-brand active:scale-90',
              active && 'bg-accent text-brand',
            )}
          />
        }
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

async function copyToClipboard(text: string) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  try {
    if (!document.execCommand('copy')) throw new Error('Não foi possível copiar')
  } finally {
    textarea.remove()
  }
}

function fileExtension(filename: string) {
  const extension = filename.split('.').pop()
  return extension && extension !== filename ? extension.toUpperCase() : 'ARQUIVO'
}

interface DownloadFileInfo extends CsvFileInfo {
  type: 'csv' | 'pdf'
}

function nodeText(node: React.ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (isValidElement<{ children?: React.ReactNode }>(node)) {
    return Children.toArray(node.props.children).map(nodeText).join('')
  }
  return ''
}

function markdownLinkLabel(children: React.ReactNode): string {
  return Children.toArray(children)
    .map(nodeText)
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
}

function downloadFileInfo(href?: string, label?: string): DownloadFileInfo | null {
  if (!href) return null

  const cleanHref = href.split(/[?#]/, 1)[0]
  const scopedDownload = /(?:^|\/)downloads\/([^/?#]+)\/((?:[^/?#]+\.csv)|(?:[^/?#]+\.pdf))$/i.exec(cleanHref)
  if (!scopedDownload) return null

  const [, encodedWorkdir, encodedFilename] = scopedDownload

  let filename: string
  let workdir: string
  try {
    filename = decodeURIComponent(encodedFilename)
  } catch {
    filename = encodedFilename
  }
  try {
    workdir = decodeURIComponent(encodedWorkdir)
  } catch {
    workdir = encodedWorkdir
  }

  const type = filename.toLowerCase().endsWith('.pdf') ? 'pdf' : 'csv'
  const displayName = label && label !== filename
    ? label
    : type === 'pdf'
      ? 'Fluxograma completo em PDF'
      : 'Dados completos da consulta em CSV'

  return {
    // Reconstrói a URL a partir dos dois segmentos esperados, sem aceitar
    // caminhos extras eventualmente presentes na resposta do modelo.
    url: `/downloads/${encodeURIComponent(workdir)}/${encodeURIComponent(filename)}`,
    filename,
    displayName,
    type,
  }
}

function incompleteCodeBlockStart(content: string) {
  const fences = [...content.matchAll(/```/g)]
  return fences.length % 2 === 0 ? null : fences.at(-1)?.index ?? null
}

function hideIncompleteCodeBlock(content: string) {
  const start = incompleteCodeBlockStart(content)
  return start === null ? content : content.slice(0, start).trimEnd()
}

// ── MessageBubble ───────────────────────────────────────────────────────────

interface MessageBubbleProps {
  message: Message
  agentSteps?: AgentStep[]
  agentStepsCompleted?: boolean
  isStreaming?: boolean
  onDiagramRendered?: () => void
  feedbackContext?: {
    question: string
    conversationId?: string | null
    userType: 'user' | 'anon'
    userId?: string | number | null
  }
}

export interface AgentStep {
  id: string
  content: string
  completed: boolean
}

function cleanStepContent(content: string) {
  return content
    .replace(/<\/?tool_preamble>/g, '')
    .replace(/\s*\{[\s\S]*\}\}?\s*$/g, '')
    .trim()
}

function uniqueVisibleSteps(steps: AgentStep[]) {
  const seen = new Set<string>()
  return steps.filter((step) => {
    const normalized = cleanStepContent(step.content).toLocaleLowerCase('pt-BR')
    if (!normalized || seen.has(normalized)) return false
    seen.add(normalized)
    return true
  })
}

function toolProgressMessage(content: string) {
  const normalized = content.toLocaleLowerCase('pt-BR')

  if (normalized.includes('calend')) return 'Consultando o calendário acadêmico…'
  if (/disciplina|ementa|turma|vaga|horário|plano de (curso|aula)|matrícula|grade curricular|professor/.test(normalized)) {
    return 'Consultando informações acadêmicas…'
  }
  if (/estudante|ingressante|histórico|seus dados|estágio/.test(normalized)) {
    return 'Consultando dados acadêmicos…'
  }
  if (/curso|setor/.test(normalized)) {
    return 'Consultando informações dos cursos…'
  }
  return 'Buscando informações oficiais…'
}

function progressMessage(steps: AgentStep[], completed: boolean) {
  if (completed) return 'Etapas concluídas'
  if (steps.length > 0 && steps.every((step) => step.completed)) {
    return 'Organizando a resposta…'
  }

  const activeStep = [...steps].reverse().find((step) => !step.completed) ?? steps.at(-1)
  if (!activeStep) return 'Analisando sua pergunta…'
  if (activeStep.id.startsWith('tool:')) return toolProgressMessage(activeStep.content)

  const hasUsedTool = steps.some((step) => step.id.startsWith('tool:'))
  return hasUsedTool ? 'Verificando os dados encontrados…' : 'Analisando sua pergunta…'
}

function AgentStepsContent({ steps, completed }: { steps: AgentStep[]; completed: boolean }) {
  const [open, setOpen] = useState(false)
  const visibleSteps = uniqueVisibleSteps(steps)
  const progress = progressMessage(steps, completed)

  return (
    <div className="min-w-0 py-0.5" aria-label="Etapas da consulta">
      <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
        <span className="grid size-5 shrink-0 place-items-center text-brand-accent" aria-hidden>
          {completed
            ? <CircleCheck className="size-4" strokeWidth={2} />
            : <LoaderCircle className="size-4 animate-spin" strokeWidth={2} />}
        </span>
        <span className="min-w-0 truncate font-medium">{progress}</span>
      </div>

      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="ml-7 mt-0.5 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-brand"
      >
        {open
          ? <ChevronDown className="size-3.5 shrink-0" />
          : <ChevronRight className="size-3.5 shrink-0" />}
        {open ? 'Ocultar etapas' : 'Ver etapas da consulta'}
      </button>

      {open && (
        <ol className="mt-3 space-y-2.5">
          {visibleSteps.map((step, index) => {
            const isDone = completed || step.completed
            return (
              <li key={step.id} className="relative flex gap-2.5 pl-0.5">
                {index < visibleSteps.length - 1 && (
                  <span className="absolute left-[0.55rem] top-5 h-[calc(100%+0.25rem)] w-px bg-border" />
                )}
                <span className="relative z-10 mt-0.5 grid size-5 shrink-0 place-items-center bg-background text-brand-accent">
                  {isDone
                    ? <CircleCheck className="size-4" strokeWidth={2} />
                    : <LoaderCircle className="size-4 animate-spin" strokeWidth={2} />}
                </span>
                <p className="min-w-0 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                  {cleanStepContent(step.content)}
                </p>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

export function AgentSteps({ steps, completed }: { steps: AgentStep[]; completed: boolean }) {
  if (steps.length === 0) return null

  return (
    <div className="flex animate-fade-up gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1">
        <AgentStepsContent steps={steps} completed={completed} />
      </div>
    </div>
  )
}

export function MessageBubble({
  message,
  agentSteps = [],
  agentStepsCompleted = false,
  isStreaming = false,
  onDiagramRendered,
  feedbackContext,
}: MessageBubbleProps) {
  const [feedbackChoice, setFeedbackChoice] = useState<FeedbackChoice | null>(null)
  const [submittedChoice, setSubmittedChoice] = useState<FeedbackChoice | null>(null)
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackStatus, setFeedbackStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [copied, setCopied] = useState(false)
  const copyResetRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const feedbackResetRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const feedbackSubmissionRef = useRef<{ id: string; createdAt: string } | null>(null)
  const feedbackAreaRef = useRef<HTMLDivElement>(null)
  const onDiagramRenderedRef = useRef(onDiagramRendered)
  const markdownContent = isStreaming
    ? hideIncompleteCodeBlock(message.content)
    : message.content
  const pendingCodeBlock = isStreaming && incompleteCodeBlockStart(message.content) !== null
  const isGeneratingImage = isStreaming && (
    pendingCodeBlock || message.content.includes('```mermaid')
  )

  useEffect(() => {
    onDiagramRenderedRef.current = onDiagramRendered
  }, [onDiagramRendered])

  const notifyDiagramRendered = useCallback(() => {
    onDiagramRenderedRef.current?.()
  }, [])

  const markdownComponents = useMemo<Components>(() => ({
    pre: ({ children, ...props }) => {
      const containsMermaid = Children.toArray(children).some(
        (child) => isValidElement<{ className?: string }>(child)
          && child.props.className?.includes('language-mermaid'),
      )

      if (containsMermaid) return <>{children}</>

      return <pre {...props}>{children}</pre>
    },
    a: ({ children, href, ...props }) => {
      const downloadFile = downloadFileInfo(href, markdownLinkLabel(children))

      if (downloadFile) {
        return downloadFile.type === 'pdf'
          ? <PdfDownloadCard file={downloadFile} />
          : <CsvDownloadCard file={downloadFile} />
      }

      return (
        <a
          {...props}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex max-w-full items-center gap-1 text-brand-accent underline underline-offset-2 transition-colors hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent"
        >
          <ExternalLink className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate">{children}</span>
        </a>
      )
    },
    code: ({ className, children, ...props }) => {
      const language = /language-(\w+)/.exec(className ?? '')?.[1]

      if (language === 'mermaid') {
        const chart = String(children).replace(/\n$/, '')
        return (
          <MermaidDiagram
            chart={chart}
            deferRender={isStreaming}
            onRendered={notifyDiagramRendered}
          />
        )
      }

      return <code className={className} {...props}>{children}</code>
    },
    table: ({ children }) => (
      <div
        role="region"
        aria-label="Tabela com rolagem horizontal"
        tabIndex={0}
        className="my-4 w-full overflow-x-auto rounded-xl border border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent/40"
      >
        <table className="w-max min-w-full border-collapse text-left text-sm [&_tbody_tr:nth-child(even)]:bg-muted/35 [&_tr:last-child_td]:border-b-0">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }) => (
      <thead className="bg-brand/7 text-brand">{children}</thead>
    ),
    tr: ({ children }) => (
      <tr className="transition-colors hover:bg-muted/60">{children}</tr>
    ),
    th: ({ children }) => (
      <th className="whitespace-nowrap border-r border-b border-border px-3 py-2.5 font-semibold last:border-r-0">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="whitespace-nowrap border-r border-b border-border px-3 py-2.5 align-top last:border-r-0">
        {children}
      </td>
    ),
  }), [isStreaming, notifyDiagramRendered])

  useEffect(() => {
    return () => {
      if (copyResetRef.current) clearTimeout(copyResetRef.current)
      if (feedbackResetRef.current) clearTimeout(feedbackResetRef.current)
    }
  }, [])

  useEffect(() => {
    if (!feedbackChoice) return

    function closeOnOutsideClick(event: PointerEvent) {
      if (feedbackStatus === 'sending') return
      if (!feedbackAreaRef.current?.contains(event.target as Node)) {
        setFeedbackChoice(null)
        setFeedbackText('')
        setFeedbackStatus('idle')
      }
    }

    document.addEventListener('pointerdown', closeOnOutsideClick)
    return () => document.removeEventListener('pointerdown', closeOnOutsideClick)
  }, [feedbackChoice, feedbackStatus])

  async function copyMessage() {
    try {
      await copyToClipboard(message.content)
      setCopied(true)
      if (copyResetRef.current) clearTimeout(copyResetRef.current)
      copyResetRef.current = setTimeout(() => setCopied(false), 2_000)
    } catch {
      setCopied(false)
    }
  }

  function openFeedback(choice: FeedbackChoice) {
    feedbackSubmissionRef.current = null
    setFeedbackChoice(choice)
    setFeedbackText('')
    setFeedbackStatus('idle')
  }

  async function sendFeedback() {
    if (!feedbackChoice || !feedbackContext || feedbackStatus === 'sending') return
    const submission = feedbackSubmissionRef.current ?? {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
    }
    feedbackSubmissionRef.current = submission
    const defaultText = feedbackChoice === 'positive' ? 'Gostei!' : 'Não gostei!'

    setFeedbackStatus('sending')
    try {
      await feedbackService.save({
        feedbackId: submission.id,
        createdAt: submission.createdAt,
        question: feedbackContext.question,
        answer: message.content,
        feedback: feedbackText.trim() || defaultText,
        choice: feedbackChoice,
        conversationId: feedbackContext.conversationId,
        userType: feedbackContext.userType,
        userId: feedbackContext.userId,
      })
      setSubmittedChoice(feedbackChoice)
      feedbackSubmissionRef.current = null
      setFeedbackChoice(null)
      setFeedbackText('')
      setFeedbackStatus('sent')
      if (feedbackResetRef.current) clearTimeout(feedbackResetRef.current)
      feedbackResetRef.current = setTimeout(() => setFeedbackStatus('idle'), 3_000)
    } catch {
      setFeedbackStatus('error')
    }
  }

  function speak() {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(message.content)
    utterance.lang = 'pt-BR'
    window.speechSynthesis.speak(utterance)
  }

  if (message.role === 'user') {
    return (
      <div className="group flex animate-fade-up justify-end">
        <div className="max-w-[85%] md:max-w-[70%]">
          <p className="mb-1.5 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Você
          </p>
          <div className="rounded-2xl rounded-tr-md bg-primary px-4 py-3 text-[0.95rem] leading-relaxed text-primary-foreground shadow-soft">
            {message.attachments && message.attachments.length > 0 && (
              <div className="mb-2.5 flex flex-wrap justify-end gap-1.5">
                {message.attachments.map((filename, index) => (
                  <div
                    key={`${filename}-${index}`}
                    title={filename}
                    className="flex min-w-0 max-w-full items-center gap-2 rounded-xl border border-white/15 bg-white/10 px-2.5 py-2 sm:max-w-72"
                  >
                    <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-white/10">
                      <FileText className="size-3.5" />
                    </span>
                    <span className="min-w-0 text-left">
                      <span className="block truncate text-xs font-medium">{filename}</span>
                      <span className="block text-[0.65rem] leading-4 text-primary-foreground/65">
                        {fileExtension(filename)}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            )}
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          </div>
          <div className="mt-1 flex justify-end opacity-100 transition-opacity [@media(hover:hover)]:pointer-events-none [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-focus-within:pointer-events-auto [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:pointer-events-auto [@media(hover:hover)]:group-hover:opacity-100">
            <ActionButton
              label={copied ? 'Copiado' : 'Copiar mensagem'}
              active={copied}
              onClick={() => void copyMessage()}
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            </ActionButton>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex animate-fade-up gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1">
        <p className="mb-1.5 text-sm font-semibold text-brand">Assistente</p>
        {agentSteps.length > 0 && (
          <div className="mb-2">
            <AgentStepsContent steps={agentSteps} completed={agentStepsCompleted} />
          </div>
        )}
        <div className="overflow-hidden rounded-2xl rounded-tl-md border border-border bg-card shadow-soft">
          <div className="min-w-0 px-4 py-3 text-[0.95rem] leading-relaxed text-card-foreground [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_ol]:ml-5 [&_ol]:list-decimal [&_p+p]:mt-3 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_ul]:ml-5 [&_ul]:list-disc">
            <ReactMarkdown
              remarkPlugins={MARKDOWN_REMARK_PLUGINS}
              components={markdownComponents}
            >
              {markdownContent}
            </ReactMarkdown>
            {isGeneratingImage && (
              <div role="status" className="my-3 flex items-center gap-2 rounded-lg border border-border bg-muted/50 p-3 text-sm text-muted-foreground">
                <LoaderCircle className="size-4 animate-spin text-brand-accent" />
                Carregando imagem…
              </div>
            )}
          </div>
        </div>
        <div ref={feedbackAreaRef}>
          <div className="mt-2 flex items-center gap-0.5">
            <ActionButton
              label={copied ? 'Copiado' : 'Copiar resposta'}
              active={copied}
              onClick={() => void copyMessage()}
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            </ActionButton>
            <ActionButton label="Ouvir resposta" onClick={speak}>
              <Volume2 className="size-4" />
            </ActionButton>
            <ActionButton
              label="Resposta útil"
              active={
                feedbackChoice
                  ? feedbackChoice === 'positive'
                  : submittedChoice === 'positive'
              }
              onClick={() => openFeedback('positive')}
            >
              <ThumbsUp className="size-4" />
            </ActionButton>
            <ActionButton
              label="Resposta não útil"
              active={
                feedbackChoice
                  ? feedbackChoice === 'negative'
                  : submittedChoice === 'negative'
              }
              onClick={() => openFeedback('negative')}
            >
              <ThumbsDown className="size-4" />
            </ActionButton>
            {feedbackStatus === 'sent' && (
              <span role="status" className="ml-1 text-xs text-muted-foreground">
                Feedback enviado
              </span>
            )}
          </div>

          {feedbackChoice && (
            <div className="mt-2 max-w-md rounded-xl border border-border bg-card p-2.5 shadow-soft">
              <p className="mb-2 text-xs font-medium text-foreground">
                {feedbackChoice === 'positive'
                  ? 'O que foi útil? (opcional)'
                  : 'O que poderia melhorar? (opcional)'}
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  autoFocus
                  type="text"
                  value={feedbackText}
                  maxLength={4000}
                  disabled={feedbackStatus === 'sending'}
                  onChange={(event) => setFeedbackText(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') void sendFeedback()
                    if (event.key === 'Escape') setFeedbackChoice(null)
                  }}
                  placeholder={feedbackChoice === 'positive' ? 'Gostei!' : 'Não gostei!'}
                  aria-label="Comentário do feedback"
                  className="h-8 min-w-0 flex-1 rounded-lg border border-border bg-background px-2.5 text-xs text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 disabled:opacity-60"
                />
                <button
                  type="button"
                  disabled={feedbackStatus === 'sending'}
                  onClick={() => void sendFeedback()}
                  className="h-8 shrink-0 rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-brand-deep disabled:opacity-60"
                >
                  {feedbackStatus === 'sending' ? 'Enviando…' : 'Enviar'}
                </button>
              </div>
              {feedbackStatus === 'error' && (
                <p role="alert" className="mt-1.5 text-xs text-destructive">
                  Não foi possível enviar. Tente novamente.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── LoadingBubble ────────────────────────────────────────────────────────────

export function LoadingBubble({ status = 'Processando a pergunta' }: { status?: string }) {
  return (
    <div className="flex animate-fade-up gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1">
        <p className="mb-1.5 text-sm font-semibold text-brand">Assistente</p>
        <div className="flex items-center gap-2 py-1 text-muted-foreground">
          <span className="font-medium">{status}</span>
          <span className="flex items-end gap-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="size-1.5 rounded-full bg-brand-accent"
                style={{ animation: `eureca-dot 1.2s ease-in-out ${i * 0.18}s infinite` }}
              />
            ))}
          </span>
        </div>
      </div>
    </div>
  )
}
