<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <div class="brand-logo">
          <el-icon><FirstAidKit /></el-icon>
        </div>
        <div class="brand-text">
          <h1>医疗文件检索与报表统计 Agent</h1>
          <span class="brand-sub">SPD分析 · 演示环境</span>
        </div>
      </div>

      <div class="header-actions">
        <el-select
          v-model="tenant"
          size="small"
          class="tenant-select"
          @change="onTenantChange"
        >
          <el-option v-for="item in tenants" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-dropdown @command="onCommand">
          <span class="user-chip">
            <el-icon><User /></el-icon>
            <span class="user-name">{{ username }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="app-body">
      <aside class="app-aside">
        <el-menu :default-active="activePath" router class="nav-menu">
          <el-menu-item index="/files">
            <el-icon><FolderOpened /></el-icon>
            <span>文件库</span>
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能问答</span>
          </el-menu-item>
          <el-menu-item index="/reports">
            <el-icon><DataAnalysis /></el-icon>
            <span>报表中心</span>
          </el-menu-item>
          <el-menu-item index="/audit">
            <el-icon><Tickets /></el-icon>
            <span>审计日志</span>
          </el-menu-item>
          <el-menu-item index="/eval">
            <el-icon><TrendCharts /></el-icon>
            <span>评测看板</span>
          </el-menu-item>
          <el-menu-item index="/models">
            <el-icon><Cpu /></el-icon>
            <span>模型健康</span>
          </el-menu-item>
        </el-menu>
        <div class="aside-footer">
          <span>P0 主链路</span>
          <span>文件 → 检索 → 问答 → 报表</span>
        </div>
      </aside>

      <main class="app-main">
        <router-view />
      </main>
    </div>

    <footer class="app-footer">
      本系统仅用于医院 SPD / 经营分析辅助，不提供诊疗建议；演示数据均为合成数据。
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchTenants, logout as logoutApi } from '@/api/auth'
import { clearAuth, getTenant, getUsername, setTenant } from '@/store/auth'
import type { TenantOption } from '@/types/api'

const route = useRoute()
const router = useRouter()

const tenant = ref(getTenant())
const username = ref(getUsername() || '未登录')
const tenants = ref<TenantOption[]>([{ id: getTenant(), name: '演示院区' }])

const activePath = computed(() => route.path)

onMounted(async () => {
  try {
    tenants.value = await fetchTenants()
  } catch {
    // 租户列表获取失败时保留默认项，不阻断主流程
  }
})

function onTenantChange(value: string): void {
  setTenant(value)
  ElMessage.success('已切换租户，数据按租户隔离')
  window.location.reload()
}

async function onCommand(command: string): Promise<void> {
  if (command === 'logout') {
    try {
      await logoutApi()
    } catch {
      // 退出失败不影响本地清理
    }
    clearAuth()
    router.replace('/login')
  }
}
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
}

.app-header {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 62px;
  padding: 0 20px;
  background: #ffffff;
  border-bottom: 1px solid var(--border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #0ea5a4);
  color: #fff;
  font-size: 18px;
}

.brand-text h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brand-sub {
  font-size: 12px;
  color: var(--muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tenant-select {
  width: 140px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.app-aside {
  flex: none;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 196px;
  padding: 10px 8px 14px;
  background: #ffffff;
  border-right: 1px solid var(--border);
}

.nav-menu {
  border-right: none;
}

.nav-menu :deep(.el-menu-item) {
  height: 44px;
  margin-bottom: 4px;
  border-radius: 8px;
}

.nav-menu :deep(.el-menu-item.is-active) {
  background: #eef4ff;
  font-weight: 600;
}

.aside-footer {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  font-size: 12px;
  color: #94a3b8;
  border-top: 1px dashed var(--border);
}

.app-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.app-footer {
  flex: none;
  padding: 6px 20px;
  background: #ffffff;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
  text-align: center;
}

@media (max-width: 960px) {
  .brand-text h1 {
    font-size: 15px;
  }

  .brand-sub {
    display: none;
  }

  .app-aside {
    width: 64px;
  }

  .nav-menu :deep(.el-menu-item span) {
    display: none;
  }

  .aside-footer {
    display: none;
  }
}

@media (max-width: 640px) {
  .brand-text {
    display: none;
  }

  .app-footer {
    display: none;
  }
}
</style>
