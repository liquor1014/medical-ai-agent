<template>
  <div ref="container" class="echart" :style="{ height: height || '320px' }"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  option: Record<string, unknown>
  height?: string
}>()

const container = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function render(): void {
  if (!chart) return
  chart.setOption(props.option as echarts.EChartsOption, true)
}

function handleResize(): void {
  chart?.resize()
}

onMounted(() => {
  if (container.value) {
    chart = echarts.init(container.value)
    render()
  }
  window.addEventListener('resize', handleResize)
})

watch(
  () => props.option,
  () => render(),
  { deep: true }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.echart {
  width: 100%;
}
</style>
