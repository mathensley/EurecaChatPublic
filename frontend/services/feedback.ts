import { apiClient } from './api/api'

export type FeedbackChoice = 'positive' | 'negative'

export interface FeedbackPayload {
  feedbackId: string
  createdAt: string
  question: string
  answer: string
  feedback: string
  choice: FeedbackChoice
  conversationId?: string | null
  userType: 'user' | 'anon'
  userId?: string | number | null
}

export const feedbackService = {
  async save(payload: FeedbackPayload): Promise<void> {
    await apiClient.post('/api/feedback', payload)
  },
}
