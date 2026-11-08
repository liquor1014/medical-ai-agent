<template>
  <div class="status-page">
    <el-result icon="info" title="404 页面不存在" sub-title="你访问的页面已被移动或不存在，请检查地址是否正确。">
      <template #extra>
        <el-button type="primary" @click="router.push('/files')">返回文件库</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.status-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--bg);
}
</style>
