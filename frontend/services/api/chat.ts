// =============================================================
// Chat service — wraps conversation message endpoints
// =============================================================

import { apiClient } from './api'
import type { ApiResponse, Message } from '@/types'

export const chatService = {
  /**
   * Fetch all messages for a given conversation.
   */
  listMessages(conversationId: string): Promise<ApiResponse<Message[]>> {
    return apiClient.get<ApiResponse<Message[]>>(`/api/conversations/${conversationId}/messages`)
  },
}
