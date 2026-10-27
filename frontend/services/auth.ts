import type { ApiResponse, AuthSession, User } from '@/types'
import { apiClient } from './api/api'

const LEGACY_STORAGE_KEY = 'eureca.auth'

function clearLegacySession() {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(LEGACY_STORAGE_KEY)
  }
}

export const authService = {
  async login(username: string, password: string): Promise<AuthSession> {
    const response = await apiClient.post<ApiResponse<AuthSession>>('/api/auth/login', {
      username,
      password,
    })
    clearLegacySession()
    return response.data
  },

  async validate(): Promise<User | null> {
    clearLegacySession()
    const response = await apiClient.get<ApiResponse<User | null>>('/api/auth/me')
    return response.data
  },

  async logout(): Promise<void> {
    await apiClient.post<ApiResponse<null>>('/api/auth/logout', {})
    clearLegacySession()
  },
}
