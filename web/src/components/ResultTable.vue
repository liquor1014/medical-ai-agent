<template>
  <div class="result-table">
    <el-empty v-if="!columns.length" description="暂无可展示的数据" :image-size="64" />
    <el-table
      v-else
      :data="rows"
      border
      stripe
      size="small"
      :max-height="maxHeight || 320"
      style="width: 100%"
    >
      <el-table-column
        v-for="column in columns"
        :key="column"
        :prop="column"
        :label="column"
        min-width="120"
        show-overflow-tooltip
      />
    </el-table>
    <div v-if="columns.length" class="table-footer muted">
      共 {{ rowCount ?? rows.length }} 行
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount?: number
  maxHeight?: number
}>()
</script>

<style scoped>
.result-table {
  width: 100%;
}

.table-footer {
  padding-top: 8px;
  text-align: right;
}
</style>
