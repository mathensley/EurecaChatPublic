'use client'

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { ChatSidebar } from './sidebar'
import { ChatHeader } from './chat-header'
import { ChatInput } from './chat-input'
import { AgentSteps, MessageBubble, LoadingBubble, type AgentStep } from './message-bubble'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn, truncate } from '@/lib/utils'
import { useConversations } from '@/hooks/use-conversations'
import { useMessages } from '@/hooks/use-messages'
import { ApiError, authService, chatService, conversationsService, wsService } from '@/services'
import type {
  AuthSession,
  SocketFile,
  WsErrorPayload,
  WsFinalPayload,
  WsReclassifiedResponsePayload,
  WsResponseStartPayload,
  WsStepPayload,
  WsStatusPayload,
  WsTokenPayload,
} from '@/types'

const SUGGESTION_GROUPS = [
  [
    'Qual o semestre atual?',
    'Qual o fluxograma do curso Engenharia Civil?',
    'Quais cursos a UFCG oferece?',
    'Quantos alunos ingressaram na UFCG em 2026.1?',
  ],
  [
    'Quantos cursos tem na UFCG?',
    'De onde vem os estudantes da UFCG?',
    'Onde é ofertado Medicina?',
    'Qual a ementa da disciplina de Cálculo 1 de Engenharia Elétrica?',
  ],
  [
    'Quantos alunos se formaram no Centro de Humanidades em 2025.2?',
    'Quais são os cursos oferecidos pela UFCG?',
    //'Como funciona o processo de matrícula?',
    'Quantos professores têm no CEEI?',
    'Quantos estudantes existem na UFCG?',
  ],
  [
    'Qual o calendário acadêmico?',
    'Faça um gráfico de barras sobre o número de alunos ativos por campus.',
    'Quando começa o próximo semestre?',
    'Quantos estudantes ingressaram em computação em 2026.1?',
  ]
]

const SIDEBAR_STORAGE_KEY = 'eurecachat.sidebar-open'

function countMermaidDiagrams(content: string) {
  return [...content.matchAll(/^(?:```|~~~)[ \t]*mermaid\b/gim)].length
}

function formatFirstName(name?: string) {
  const firstName = name?.trim().split(/\s+/)[0]
  if (!firstName) return null

  const normalized = firstName.toLocaleLowerCase('pt-BR')
  return normalized.charAt(0).toLocaleUpperCase('pt-BR') + normalized.slice(1)
}

function getDayPeriod(hour: number) {
  if (hour >= 5 && hour < 12) return 'Bom dia'
  if (hour >= 12 && hour < 18) return 'Boa tarde'
  return 'Boa noite'
}

function nameSuffix(firstName: string | null) {
  return firstName ? `, ${firstName}` : ''
}

const WELCOME_VARIANTS = [
  {
    title: (firstName: string | null, dayPeriod: string) =>
      `${dayPeriod}${nameSuffix(firstName)}! Como posso ajudar?`,
    description:
      'Faça uma pergunta sobre a UFCG e o EurecaChat pesquisará as informações para você.',
  },
  {
    title: (firstName: string | null) =>
      `Bem-vindo ao EurecaChat${nameSuffix(firstName)}!`,
    description:
      'Faça uma pergunta sobre a UFCG e eu buscarei as informações para você.',
  },
  {
    title: (firstName: string | null) => `Olá${nameSuffix(firstName)}! 👋`,
    description: 'Estou aqui para ajudar com informações sobre a UFCG.',
  },
  {
    title: (firstName: string | null) =>
      `O que você gostaria de saber${nameSuffix(firstName)}?`,
    description:
      'Faça uma pergunta sobre a UFCG e o EurecaChat pesquisará as informações para você.',
  },
  {
    title: (firstName: string | null) => (
      <>
        Olá{nameSuffix(firstName)}!
        <br />
        Seja bem-vindo ao EurecaChat.
      </>
    ),
    description:
      'Posso ajudar você a encontrar informações oficiais da UFCG. Basta fazer sua pergunta.',
  }
]

function extractResponseText(content: unknown): string {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) return content.map(extractResponseText).join('')
  if (
    content
    && typeof content === 'object'
    && 'type' in content
    && (content.type === 'text' || content.type === 'output_text')
    && 'text' in content
    && typeof content.text === 'string'
  ) {
    return content.text
  }
  return ''
}

function removeToolPreambleMarkers(content: string): string {
  return content.replace(/<\/?tool_preamble>/g, '')
}

function EmptyState({ onPick, userName }: { onPick: (text: string) => void; userName?: string }) {
  const firstName = formatFirstName(userName)
  const [variantIndex, setVariantIndex] = useState(0)
  const [suggestionGroupIndex, setSuggestionGroupIndex] = useState(0)
  const [dayPeriod, setDayPeriod] = useState('Olá')
  const variant = WELCOME_VARIANTS[variantIndex]
  const suggestions = SUGGESTION_GROUPS[suggestionGroupIndex]

  useEffect(() => {
    setVariantIndex(Math.floor(Math.random() * WELCOME_VARIANTS.length))
    setSuggestionGroupIndex(Math.floor(Math.random() * SUGGESTION_GROUPS.length))
    setDayPeriod(getDayPeriod(new Date().getHours()))
  }, [])

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-6 grid size-14 place-items-center rounded-2xl bg-brand text-brand-accent shadow-card dark:bg-brand-deep">
        <Sparkles className="size-7" />
      </div>
      <h1 className="text-balance text-3xl font-semibold tracking-tight text-brand md:text-4xl">
        {variant.title(firstName, dayPeriod)}
      </h1>
      <p className="mt-3 text-pretty text-[0.95rem] leading-relaxed text-muted-foreground">
        {variant.description}
      </p>
      <div className="mt-8 grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onPick(suggestion)}
            className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm leading-snug text-foreground shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-accent/60 hover:shadow-card"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}

function fileToSocketPayload(file: File): Promise<SocketFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Não foi possível ler ${file.name}`))
    reader.onload = () => {
      const value = String(reader.result ?? '')
      resolve({ filename: file.name, content: value.split(',', 2)[1] ?? '' })
    }
    reader.readAsDataURL(file)
  })
}

export function ChatView() {
  const {
    conversations,
    setConversations,
    activeId,
    setActiveId,
    addConversation,
    removeConversation,
    selectConversation,
  } = useConversations()
  const {
    messages,
    setMessages,
    addUserMessage,
    addAssistantPlaceholder,
    updateAssistantMessage,
    reset: resetMessages,
  } = useMessages()

  const [session, setSession] = useState<AuthSession | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [status, setStatus] = useState('Processando a pergunta')
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([])
  const [stepsMessageId, setStepsMessageId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [inputFocusRequest, setInputFocusRequest] = useState(0)
  const [scrollRequest, setScrollRequest] = useState(0)
  const [restoringHistoryLayout, setRestoringHistoryLayout] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null)
  const [deletingConversation, setDeletingConversation] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)
  const forceScrollRef = useRef(false)
  const scrollBehaviorRef = useRef<ScrollBehavior>('auto')
  const pendingMessageRef = useRef<string | null>(null)
  const diagramScrollTargetRef = useRef<{
    messageIds: Set<string>
    remaining: number
  } | null>(null)
  const diagramScrollFallbackRef = useRef<number | null>(null)
  const finalLayoutObserverRef = useRef<ResizeObserver | null>(null)
  const finalLayoutTimerRef = useRef<number | null>(null)
  const finalLayoutMaxTimerRef = useRef<number | null>(null)
  const revealHistoryAfterScrollRef = useRef(false)
  const streamedTextRef = useRef('')
  const streamRenderFrameRef = useRef<number | null>(null)
  const activeIdRef = useRef<string | null>(null)
  const sessionRef = useRef<AuthSession | null>(null)
  const lastQuestionRef = useRef('')
  const newConversationQuestionRef = useRef<string | null>(null)

  const performFinalScroll = useCallback((behavior: ScrollBehavior) => {
    forceScrollRef.current = true
    scrollBehaviorRef.current = behavior
    setScrollRequest((current) => current + 1)
  }, [])

  const clearFinalScrollSettlement = useCallback(() => {
    finalLayoutObserverRef.current?.disconnect()
    finalLayoutObserverRef.current = null

    if (finalLayoutTimerRef.current !== null) {
      window.clearTimeout(finalLayoutTimerRef.current)
      finalLayoutTimerRef.current = null
    }
    if (finalLayoutMaxTimerRef.current !== null) {
      window.clearTimeout(finalLayoutMaxTimerRef.current)
      finalLayoutMaxTimerRef.current = null
    }
  }, [])

  const requestFinalScroll = useCallback((behavior: ScrollBehavior = 'smooth') => {
    clearFinalScrollSettlement()

    const scrollElement = scrollRef.current
    const contentElement = scrollElement?.firstElementChild
    if (!scrollElement || !contentElement || typeof ResizeObserver === 'undefined') {
      performFinalScroll(behavior)
      return
    }

    const finish = () => {
      clearFinalScrollSettlement()
      performFinalScroll(behavior)
    }
    const waitUntilStable = () => {
      if (finalLayoutTimerRef.current !== null) {
        window.clearTimeout(finalLayoutTimerRef.current)
      }
      // Mermaid pode inserir o SVG antes de concluir seus cálculos de tamanho.
      // Só medimos o fim da conversa quando o conteúdo para de redimensionar.
      finalLayoutTimerRef.current = window.setTimeout(finish, 300)
    }

    const observer = new ResizeObserver(waitUntilStable)
    finalLayoutObserverRef.current = observer
    observer.observe(contentElement)
    waitUntilStable()

    // Evita manter o scroll pendente indefinidamente caso alguma animação
    // externa continue alterando o layout.
    finalLayoutMaxTimerRef.current = window.setTimeout(finish, 3_000)
  }, [clearFinalScrollSettlement, performFinalScroll])

  const clearDiagramScrollFallback = useCallback(() => {
    if (diagramScrollFallbackRef.current === null) return
    window.clearTimeout(diagramScrollFallbackRef.current)
    diagramScrollFallbackRef.current = null
  }, [])

  useEffect(() => {
    activeIdRef.current = activeId
  }, [activeId])

  useEffect(() => {
    const savedSidebarState = window.localStorage.getItem(SIDEBAR_STORAGE_KEY)
    if (savedSidebarState !== null) setSidebarOpen(savedSidebarState === 'true')
  }, [])

  useEffect(() => {
    sessionRef.current = session
  }, [session])

  useEffect(() => {
    let cancelled = false

    async function initializeSession() {
      try {
        const user = await authService.validate()
        if (cancelled) return

        if (!user) {
          setSession(null)
          sessionRef.current = null
          setConversations([])
          setAuthReady(true)
          return
        }

        const restoredSession = { user }
        setSession(restoredSession)
        sessionRef.current = restoredSession
        setAuthReady(true)

        try {
          const response = await conversationsService.list()
          if (!cancelled) setConversations(response.data)
        } catch (cause) {
          if (cancelled) return
          if (cause instanceof ApiError && cause.status === 401) {
            try {
              await authService.logout()
            } catch {
              setError('Não foi possível encerrar a sessão expirada. Recarregue a página.')
              return
            }
            if (cancelled) return
            wsService.disconnect()
            setSession(null)
            sessionRef.current = null
            setConversations([])
            setError('Sua sessão expirou. Entre novamente para acessar o histórico.')
            wsService.connect()
            return
          }
          setError('Sua sessão está ativa, mas não foi possível carregar o histórico.')
        }
      } catch (cause) {
        if (cancelled) return
        if (cause instanceof ApiError && cause.status === 401) {
          setSession(null)
          sessionRef.current = null
          setConversations([])
          setAuthReady(true)
          return
        }
        setError('Não foi possível verificar sua sessão. Recarregue a página para tentar novamente.')
      }
    }

    void initializeSession()
    return () => {
      cancelled = true
    }
  }, [setConversations])

  useEffect(() => () => {
    if (streamRenderFrameRef.current !== null) {
      window.cancelAnimationFrame(streamRenderFrameRef.current)
    }
    clearDiagramScrollFallback()
    clearFinalScrollSettlement()
  }, [clearDiagramScrollFallback, clearFinalScrollSettlement])

  useEffect(() => {
    if (!authReady) return

    const unsubscribers = [
      wsService.on('connected', () => setIsConnected(true)),
      wsService.on('disconnected', () => {
        setIsConnected(false)
        if (pendingMessageRef.current) {
          updateAssistantMessage(
            pendingMessageRef.current,
            'A conexão foi interrompida. Reconecte e tente novamente.',
          )
          pendingMessageRef.current = null
          setLoading(false)
          setStreaming(false)
        }
      }),
      wsService.on('reconnecting', () => setIsConnected(false)),
      wsService.on<WsStatusPayload>('status', ({ payload }) => setStatus(payload.resposta)),
      wsService.on<WsStepPayload>('etapa', ({ payload }) => {
        const text = extractResponseText(payload.resposta)
        if (!text) return
        setAgentSteps((current) => {
          const existingIndex = current.findIndex((step) => step.id === payload.id)
          if (existingIndex >= 0) {
            return current.map((step, index) => index === existingIndex
              ? {
                  ...step,
                  content: removeToolPreambleMarkers(
                    payload.modo === 'append' ? step.content + text : text,
                  ),
                }
              : step)
          }
          return [
            ...current.map((step) => ({ ...step, completed: true })),
            {
              id: payload.id,
              content: removeToolPreambleMarkers(text),
              completed: false,
            },
          ]
        })
      }),
      wsService.on<WsResponseStartPayload>('resposta_inicio', ({ payload }) => {
        const pendingId = pendingMessageRef.current
        if (!pendingId) return
        const responseText = extractResponseText(payload.resposta)
        if (payload.etapa_id) {
          setAgentSteps((current) => current.filter((step) => step.id !== payload.etapa_id))
        }
        setAgentSteps((current) => current.map((step) => ({ ...step, completed: true })))
        if (responseText) {
          streamedTextRef.current = responseText
          updateAssistantMessage(pendingId, responseText)
        }
        setStreaming(true)
      }),
      wsService.on<WsReclassifiedResponsePayload>('resposta_reclassificada', ({ payload }) => {
        const pendingId = pendingMessageRef.current
        if (!pendingId) return
        const text = extractResponseText(payload.resposta)
        streamedTextRef.current = ''
        updateAssistantMessage(pendingId, '')
        setStreaming(false)
        if (!text) return
        setAgentSteps((current) => [
          ...current.map((step) => ({ ...step, completed: true })),
          {
            id: payload.id,
            content: text,
            completed: false,
          },
        ])
      }),
      wsService.on<WsTokenPayload>('token', ({ payload }) => {
        const pendingId = pendingMessageRef.current
        if (!pendingId) return
        const token = extractResponseText(payload.resposta)
        if (!token) return
        streamedTextRef.current += token
        setAgentSteps((current) => current.map((step) => ({ ...step, completed: true })))
        setStreaming(true)
        if (streamRenderFrameRef.current !== null) return

        streamRenderFrameRef.current = window.requestAnimationFrame(() => {
          const currentPendingId = pendingMessageRef.current
          if (currentPendingId) {
            updateAssistantMessage(currentPendingId, streamedTextRef.current)
          }
          streamRenderFrameRef.current = null
        })
      }),
      wsService.on<WsErrorPayload>('erro', ({ payload }) => {
        const message = (
          extractResponseText(payload.mensagem ?? payload.resposta)
          || 'Não foi possível processar a mensagem.'
        )
        if (pendingMessageRef.current) updateAssistantMessage(pendingMessageRef.current, message)
        pendingMessageRef.current = null
        setError(message)
        setLoading(false)
        setStreaming(false)
      }),
      wsService.on<WsErrorPayload>('error', ({ payload }) => {
        setError(payload.mensagem ?? 'Falha na conexão em tempo real.')
      }),
      wsService.on<WsFinalPayload>('resposta_final', ({ payload }) => {
        if (streamRenderFrameRef.current !== null) {
          window.cancelAnimationFrame(streamRenderFrameRef.current)
          streamRenderFrameRef.current = null
        }
        const pendingId = pendingMessageRef.current
        const finalText = extractResponseText(payload.resposta) || streamedTextRef.current
        if (pendingId) updateAssistantMessage(pendingId, finalText)
        clearDiagramScrollFallback()
        const diagramCount = countMermaidDiagrams(finalText)
        if (pendingId && diagramCount > 0) {
          diagramScrollTargetRef.current = {
            messageIds: new Set([pendingId]),
            remaining: diagramCount,
          }
          // Segurança para um bloco Mermaid inválido que não consiga concluir
          // o ciclo normal de renderização.
          diagramScrollFallbackRef.current = window.setTimeout(() => {
            if (!diagramScrollTargetRef.current?.messageIds.has(pendingId)) return
            diagramScrollTargetRef.current = null
            diagramScrollFallbackRef.current = null
            requestFinalScroll('auto')
          }, 5_000)
        } else {
          diagramScrollTargetRef.current = null
          requestFinalScroll()
        }
        pendingMessageRef.current = null
        streamedTextRef.current = ''
        setLoading(false)
        setStreaming(false)
        setStatus('Processando a pergunta')

        const currentSession = sessionRef.current
        const firstQuestion = newConversationQuestionRef.current
        const wasNewConversation = firstQuestion !== null
        newConversationQuestionRef.current = null
        if (!currentSession || !payload.chat_id) return

        const chatId = payload.chat_id
        const now = new Date().toISOString()
        if (wasNewConversation) {
          const title = truncate(lastQuestionRef.current, 60) || 'Novo Chat'
          addConversation({ id: chatId, title, createdAt: now, updatedAt: now })
          activeIdRef.current = chatId
          void conversationsService.generateTitle(firstQuestion)
            .then(({ resumo }) => {
              const generatedTitle = resumo?.trim()
              if (!generatedTitle) throw new Error('Título vazio')
              return conversationsService.updateGeneratedTitle(chatId, generatedTitle)
                .then(() => {
                  setConversations((current) => current.map((conversation) =>
                    conversation.id === chatId
                      ? { ...conversation, title: generatedTitle }
                      : conversation,
                  ))
                })
            })
            .catch((titleError) => {
              console.error('[Chat title] Não foi possível gerar ou salvar o título', titleError)
            })
        } else {
          setConversations((current) => current
            .map((conversation) => conversation.id === chatId
              ? { ...conversation, updatedAt: now }
              : conversation)
            .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)))
        }
      }),
    ]

    wsService.connect()
    setIsConnected(wsService.isConnected())
    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      wsService.disconnect()
    }
  }, [
    addConversation,
    authReady,
    clearDiagramScrollFallback,
    requestFinalScroll,
    setConversations,
    updateAssistantMessage,
  ])

  useLayoutEffect(() => {
    if (scrollRequest === 0) return
    const forceScroll = forceScrollRef.current
    if (!forceScroll && !shouldAutoScrollRef.current) return
    forceScrollRef.current = false
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: scrollBehaviorRef.current,
    })
    if (revealHistoryAfterScrollRef.current) {
      revealHistoryAfterScrollRef.current = false
      setRestoringHistoryLayout(false)
    }
  }, [scrollRequest])

  async function handleSend(text: string, files: File[] = []) {
    if (loading) return
    if (!wsService.isConnected()) {
      setError('Ainda não há conexão com o servidor. Aguarde e tente novamente.')
      return
    }
    setError(null)
    newConversationQuestionRef.current = (
      sessionRef.current && !activeIdRef.current ? text : null
    )
    addUserMessage(text, files.map((file) => file.name))
    lastQuestionRef.current = text
    const pendingId = addAssistantPlaceholder()
    pendingMessageRef.current = pendingId
    clearDiagramScrollFallback()
    clearFinalScrollSettlement()
    diagramScrollTargetRef.current = null
    revealHistoryAfterScrollRef.current = false
    setRestoringHistoryLayout(false)
    streamedTextRef.current = ''
    setAgentSteps([])
    setStepsMessageId(pendingId)
    setLoading(true)
    setStreaming(false)
    shouldAutoScrollRef.current = true
    // Em conversas longas (especialmente após gráficos), uma animação suave
    // pode ser interrompida pelas etapas que surgem logo depois do envio.
    scrollBehaviorRef.current = 'auto'
    setScrollRequest((current) => current + 1)

    try {
      const socketFiles = await Promise.all(files.map(fileToSocketPayload))
      const sent = wsService.sendMessage({
        conversationId: activeIdRef.current,
        content: text,
        files: socketFiles,
      })
      if (!sent) throw new Error('Sem conexão com o servidor. Aguarde a reconexão e tente novamente.')
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Não foi possível enviar a mensagem.'
      updateAssistantMessage(pendingId, message)
      pendingMessageRef.current = null
      setError(message)
      setLoading(false)
    }
  }

  async function handleNewChat() {
    if (loading) return
    closeSidebarOnMobile()
    clearDiagramScrollFallback()
    clearFinalScrollSettlement()
    diagramScrollTargetRef.current = null
    revealHistoryAfterScrollRef.current = false
    setRestoringHistoryLayout(false)
    if (!sessionRef.current) await wsService.resetAnonymousChat()
    activeIdRef.current = null
    newConversationQuestionRef.current = null
    setActiveId(null)
    resetMessages()
    setAgentSteps([])
    setStepsMessageId(null)
    setError(null)
    setInputFocusRequest((current) => current + 1)
  }

  async function handleSelectConversation(id: string) {
    if (loading) return
    closeSidebarOnMobile()
    if (id === activeIdRef.current) return
    setError(null)
    setLoading(true)
    try {
      const response = await chatService.listMessages(id)
      clearDiagramScrollFallback()
      clearFinalScrollSettlement()

      const diagramMessageIds = new Set<string>()
      let diagramCount = 0
      for (const message of response.data) {
        const messageDiagramCount = countMermaidDiagrams(message.content)
        if (messageDiagramCount === 0) continue
        diagramMessageIds.add(message.id)
        diagramCount += messageDiagramCount
      }

      if (diagramCount > 0) {
        const target = {
          messageIds: diagramMessageIds,
          remaining: diagramCount,
        }
        diagramScrollTargetRef.current = target
        revealHistoryAfterScrollRef.current = true
        setRestoringHistoryLayout(true)
        diagramScrollFallbackRef.current = window.setTimeout(() => {
          if (diagramScrollTargetRef.current !== target) return
          diagramScrollTargetRef.current = null
          diagramScrollFallbackRef.current = null
          requestFinalScroll('auto')
        }, 5_000)
      } else {
        diagramScrollTargetRef.current = null
        revealHistoryAfterScrollRef.current = false
        setRestoringHistoryLayout(false)
      }

      selectConversation(id)
      activeIdRef.current = id
      setMessages(response.data)
      setAgentSteps([])
      setStepsMessageId(null)
      scrollBehaviorRef.current = 'auto'
      if (diagramCount === 0) {
        forceScrollRef.current = true
        setScrollRequest((current) => current + 1)
      }
    } catch {
      clearDiagramScrollFallback()
      diagramScrollTargetRef.current = null
      revealHistoryAfterScrollRef.current = false
      setRestoringHistoryLayout(false)
      setError('Não foi possível carregar essa conversa.')
    } finally {
      setLoading(false)
    }
  }

  function handleDeleteConversation(id: string) {
    setConversationToDelete(id)
  }

  async function confirmDeleteConversation() {
    if (!conversationToDelete || deletingConversation) return
    const id = conversationToDelete
    setDeletingConversation(true)
    try {
      await conversationsService.delete(id)
      removeConversation(id)
      if (activeIdRef.current === id) {
        activeIdRef.current = null
        resetMessages()
        setAgentSteps([])
        setStepsMessageId(null)
      }
      setConversationToDelete(null)
    } catch {
      setError('Não foi possível excluir a conversa.')
      setConversationToDelete(null)
    } finally {
      setDeletingConversation(false)
    }
  }

  async function handleLogout() {
    setError(null)
    try {
      await authService.logout()
    } catch {
      setError('Não foi possível sair da conta. Verifique sua conexão e tente novamente.')
      return
    }
    wsService.disconnect()
    setIsConnected(false)
    setSession(null)
    sessionRef.current = null
    setConversations([])
    activeIdRef.current = null
    setActiveId(null)
    resetMessages()
    setAgentSteps([])
    setStepsMessageId(null)
    wsService.connect()
  }

  function rememberSidebarState(open: boolean) {
    setSidebarOpen(open)
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(open))
  }

  function closeSidebarOnMobile() {
    if (window.matchMedia('(max-width: 767px)').matches) {
      rememberSidebarState(false)
    }
  }

  function toggleSidebar() {
    setSidebarOpen((current) => {
      const next = !current
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next))
      return next
    })
  }

  const isEmpty = messages.length === 0 && !loading

  return (
    <div className="flex h-dvh overflow-hidden">
      <ChatSidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={session ? handleDeleteConversation : undefined}
        open={sidebarOpen}
        onClose={() => rememberSidebarState(false)}
        onToggle={toggleSidebar}
        authReady={authReady}
        userName={session?.user.name}
        onLogout={handleLogout}
      />

      <Dialog
        open={conversationToDelete !== null}
        onOpenChange={(open) => {
          if (!open && !deletingConversation) setConversationToDelete(null)
        }}
      >
        <DialogContent
          showCloseButton={false}
          className="w-[calc(100%-2rem)] max-w-md gap-5 rounded-2xl border border-transparent bg-card p-5 shadow-float ring-transparent sm:p-6"
        >
          <div className="space-y-3">
            <DialogTitle className="text-xl font-semibold tracking-tight text-foreground">
              Excluir chat?
            </DialogTitle>
            <DialogDescription className="text-sm leading-relaxed text-muted-foreground sm:text-base">
              Isso vai excluir esta conversa e toda a memória associada.
            </DialogDescription>
          </div>

          <div className="grid grid-cols-2 gap-2.5 sm:flex sm:justify-end">
            <Button
              type="button"
              variant="outline"
              size="lg"
              disabled={deletingConversation}
              onClick={() => setConversationToDelete(null)}
              className="h-10 rounded-xl px-5"
            >
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="lg"
              disabled={deletingConversation}
              onClick={() => void confirmDeleteConversation()}
              className="h-10 rounded-xl bg-destructive px-5 text-white hover:bg-destructive/90"
            >
              {deletingConversation ? 'Excluindo…' : 'Excluir'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <ChatHeader
          onOpenSidebar={() => rememberSidebarState(true)}
        />

        {error && (
          <div role="alert" className="border-b border-destructive/20 bg-destructive/5 px-4 py-2 text-center text-sm text-destructive">
            {error}
          </div>
        )}

        <div
          ref={scrollRef}
          onScroll={(event) => {
            const element = event.currentTarget
            const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight
            shouldAutoScrollRef.current = distanceFromBottom < 48
          }}
          className="min-h-0 flex-1 overflow-y-auto [overflow-anchor:none]"
        >
          {!authReady ? (
            <div className="min-h-full" aria-label="Carregando sessão" />
          ) : isEmpty ? (
            <div className="flex min-h-full flex-col">
              <EmptyState userName={session?.user.name} onPick={(text) => void handleSend(text)} />
            </div>
          ) : (
            <div
              aria-busy={restoringHistoryLayout}
              className={cn(
                'mx-auto w-full max-w-3xl space-y-6 px-4 py-6 md:px-6 md:py-8',
                restoringHistoryLayout && 'invisible',
              )}
            >
              {messages.map((message, index) => {
                const ownsSteps = message.id === stepsMessageId
                const hidePendingMessage = (
                  loading
                  && !streaming
                  && message.id === pendingMessageRef.current
                )
                const isStreamingMessage = streaming && message.id === pendingMessageRef.current

                const previousQuestion = message.role === 'assistant'
                  ? messages.slice(0, index).findLast((item) => item.role === 'user')?.content
                  : undefined

                return (
                  <div key={message.id} className="contents">
                    {ownsSteps && hidePendingMessage && (
                      <AgentSteps steps={agentSteps} completed={!loading} />
                    )}
                    {!hidePendingMessage && (
                      <MessageBubble
                        message={message}
                        agentSteps={ownsSteps ? agentSteps : undefined}
                        agentStepsCompleted={ownsSteps ? !loading : undefined}
                        isStreaming={isStreamingMessage}
                        onDiagramRendered={diagramScrollTargetRef.current?.messageIds.has(message.id)
                          ? () => {
                            const target = diagramScrollTargetRef.current
                            if (!target?.messageIds.has(message.id)) return
                            target.remaining -= 1
                            if (target.remaining > 0) return
                            diagramScrollTargetRef.current = null
                            clearDiagramScrollFallback()
                            requestFinalScroll('auto')
                          }
                          : undefined}
                        feedbackContext={message.role === 'assistant' ? {
                          question: previousQuestion ?? '',
                          conversationId: activeId,
                          userType: session ? 'user' : 'anon',
                          userId: session?.user.id,
                        } : undefined}
                      />
                    )}
                  </div>
                )
              })}
              {loading && !streaming && agentSteps.length === 0 && (
                <LoadingBubble status={status} />
              )}
            </div>
          )}
        </div>

        <div className="border-t border-border/60 bg-background/70 px-4 py-4 backdrop-blur-md md:px-6">
          <ChatInput
            onSend={handleSend}
            disabled={loading || !isConnected}
            focusRequest={inputFocusRequest}
          />
          {!isConnected && <p className="mt-1 text-center text-xs text-muted-foreground">Conectando ao servidor…</p>}
        </div>
      </div>
    </div>
  )
}
