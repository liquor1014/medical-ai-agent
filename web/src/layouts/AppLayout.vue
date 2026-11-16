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
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item v-if="hasPermission('system:tenant')" command="tenants">租户管理</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="app-body">
      <aside class="app-aside">
        <el-menu :default-active="activePath" router class="nav-menu">
          <template v-for="group in visibleMenu" :key="group.index">
            <el-sub-menu v-if="group.children" :index="group.index">
              <template #title>
                <el-icon><component :is="group.icon" /></el-icon>
                <span>{{ group.title }}</span>
              </template>
              <el-menu-item v-for="item in group.children" :key="item.index" :index="item.index">
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.title }}</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="group.index">
              <el-icon><component :is="group.icon" /></el-icon>
              <span>{{ group.title }}</span>
            </el-menu-item>
          </template>
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

    <el-dialog
      v-model="passwordVisible"
      title="修改密码"
      width="420px"
      :close-on-click-modal="false"
      @closed="resetPasswordForm"
    >
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="原密码">
          <el-input
            v-model="passwordForm.oldPassword"
            type="password"
            show-password
            placeholder="请输入当前密码"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            show-password
            :placeholder="`需 ${policy.minLength}-${policy.maxLength} 位，至少 ${policy.minClasses} 类字符`"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
          <PasswordStrength :password="passwordForm.newPassword" :policy="policy" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            @keyup.enter="onSubmitPassword"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSubmitting" @click="onSubmitPassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  FirstAidKit, User, ArrowDown, FolderOpened, ChatDotRound, DataAnalysis,
  Tickets, TrendCharts, Cpu, UserFilled, OfficeBuilding, Lock, Setting,
  Menu as MenuIcon, Tools
} from '@element-plus/icons-vue'
import { changePassword, fetchPasswordPolicy, fetchTenants, logout as logoutApi } from '@/api/auth'
import PasswordStrength from '@/components/PasswordStrength.vue'
import { clearAuth, getTenant, getUsername, hasPermission, isSuperAdmin, setTenant } from '@/store/auth'
import type { PasswordPolicy, TenantOption } from '@/types/api'
import { DEFAULT_PASSWORD_POLICY, passwordErrorMessage } from '@/utils/password'

const route = useRoute()
const router = useRouter()

const tenant = ref(getTenant())
const username = ref(getUsername() || '未登录')
const tenants = ref<TenantOption[]>([{ id: getTenant(), name: '演示院区' }])
const policy = ref<PasswordPolicy>({ ...DEFAULT_PASSWORD_POLICY })

const activePath = computed(() => route.path)

interface MenuItem {
  index: string
  title: string
  icon: unknown
  permission?: string
  children?: MenuItem[]
}

// 菜单配置：按权限码过滤，支持嵌套分组
const menuConfig: MenuItem[] = [
  {
    index: 'business',
    title: '业务功能',
    icon: MenuIcon,
    children: [
      { index: '/files', title: '文件库', icon: FolderOpened, permission: 'business:files' },
      { index: '/chat', title: '智能问答', icon: ChatDotRound, permission: 'business:chat' },
      { index: '/reports', title: '报表中心', icon: DataAnalysis, permission: 'business:reports' },
      { index: '/eval', title: '评测看板', icon: TrendCharts, permission: 'business:eval' },
      { index: '/models', title: '模型健康', icon: Cpu, permission: 'business:models' }
    ]
  },
  {
    index: 'system',
    title: '系统管理',
    icon: Setting,
    children: [
      { index: '/users', title: '用户管理', icon: UserFilled, permission: 'system:user' },
      { index: '/roles', title: '角色配置', icon: Tools, permission: 'system:role' },
      { index: '/tenants', title: '租户管理', icon: OfficeBuilding, permission: 'system:tenant' },
      { index: '/audit', title: '审计日志', icon: Tickets, permission: 'system:audit' }
    ]
  }
]

// 响应式：权限变化时自动重算可见菜单
const visibleMenu = computed<MenuItem[]>(() => {
  return menuConfig
    .map((group) => {
      if (!group.children) return group
      const children = group.children.filter((c) => !c.permission || hasPermission(c.permission))
      return children.length > 0 ? { ...group, children } : null
    })
    .filter((g): g is MenuItem => g !== null)
})

const passwordVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

onMounted(async () => {
  try {
    tenants.value = await fetchTenants()
  } catch {
    // 租户列表获取失败时保留默认项，不阻断主流程
  }
  try {
    policy.value = await fetchPasswordPolicy()
  } catch {
    // 策略接口异常时使用默认规则
  }
})

function onTenantChange(value: string): void {
  setTenant(value)
  ElMessage.success('已切换租户，数据按租户隔离')
  window.location.reload()
}

async function onCommand(command: string): Promise<void> {
  if (command === 'password') {
    passwordVisible.value = true
    return
  }
  if (command === 'tenants') {
    await router.push('/tenants')
    return
  }
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

function resetPasswordForm(): void {
  passwordForm.oldPassword = ''
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
}

async function onSubmitPassword(): Promise<void> {
  if (!passwordForm.oldPassword) {
    ElMessage.warning('请输入原密码')
    return
  }
  const message = passwordErrorMessage(passwordForm.newPassword, policy.value)
  if (message) {
    ElMessage.warning(message)
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  passwordSubmitting.value = true
  try {
    await changePassword(passwordForm.oldPassword, passwordForm.newPassword)
    ElMessage.success('密码修改成功')
    passwordVisible.value = false
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '密码修改失败')
  } finally {
    passwordSubmitting.value = false
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
