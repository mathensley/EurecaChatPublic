import { io, type Socket } from 'socket.io-client'
import type { SendMessagePayload, WsEvent, WsEventType } from '@/types'

type WsCallback<T = unknown> = (event: WsEvent<T>) => void

const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || undefined

class WebSocketService {
  private socket: Socket | null = null
  private callbacks = new Map<WsEventType, Set<WsCallback>>()

  connect(): void {
    if (this.socket) {
      if (!this.socket.connected) this.socket.connect()
      return
    }

    this.socket = io(SOCKET_URL, {
      path: '/socket.io',
      transports: ['websocket'],
      withCredentials: true,
      reconnection: true,
      reconnectionDelay: 1_000,
      reconnectionDelayMax: 5_000,
    })

    this.socket.on('connect', () => this.dispatch({ type: 'connected', payload: null }))
    this.socket.on('disconnect', () => this.dispatch({ type: 'disconnected', payload: null }))
    this.socket.io.on('reconnect_attempt', () => this.dispatch({ type: 'reconnecting', payload: null }))
    this.socket.on('connect_error', (error) => {
      this.dispatch({ type: 'error', payload: { mensagem: error.message } })
    })

    for (const event of [
      'token',
      'etapa',
      'resposta_inicio',
      'resposta_reclassificada',
      'resposta_final',
      'status',
      'erro',
    ] as const) {
      this.socket.on(event, (payload: unknown) => this.dispatch({ type: event, payload }))
    }
  }

  disconnect(): void {
    this.socket?.disconnect()
    this.socket = null
  }

  isConnected(): boolean {
    return Boolean(this.socket?.connected)
  }

  sendMessage(payload: SendMessagePayload): boolean {
    if (!this.socket?.connected) return false
    this.socket.emit('input_text', {
      input_data: payload.content,
      arquivos: payload.files ?? [],
      chat_id: payload.conversationId,
    })
    return true
  }

  resetAnonymousChat(): Promise<boolean> {
    return new Promise((resolve) => {
      if (!this.socket?.connected) return resolve(false)
      this.socket.timeout(5_000).emit(
        'new_chat',
        (error: Error | null, response?: { ok?: boolean }) => resolve(!error && response?.ok === true),
      )
    })
  }

  on<T = unknown>(type: WsEventType, callback: WsCallback<T>): () => void {
    if (!this.callbacks.has(type)) this.callbacks.set(type, new Set())
    this.callbacks.get(type)!.add(callback as WsCallback)
    return () => this.callbacks.get(type)?.delete(callback as WsCallback)
  }

  private dispatch(event: WsEvent): void {
    this.callbacks.get(event.type)?.forEach((callback) => callback(event))
  }
}

export const wsService = new WebSocketService()
