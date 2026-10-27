'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { wsService } from '@/services/websocket'
import type { WsTokenPayload } from '@/types'

/**
 * Manages the WebSocket lifecycle for a given conversation.
 * Returns the streaming chunk accumulator and connection state.
 */
export function useWebSocket(_conversationId: string | null) {
  const [isConnected, setIsConnected] = useState(false)
  const [streamingChunk, setStreamingChunk] = useState('')
  const unsubscribeRefs = useRef<Array<() => void>>([])

  useEffect(() => {
    const unsubs = [
      wsService.on('connected', () => setIsConnected(true)),
      wsService.on('reconnecting', () => setIsConnected(false)),
      wsService.on<WsTokenPayload>('token', (ev) => {
        setStreamingChunk((prev) => prev + ev.payload.resposta)
      }),
      wsService.on('resposta_final', () => {
        setStreamingChunk('')
      }),
    ]

    wsService.connect()

    unsubscribeRefs.current = unsubs

    return () => {
      unsubs.forEach((fn) => fn())
      wsService.disconnect()
      setIsConnected(false)
    }
  }, [])

  const resetChunk = useCallback(() => setStreamingChunk(''), [])

  return { isConnected, streamingChunk, resetChunk }
}
