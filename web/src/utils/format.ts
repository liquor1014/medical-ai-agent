export interface TagMeta {
  label: string
  type: 'success' | 'warning' | 'info' | 'danger' | 'primary'
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function documentStatusMeta(status: string): TagMeta {
  switch (status) {
    case 'pending':
      return { label: '待解析', type: 'info' }
    case 'parsing':
      return { label: '解析中', type: 'warning' }
    case 'completed':
      return { label: '已完成', type: 'success' }
    case 'failed':
      return { label: '解析失败', type: 'danger' }
    default:
      return { label: status || '未知', type: 'info' }
  }
}

export function docTypeLabel(type: string): string {
  const map: Record<string, string> = {
    pdf: 'PDF',
    docx: 'Word',
    txt: '文本',
    md: 'Markdown',
    image: '图片',
    unknown: '其他'
  }
  return map[type] || type
}

export function reportChartLabel(type?: string | null): string {
  const map: Record<string, string> = {
    line: '折线图',
    pie: '饼图',
    bar: '柱状图',
    none: '表格'
  }
  return map[type || ''] || '表格'
}

export function reportStatusMeta(status: string): TagMeta {
  switch (status) {
    case 'success':
      return { label: '成功', type: 'success' }
    case 'rejected':
      return { label: '已拦截', type: 'danger' }
    case 'failed':
      return { label: '执行失败', type: 'danger' }
    default:
      return { label: status || '未知', type: 'info' }
  }
}

export function intentLabel(intent?: string): string {
  const map: Record<string, string> = {
    retrieval: '文档检索',
    nl2sql: '数据查询',
    report: '报表生成',
    clarify: '意图追问'
  }
  return (intent && map[intent]) || '智能问答'
}
