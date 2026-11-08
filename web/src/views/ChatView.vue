<template>
  <div class="chat-page">
    <div class="chat-shell panel">
      <header class="chat-header">
        <div>
          <h2>智能问答</h2>
          <p class="muted">
            文档问答可按页码追溯引用；数据查询与报表由 NL2SQL 生成，仅执行只读 SQL。
          </p>
        </div>
        <div class="chat-header-actions">
          <el-tag v-if="lastModel" size="small" type="success" effect="plain">
            {{ lastModel.provider }} · {{ lastModel.model }}
          </el-tag>
          <el-button size="small" :icon="Plus" @click="newSession">新会话</el-button>
        </div>
      </header>

      <div ref="scrollRef" class="chat-scroll">
        <div v-if="messages.length === 0" class="chat-welcome">
          <div class="welcome-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h3>从一份文档或一张报表开始</h3>
          <p class="muted">点击示例问题填入输入框，或直接提问。</p>
          <div class="suggestions">
            <button
              v-for="question in suggestions"
              :key="question"
              class="suggestion"
              @click="useSuggestion(question)"
            >
              {{ question }}
            </button>
          </div>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message"
          :class="msg.role"
        >
          <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
          <div class="message-body">
            <div class="message-meta">
              <span class="sender">{{ msg.role === 'user' ? '我' : '助手' }}</span>
              <el-tag v-if="msg.intent" size="small" effect="plain">
                {{ intentLabel(msg.intent) }}
              </el-tag>
              <el-tag
                v-if="msg.retrievalCount"
                size="small"
                type="info"
                effect="plain"
              >
                检索 {{ msg.retrievalCount }} 片段
              </el-tag>
              <el-tag v-if="msg.model" size="small" type="success" effect="plain">
                {{ msg.model.provider }}
              </el-tag>
              <span class="message-time">{{ formatDateTime(new Date(msg.createdAt).toISOString()) }}</span>
            </div>

            <template v-if="msg.role === 'user'">
              <div class="user-bubble">{{ msg.content }}</div>
            </template>

            <template v-else>
              <div v-if="msg.sql" class="sql-panel">
                <div class="sql-head" @click="toggleSql(msg.id)">
                  <span>SQL 预览（只读）</span>
                  <el-icon>
                    <ArrowUp v-if="sqlOpen[msg.id]" />
                    <ArrowDown v-else />
                  </el-icon>
                </div>
                <pre v-show="sqlOpen[msg.id]" class="sql-code">{{ msg.sql }}</pre>
              </div>

              <div
                v-if="msg.content"
                class="answer markdown-body"
                v-html="renderMarkdown(msg.content)"
              ></div>
              <div v-else-if="msg.status === 'streaming'" class="answer streaming-hint">
                正在生成回答<span class="dots">...</span>
              </div>

              <div v-if="msg.result" class="result-block">
                <div class="block-title">
                  <el-icon><Grid /></el-icon>
                  查询结果
                </div>
                <ResultTable
                  :columns="msg.result.columns"
                  :rows="msg.result.rows"
                  :row-count="msg.result.row_count"
                  :max-height="260"
                />
              </div>

              <div v-if="msg.report" class="report-block">
                <div class="report-head">
                  <span class="report-title">{{ msg.report.title }}</span>
                  <el-button
                    v-if="msg.report.report_id"
                    link
                    type="primary"
                    size="small"
                    @click="openReport(msg.report.report_id)"
                  >
                    查看报表详情
                  </el-button>
                </div>
                <EChart
                  v-if="msg.report.option && msg.report.chart_type !== 'none'"
                  :option="msg.report.option"
                  height="300px"
                />
                <ResultTable
                  v-else
                  :columns="msg.report.columns"
                  :rows="msg.report.rows"
                  :row-count="msg.report.row_count"
                  :max-height="260"
                />
              </div>

              <CitationList
                v-if="msg.citations.length"
                :citations="msg.citations"
                @open-document="openDocument"
                @open-report="openReport"
              />

              <div v-if="msg.review" class="review-line">
                <el-tag
                  :type="msg.review.passed ? 'success' : 'warning'"
                  size="small"
                  effect="plain"
                >
                  {{ msg.review.passed ? '质量检查通过' : '质量检查提示' }}
                </el-tag>
                <span v-for="issue in msg.review.issues" :key="issue" class="review-issue">
                  {{ issue }}
                </span>
              </div>

              <div v-if="msg.error" class="error-line">
                <el-icon><CircleCloseFilled /></el-icon>
                <span>{{ msg.error }}</span>
              </div>
              <div v-if="msg.status === 'stopped'" class="muted stopped-line">已停止生成</div>
            </template>
          </div>
        </div>
      </div>

      <footer class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          resize="none"
          placeholder="输入问题，例如：高值耗材的验收流程是什么？"
          :disabled="streaming"
          @keydown.enter.exact.prevent="send"
        />
        <div class="input-actions">
          <span class="muted input-tip">Enter 发送 / Shift + Enter 换行</span>
          <div class="input-buttons">
            <el-button v-if="streaming" type="danger" plain :icon="CircleClose" @click="stop">
              停止
            </el-button>
            <el-button
              v-else
              type="primary"
              :icon="Promotion"
              :disabled="!input.trim()"
              @click="send"
            >
              发送
            </el-button>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  CircleClose,
  CircleCloseFilled,
  Grid,
  Plus,
  Promotion
} from '@element-plus/icons-vue'

import CitationList from '@/components/CitationList.vue'
import EChart from '@/components/EChart.vue'
import ResultTable from '@/components/ResultTable.vue'
import { streamChat } from '@/api/chat'
import { formatDateTime, intentLabel } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import type {
  ChatMessage,
  Citation,
  ModelInfo,
  ReportPayload,
  ReviewPayload,
  SqlResult
} from '@/types/api'

const router = useRouter()

const suggestions = [
  '高值耗材的验收流程是什么？',
  '查询各科室消耗金额排名',
  '生成供应商履约率报表',
  '库存周转情况如何？'
]

const messages = ref<ChatMessage[]>([])
const input = ref('')
const streaming = ref(false)
const scrollRef = ref<HTMLDivElement>()
const sqlOpen = reactive<Record<string, boolean>>({})
const lastModel = ref<ModelInfo | null>(null)

let sessionId = createSessionId()
let controller: AbortController | null = null
let scrollScheduled = false

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createMessage(role: 'user' | 'assistant', content = ''): ChatMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content,
    status: role === 'user' ? 'done' : 'streaming',
    createdAt: Date.now(),
    citations: []
  }
}

function safeParse<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T
  } catch {
    return null
  }
}

async function send(): Promise<void> {
  const question = input.value.trim()
  if (!question || streaming.value) return

  messages.value.push(createMessage('user', question))
  const assistant = createMessage('assistant')
  messages.value.push(assistant)
  input.value = ''
  streaming.value = true
  scrollToBottom()

  controller = new AbortController()
  try {
    await streamChat(question, sessionId, (event, data) => handleEvent(assistant, event, data), controller.signal)
    if (assistant.status === 'streaming') {
      assistant.status = 'done'
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      assistant.status = 'stopped'
    } else {
      assistant.status = 'error'
      assistant.error = error instanceof Error ? error.message : '对话请求失败'
    }
  } finally {
    streaming.value = false
    controller = null
    scrollToBottom()
  }
}

function handleEvent(msg: ChatMessage, event: string, data: string): void {
  switch (event) {
    case 'start':
      break
    case 'intent': {
      const payload = safeParse<{ intent?: string }>(data)
      if (payload?.intent) msg.intent = payload.intent
      break
    }
    case 'retrieval': {
      const payload = safeParse<{ count?: number }>(data)
      if (payload?.count !== undefined) msg.retrievalCount = payload.count
      break
    }
    case 'token':
      appendToken(msg, data)
      break
    case 'citations': {
      const payload = safeParse<Citation[]>(data)
      if (Array.isArray(payload)) msg.citations = payload
      break
    }
    case 'sql': {
      const payload = safeParse<{ sql?: string }>(data)
      if (payload?.sql) {
        msg.sql = payload.sql
        sqlOpen[msg.id] = true
      }
      break
    }
    case 'result': {
      const payload = safeParse<SqlResult>(data)
      if (payload && Array.isArray(payload.columns)) msg.result = payload
      break
    }
    case 'report': {
      const payload = safeParse<ReportPayload>(data)
      if (payload && Array.isArray(payload.columns)) {
        msg.report = payload
      }
      break
    }
    case 'review': {
      const payload = safeParse<ReviewPayload & { answer?: string }>(data)
      if (payload) {
        msg.review = {
          passed: payload.passed,
          level: payload.level,
          issues: payload.issues || [],
          model: payload.model
        }
        if (payload.answer) msg.content = payload.answer
        if (payload.model) {
          msg.model = payload.model
          lastModel.value = payload.model
        }
      }
      break
    }
    case 'model': {
      const payload = safeParse<ModelInfo>(data)
      if (payload) {
        msg.model = payload
        lastModel.value = payload
      }
      break
    }
    case 'error': {
      const payload = safeParse<{ message?: string }>(data)
      msg.error = payload?.message || data || 'AI 服务处理失败'
      msg.status = 'error'
      break
    }
    case 'done': {
      const payload = safeParse<{ model?: ModelInfo | null }>(data)
      if (payload?.model && !msg.model) {
        msg.model = payload.model
        lastModel.value = payload.model
      }
      if (msg.status === 'streaming') msg.status = 'done'
      break
    }
    default:
      break
  }
  scrollToBottom()
}

function appendToken(msg: ChatMessage, token: string): void {
  if (!token) return
  if (!msg.content) {
    msg.content = token
    return
  }
  // 后端按“累计全文”推送：新文本以已有内容开头时直接替换，否则按增量追加。
  if (token.startsWith(msg.content)) {
    msg.content = token
  } else if (!msg.content.endsWith(token)) {
    msg.content += token
  }
}

function stop(): void {
  controller?.abort()
}

function newSession(): void {
  if (streaming.value) {
    stop()
  }
  messages.value = []
  sessionId = createSessionId()
  lastModel.value = null
  ElMessage.success('已创建新会话')
}

function useSuggestion(question: string): void {
  input.value = question
}

function toggleSql(id: string): void {
  sqlOpen[id] = !sqlOpen[id]
}

function openDocument(docId: number, pageNo?: number): void {
  const query: Record<string, string> = { docId: String(docId) }
  if (pageNo) query.page = String(pageNo)
  router.push({ path: '/files', query })
}

function openReport(reportId: number): void {
  router.push({ path: '/reports', query: { reportId: String(reportId) } })
}

function scrollToBottom(): void {
  if (scrollScheduled) return
  scrollScheduled = true
  nextTick(() => {
    scrollScheduled = false
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
</script>

<style scoped>
.chat-page {
  height: 100%;
  padding: 16px;
}

.chat-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.chat-header {
  flex: none;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
}

.chat-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.chat-header p {
  margin: 0;
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  padding: 20px;
  overflow-y: auto;
  background: linear-gradient(180deg, #fbfcff, #f6f8fc);
}

.chat-welcome {
  max-width: 620px;
  margin: 40px auto;
  text-align: center;
}

.welcome-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  margin-bottom: 14px;
  border-radius: 16px;
  background: #eef4ff;
  color: var(--brand);
  font-size: 26px;
}

.chat-welcome h3 {
  margin: 0 0 6px;
  font-size: 18px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 18px;
}

.suggestion {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.suggestion:hover {
  border-color: #93c5fd;
  color: var(--brand);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.12);
}

.message {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #e2e8f0;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.message.user .avatar {
  background: var(--brand);
  color: #fff;
}

.message-body {
  max-width: min(860px, 88%);
}

.message.user .message-body {
  max-width: 72%;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--muted);
}

.sender {
  font-weight: 600;
  color: #475569;
}

.message-time {
  color: #94a3b8;
}

.user-bubble {
  padding: 10px 14px;
  border-radius: 10px 2px 10px 10px;
  background: var(--brand);
  color: #ffffff;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.assistant .message-body {
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 2px 10px 10px 10px;
  background: #ffffff;
}

.answer {
  margin-top: 2px;
}

.streaming-hint {
  color: var(--muted);
  font-size: 14px;
}

.dots {
  display: inline-block;
  animation: blink 1.2s infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 0.2;
  }
  50% {
    opacity: 1;
  }
}

.sql-panel {
  margin: 8px 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}

.sql-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  user-select: none;
}

.sql-code {
  margin: 0;
  padding: 10px 12px;
  max-height: 180px;
  overflow: auto;
  border-top: 1px solid var(--border);
  background: #ffffff;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  color: #334155;
}

.result-block,
.report-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}

.block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.report-title {
  font-size: 14px;
  font-weight: 600;
}

.review-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
}

.review-issue {
  color: #b45309;
}

.error-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

.stopped-line {
  margin-top: 8px;
}

.chat-input {
  flex: none;
  padding: 12px 20px 14px;
  border-top: 1px solid var(--border);
  background: #ffffff;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.input-tip {
  font-size: 12px;
}

@media (max-width: 720px) {
  .chat-page {
    padding: 8px;
  }

  .chat-header p {
    display: none;
  }

  .message-body,
  .message.user .message-body {
    max-width: 100%;
  }

  .input-tip {
    display: none;
  }
}
</style>
