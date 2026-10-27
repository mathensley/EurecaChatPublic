// =============================================================
// Domain Types — EurecaChat
// =============================================================

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  createdAt: string
  attachments?: string[]
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

export interface User {
  id: string | number
  name: string
  type?: string
  attributes?: Record<string, unknown>
}

export interface AuthSession {
  user: User
}

// =============================================================
// API / Transport Types
// =============================================================

export interface ApiResponse<T> {
  data: T
  error?: string
}

export interface SendMessagePayload {
  conversationId: string | null
  content: string
  files?: SocketFile[]
}

export interface CreateConversationPayload {
  title?: string
}

// =============================================================
// WebSocket Types
// =============================================================

export type WsEventType =
  | 'token'
  | 'etapa'
  | 'resposta_inicio'
  | 'resposta_reclassificada'
  | 'resposta_final'
  | 'status'
  | 'erro'
  | 'error'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'

export interface WsEvent<T = unknown> {
  type: WsEventType
  payload: T
}

export interface SocketFile {
  filename: string
  content: string
}

export interface WsTokenPayload {
  resposta: string
}

export interface WsStepPayload {
  id: string
  resposta: string
  modo: 'append' | 'replace'
}

export interface WsResponseStartPayload {
  etapa_id?: string
  resposta?: string
}

export interface WsReclassifiedResponsePayload {
  id: string
  resposta: string
}

export interface WsFinalPayload {
  resposta: string
  chat_id?: string
}

export interface WsStatusPayload {
  resposta: string
}

export interface WsErrorPayload {
  mensagem?: string
  resposta?: string
}
