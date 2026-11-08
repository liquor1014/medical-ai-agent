<template>
  <div class="status-page">
    <el-result icon="warning" title="403 无访问权限" sub-title="当前账号无权访问该功能或租户数据，请返回文件库继续使用。">
      <template #extra>
        <el-button type="primary" @click="router.push('/files')">返回文件库</el-button>
        <el-button @click="router.push('/login')">重新登录</el-button>
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
