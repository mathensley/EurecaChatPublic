'use client'

import { useCallback, useState } from 'react'
import type { Conversation } from '@/types'

/**
 * Manages the sidebar conversation list state.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)

  const addConversation = useCallback((conv: Conversation) => {
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
  }, [])

  const removeConversation = useCallback(
    (id: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (activeId === id) setActiveId(null)
    },
    [activeId],
  )

  const selectConversation = useCallback((id: string) => {
    setActiveId(id)
  }, [])

  return {
    conversations,
    setConversations,
    activeId,
    setActiveId,
    addConversation,
    removeConversation,
    selectConversation,
  }
}
