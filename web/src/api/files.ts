import { apiDelete, apiGet, apiPost } from './http'
import type { DocumentItem, FileUploadResult } from '@/types/api'

export function listDocuments(): Promise<DocumentItem[]> {
  return apiGet<DocumentItem[]>('/files')
}

export function getDocument(id: number): Promise<DocumentItem> {
  return apiGet<DocumentItem>(`/files/${id}`)
}

export function uploadDocument(
  file: File,
  onProgress?: (percent: number) => void
): Promise<FileUploadResult> {
  const form = new FormData()
  form.append('file', file)
  return apiPost<FileUploadResult>('/files/upload', form, {
    timeout: 120000,
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
  })
}

export function deleteDocument(id: number): Promise<void> {
  return apiDelete<void>(`/files/${id}`)
}
