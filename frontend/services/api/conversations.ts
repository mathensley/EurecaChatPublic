// =============================================================
// Conversations service — wraps /conversations endpoints
// =============================================================

import { apiClient } from './api'
import type { Conversation, ApiResponse } from '@/types'

export const conversationsService = {
  generateTitle(text: string): Promise<{ resumo: string }> {
    return apiClient.post<{ resumo: string }>('/resumir', { texto: text })
  },

  /**
   * Fetch all conversations for the authenticated user.
   */
  list(): Promise<ApiResponse<Conversation[]>> {
    return apiClient.get<ApiResponse<Conversation[]>>('/api/conversations')
  },

  /**
   * Delete a conversation by id.
   */
  delete(id: string): Promise<ApiResponse<void>> {
    return apiClient.delete<ApiResponse<void>>(`/api/conversations/${id}`)
  },

  updateGeneratedTitle(chatId: string, title: string): Promise<{ ok: boolean }> {
    return apiClient.post<{ ok: boolean }>('/update_title', {
      chat_id: chatId,
      title,
    })
  },
}
