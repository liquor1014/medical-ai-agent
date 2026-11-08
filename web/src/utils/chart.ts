type Row = Record<string, unknown>

function isNumericColumn(column: string, rows: Row[]): boolean {
  return rows.length > 0 && rows.every((row) => {
    const value = row[column]
    return typeof value === 'number' && Number.isFinite(value)
  })
}

function pickValueColumn(columns: string[], rows: Row[]): string | null {
  const numeric = columns.filter((column, index) => index > 0 && isNumericColumn(column, rows))
  const preferred = numeric.filter((column) => !['单价', '价格', '率'].some((key) => column.includes(key)))
  const usable = preferred.length > 0 ? preferred : numeric
  if (usable.length === 0) return null
  const amount = usable.find((column) => column.includes('金额') || column.includes('总额'))
  if (amount) return amount
  const quantity = usable.find((column) => column.includes('数量') || column.includes('库存'))
  return quantity || usable[0]
}

/**
 * 根据报表列与数据构造 ECharts 配置（与 AI 服务端规则保持一致）。
 */
export function buildChartOption(
  columns: string[],
  rows: Row[],
  chartType?: string | null,
  title = '数据报表'
): Record<string, unknown> | null {
  if (!columns.length || !rows.length) return null

  const categories = rows.map((row) => String(row[columns[0]] ?? ''))
  const numericColumns = columns.filter((column, index) => index > 0 && isNumericColumn(column, rows))
  const preferred = numericColumns.filter(
    (column) => !['单价', '价格', '率'].some((key) => column.includes(key))
  )
  const usable = preferred.length > 0 ? preferred : numericColumns
  if (usable.length === 0) return null

  const inferred = categories.every((value) => /^\d{4}-\d{2}$/.test(value)) ? 'line' : 'bar'
  const type = chartType && ['line', 'pie', 'bar'].includes(chartType) ? chartType : inferred

  if (type === 'pie') {
    const valueColumn = pickValueColumn(columns, rows) || usable[0]
    return {
      title: { text: title, left: 'center' },
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', right: 10, top: 'middle' },
      series: [
        {
          name: title,
          type: 'pie',
          radius: ['35%', '65%'],
          center: ['45%', '55%'],
          data: rows.map((row) => ({
            name: String(row[columns[0]] ?? ''),
            value: row[valueColumn]
          }))
        }
      ]
    }
  }

  return {
    title: { text: title, left: 'center' },
    tooltip: { trigger: 'axis' },
    legend: { top: 30, data: usable },
    grid: { left: 60, right: 30, bottom: 60, top: 70 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { rotate: 30, interval: 0 }
    },
    yAxis: { type: 'value' },
    series: usable.map((column) => ({
      name: column,
      type,
      smooth: type === 'line',
      data: rows.map((row) => row[column])
    }))
  }
}
