'use client'

import { useCallback, useRef, useState } from 'react'
import type { Message } from '@/types'

/**
 * Manages the local list of messages in a conversation.
 * Provides helpers for optimistic updates and appending streamed content.
 */
export function useMessages() {
  const [messages, setMessages] = useState<Message[]>([])
  const pendingIdRef = useRef<string | null>(null)

  const addUserMessage = useCallback((content: string, attachments: string[] = []): Message => {
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
      attachments,
    }
    setMessages((prev) => [...prev, msg])
    return msg
  }, [])

  const addAssistantPlaceholder = useCallback((): string => {
    const id = crypto.randomUUID()
    pendingIdRef.current = id
    setMessages((prev) => [
      ...prev,
      { id, role: 'assistant', content: '', createdAt: new Date().toISOString() },
    ])
    return id
  }, [])

  const updateAssistantMessage = useCallback((id: string, content: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content } : m)),
    )
  }, [])

  const reset = useCallback(() => {
    setMessages([])
    pendingIdRef.current = null
  }, [])

  return {
    messages,
    setMessages,
    addUserMessage,
    addAssistantPlaceholder,
    updateAssistantMessage,
    pendingId: pendingIdRef.current,
    reset,
  }
}
