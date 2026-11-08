import { ApiError } from './http'
import { getTenant, getToken } from '@/store/auth'

export type ChatEventHandler = (event: string, data: string) => void

function dispatchFrame(frame: string, onEvent: ChatEventHandler): void {
  let eventName = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }
  if (dataLines.length > 0) {
    onEvent(eventName, dataLines.join('\n'))
  }
}

export async function streamChat(
  question: string,
  sessionId: string,
  onEvent: ChatEventHandler,
  signal: AbortSignal
): Promise<void> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Tenant-Id': getTenant()
  }
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify({ question, sessionId }),
    signal
  })

  if (!response.ok) {
    let message = `对话请求失败（${response.status}）`
    try {
      const text = await response.text()
      const payload = JSON.parse(text) as { message?: string; detail?: string }
      message = payload.message || payload.detail || message
    } catch {
      // 忽略非 JSON 错误体
    }
    throw new ApiError(response.status, message)
  }
  if (!response.body) {
    throw new ApiError(500, '当前浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replace(/\r\n/g, '\n')

    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const frame = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      if (frame.trim()) {
        dispatchFrame(frame, onEvent)
      }
      index = buffer.indexOf('\n\n')
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    dispatchFrame(buffer, onEvent)
  }
}
