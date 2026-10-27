import { apiClient } from './api'

interface TranscriptionResponse {
  transcription: string
}

export const audioService = {
  transcribe: (audio: Blob, filename: string) => {
    const formData = new FormData()
    formData.append('file', audio, filename)
    return apiClient.postForm<TranscriptionResponse>('/voice-to-text', formData)
  },
}
