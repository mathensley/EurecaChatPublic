// =============================================================
// Services barrel — single import point for all services
// =============================================================

export { apiClient, ApiError } from './api/api'
export { conversationsService } from './api/conversations'
export { chatService } from './api/chat'
export { audioService } from './api/audio'
export { feedbackService } from './feedback'
export type { FeedbackChoice, FeedbackPayload } from './feedback'
export { wsService } from './websocket'
export { authService } from './auth'
