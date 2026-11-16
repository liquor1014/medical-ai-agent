<template>
  <div class="tenant-page page-block">
    <div class="page-head">
      <div>
        <h2>租户管理</h2>
        <p class="muted">维护系统租户，登录页租户下拉列表实时读取此处配置，新增后无需改动代码。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增租户</el-button>
    </div>

    <div class="toolbar panel">
      <el-input
        v-model="keyword"
        placeholder="搜索租户 ID / 名称"
        clearable
        style="width: 240px"
      />
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      <span class="muted">共 {{ filtered.length }} 个租户</span>
    </div>

    <div class="table-panel panel">
      <el-table v-loading="loading" :data="filtered">
        <el-table-column prop="id" label="租户 ID" min-width="150" />
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column label="描述" min-width="180">
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="userCount" label="用户数" width="90" />
        <el-table-column prop="sortOrder" label="排序" width="80" />
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updatedAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑租户' : '新增租户'"
      width="460px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="租户 ID" prop="id">
          <el-input
            v-model="form.id"
            :disabled="editing"
            placeholder="如 hospital-c（小写字母 / 数字 / 中划线）"
            maxlength="64"
          />
        </el-form-item>
        <el-form-item label="租户名称" prop="name">
          <el-input v-model="form.name" maxlength="128" placeholder="如 C 院区" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sortOrder" :min="0" :max="9999" />
          <span class="form-tip muted">数值越小越靠前</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">
          {{ editing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

import { createTenant, deleteTenant, fetchTenantAdminList, updateTenant } from '@/api/tenants'
import type { TenantItem } from '@/types/api'
import { formatDateTime } from '@/utils/format'

const items = ref<TenantItem[]>([])
const loading = ref(false)
const keyword = ref('')

const dialogVisible = ref(false)
const editing = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  id: '',
  name: '',
  description: '',
  sortOrder: 0,
  active: true
})

const rules: FormRules = {
  id: [
    { required: true, message: '请输入租户 ID', trigger: 'blur' },
    {
      pattern: /^[a-z0-9][a-z0-9-]{1,62}$/,
      message: '租户 ID 需为 2-63 位小写字母、数字或中划线，且以字母或数字开头',
      trigger: 'blur'
    }
  ],
  name: [{ required: true, message: '请输入租户名称', trigger: 'blur' }]
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(
    (t) => t.id.toLowerCase().includes(kw) || t.name.toLowerCase().includes(kw)
  )
})

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await fetchTenantAdminList()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '租户列表加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editing.value = false
  form.id = ''
  form.name = ''
  form.description = ''
  form.sortOrder = items.value.length * 10
  form.active = true
  dialogVisible.value = true
}

function openEdit(row: TenantItem): void {
  editing.value = true
  form.id = row.id
  form.name = row.name
  form.description = row.description || ''
  form.sortOrder = row.sortOrder
  form.active = row.status === 'active'
  dialogVisible.value = true
}

function resetForm(): void {
  formRef.value?.clearValidate()
}

async function submit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      status: form.active ? 'active' : 'disabled',
      sortOrder: form.sortOrder
    }
    if (editing.value) {
      await updateTenant(form.id, payload)
      ElMessage.success('租户已更新')
    } else {
      await createTenant({ ...payload, id: form.id.trim() })
      ElMessage.success('租户已创建，登录页下拉列表已同步')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row: TenantItem): Promise<void> {
  const nextStatus = row.status === 'active' ? 'disabled' : 'active'
  try {
    await updateTenant(row.id, {
      name: row.name,
      description: row.description || undefined,
      status: nextStatus,
      sortOrder: row.sortOrder
    })
    ElMessage.success(nextStatus === 'active' ? '租户已启用' : '租户已禁用')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '状态更新失败')
  }
}

async function remove(row: TenantItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除租户「${row.name}」？该租户下存在用户时无法删除。`,
      '删除租户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteTenant(row.id)
    ElMessage.success('租户已删除')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}
</script>

<style scoped>
.tenant-page {
  padding: 20px 24px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.table-panel {
  padding: 6px 4px;
}

.form-tip {
  margin-left: 10px;
  font-size: 12px;
}
</style>
