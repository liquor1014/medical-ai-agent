<template>
  <div class="role-page page-block">
    <div class="page-head">
      <div>
        <h2>角色配置</h2>
        <p class="muted">
          管理系统角色及其启停状态。内置角色（超级管理员、租户管理员、医生）不可删除，超级管理员不可停用。
        </p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建角色</el-button>
    </div>

    <div class="toolbar panel">
      <el-input
        v-model="keyword"
        placeholder="搜索角色编码 / 名称"
        clearable
        style="width: 240px"
      />
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      <span class="muted">共 {{ filtered.length }} 个角色</span>
    </div>

    <div class="table-panel panel">
      <el-table v-loading="loading" :data="filtered">
        <el-table-column prop="code" label="角色编码" min-width="160" />
        <el-table-column prop="name" label="角色名称" min-width="130" />
        <el-table-column label="描述" min-width="200">
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.isBuiltin ? 'warning' : 'info'" size="small">
              {{ row.isBuiltin ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status === 'enabled'"
              :disabled="row.code === SUPER_ADMIN_ROLE"
              @change="onStatusChange(row)"
            />
            <span class="status-text">{{ row.status === 'enabled' ? '启用' : '停用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              type="danger"
              :disabled="row.isBuiltin"
              @click="remove(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑角色' : '新建角色'"
      width="460px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="角色编码" prop="code">
          <el-input
            v-model="form.code"
            :disabled="editing"
            placeholder="如 dept_admin（小写字母 / 数字 / 下划线）"
            maxlength="64"
          />
          <span v-if="editing" class="form-tip muted">角色编码创建后不可修改</span>
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" maxlength="128" placeholder="如 科室管理员" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            maxlength="255"
            placeholder="可选，简要说明该角色的职责范围"
          />
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

import {
  createRole,
  deleteRole,
  listRoles,
  toggleRoleStatus,
  updateRole
} from '@/api/role'
import type { RoleConfig } from '@/types/api'

/** 超级管理员角色编码（内置，不可删除、不可停用） */
const SUPER_ADMIN_ROLE = 'super_admin'

const items = ref<RoleConfig[]>([])
const loading = ref(false)
const keyword = ref('')

const dialogVisible = ref(false)
const editing = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  code: '',
  name: '',
  description: ''
})

const rules: FormRules = {
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    {
      pattern: /^[a-z][a-z0-9_]{1,62}$/,
      message: '角色编码需为 2-63 位小写字母、数字或下划线，且以字母开头',
      trigger: 'blur'
    }
  ],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(
    (r) => r.code.toLowerCase().includes(kw) || r.name.toLowerCase().includes(kw)
  )
})

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await listRoles()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '角色列表加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editing.value = false
  form.code = ''
  form.name = ''
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row: RoleConfig): void {
  editing.value = true
  form.code = row.code
  form.name = row.name
  form.description = row.description || ''
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
      description: form.description.trim() || undefined
    }
    if (editing.value) {
      await updateRole(form.code, payload)
      ElMessage.success('角色已更新')
    } else {
      await createRole({ ...payload, code: form.code.trim() })
      ElMessage.success('角色已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function onStatusChange(row: RoleConfig): Promise<void> {
  const nextStatus = row.status === 'enabled' ? 'disabled' : 'enabled'
  const action = nextStatus === 'enabled' ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      `确认${action}角色「${row.name}」？${action === '停用' ? '停用后持有该角色的用户将无法登录。' : ''}`,
      `${action}角色`,
      { type: 'warning', confirmButtonText: action, cancelButtonText: '取消' }
    )
  } catch {
    // 取消后回滚开关显示
    await load()
    return
  }
  try {
    await toggleRoleStatus(row.code, nextStatus)
    ElMessage.success(`角色已${action}`)
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '状态更新失败')
    await load()
  }
}

async function remove(row: RoleConfig): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除角色「${row.name}」？若该角色下仍有用户绑定，将无法删除。`,
      '删除角色',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteRole(row.code)
    ElMessage.success('角色已删除')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}
</script>

<style scoped>
.role-page {
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
  margin-top: 4px;
  font-size: 12px;
}

.status-text {
  margin-left: 8px;
  font-size: 13px;
  color: var(--muted);
}
</style>
