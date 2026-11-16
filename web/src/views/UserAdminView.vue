<template>
  <div class="user-page page-block">
    <div class="page-head">
      <div>
        <h2>用户管理</h2>
        <p class="muted">
          管理租户内用户与角色。每个租户仅允许一个「租户管理员」；超级管理员可跨租户操作。
        </p>
      </div>
    </div>

    <div class="toolbar panel">
      <template v-if="isSuperAdminUser">
        <el-select
          v-model="selectedTenant"
          placeholder="选择租户"
          filterable
          style="width: 200px"
          @change="load"
        >
          <el-option v-for="t in tenants" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </template>
      <template v-else>
        <span class="muted">当前租户：{{ currentTenant }}</span>
      </template>
      <el-input
        v-model="keyword"
        placeholder="搜索用户名 / 昵称"
        clearable
        style="width: 220px"
      />
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      <span class="muted">共 {{ filtered.length }} 位用户</span>
    </div>

    <div class="table-panel panel">
      <el-table v-loading="loading" :data="filtered">
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column label="昵称" min-width="120">
          <template #default="{ row }">{{ row.display_name || row.username }}</template>
        </el-table-column>
        <el-table-column label="邮箱" min-width="180">
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="180">
          <template #default="{ row }">
            <el-select
              v-model="row.role"
              size="small"
              style="width: 100%"
              :disabled="row.username === SUPER_ADMIN_USERNAME"
              @change="onRoleChange(row)"
            >
              <el-option
                v-for="opt in roleOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ row.last_login_at ? formatDateTime(row.last_login_at) : '从未登录' }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { assignRole, listTenantUsers } from '@/api/admin'
import { fetchTenants } from '@/api/auth'
import { getTenant, getUsername, isSuperAdmin, SUPER_ADMIN_USERNAME, refreshPermissions } from '@/store/auth'
import type { TenantOption, TenantUser } from '@/types/api'
import { formatDateTime } from '@/utils/format'

const isSuperAdminUser = isSuperAdmin()
const currentTenant = getTenant()

const tenants = ref<TenantOption[]>([])
const selectedTenant = ref(currentTenant)
const users = ref<TenantUser[]>([])
const keyword = ref('')
const loading = ref(false)

// 角色下拉选项：禁止分配 super_admin（仅 superAdmin 账号硬编码持有）
const roleOptions = computed(() => {
  return [
    { label: '租户管理员', value: 'tenant_admin' },
    { label: '医生', value: 'doctor' }
  ]
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return users.value
  return users.value.filter(
    (u) =>
      u.username.toLowerCase().includes(kw) ||
      (u.display_name || '').toLowerCase().includes(kw)
  )
})

async function load(): Promise<void> {
  loading.value = true
  try {
    users.value = await listTenantUsers(isSuperAdminUser ? selectedTenant.value : undefined)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function onRoleChange(row: TenantUser): Promise<void> {
  try {
    await assignRole(row.id, row.role, isSuperAdminUser ? selectedTenant.value : undefined)
    ElMessage.success(`已将 ${row.username} 的角色更新为 ${roleLabel(row.role)}`)
    // 若变更的是当前用户自身角色，刷新权限以同步菜单
    if (row.username === getUsername()) {
      await refreshPermissions()
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '角色分配失败')
    // 回滚：重新加载
    await load()
  }
}

function roleLabel(role: string): string {
  return roleOptions.value.find((o) => o.value === role)?.label || role
}

onMounted(async () => {
  if (isSuperAdminUser) {
    try {
      tenants.value = await fetchTenants()
    } catch {
      // ignore
    }
  }
  await load()
})
</script>

<style scoped>
.user-page {
  padding: 24px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-head h2 {
  margin: 0 0 4px;
  font-size: 20px;
}

.muted {
  color: var(--muted);
  font-size: 13px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 16px;
}

.panel {
  background: #fff;
  border-radius: 10px;
  border: 1px solid var(--border);
}

.table-panel {
  padding: 16px;
}
</style>
