<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true"></div>

    <section class="login-hero">
      <div class="hero-badge">医疗 SPD Demo</div>
      <h1>医疗文件检索与<br />报表统计 Agent</h1>
      <p class="hero-desc">
        上传院内制度与耗材文档，基于引用页码回答问题；用自然语言生成库存、供应商、科室消耗报表。
      </p>
      <ul class="hero-list">
        <li><el-icon><Document /></el-icon> 文档解析 + 检索问答 + 页码引用</li>
        <li><el-icon><ChatDotRound /></el-icon> SSE 流式对话，支持停止与重连</li>
        <li><el-icon><DataAnalysis /></el-icon> NL2SQL 报表、图表与 CSV 导出</li>
      </ul>
      <p class="hero-note">仅用于管理辅助，不提供诊疗建议；演示数据均为合成数据。</p>
    </section>

    <section class="login-card">
      <div class="card-head">
        <div class="card-logo">
          <el-icon><FirstAidKit /></el-icon>
        </div>
        <div>
          <h2>{{ isRegister ? '注册账号' : '登录系统' }}</h2>
          <p class="muted">
            {{ isRegister ? '注册成功后自动登录，默认角色为医生' : '使用演示账号进入工作台' }}
          </p>
        </div>
      </div>

      <el-form ref="formRef" :model="form" :rules="activeRules" label-position="top" @submit.prevent>
        <el-form-item label="所属租户" prop="tenantId">
          <el-select
            v-model="form.tenantId"
            size="large"
            filterable
            placeholder="请选择所属租户"
            style="width: 100%"
            :loading="tenantLoading"
          >
            <el-option
              v-for="t in tenants"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" size="large" placeholder="请输入用户名" clearable>
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item v-if="isRegister" label="昵称（选填）" prop="displayName">
          <el-input
            v-model="form.displayName"
            size="large"
            placeholder="用于页面展示，默认与用户名相同"
            maxlength="64"
            clearable
          >
            <template #prefix>
              <el-icon><Avatar /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item v-if="isRegister" label="绑定邮箱" prop="email">
          <el-input
            v-model="form.email"
            size="large"
            placeholder="用于找回密码，如 name@example.com"
            maxlength="128"
            clearable
          >
            <template #prefix>
              <el-icon><Message /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <template #label>
            <span>密码</span>
          </template>
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            :placeholder="isRegister ? passwordPlaceholder : '请输入密码'"
            show-password
            @keyup.enter="onSubmit"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
          <PasswordStrength v-if="isRegister" :password="form.password" :policy="policy" />
          <div class="pwd-label">
            <el-button v-if="!isRegister" link type="primary" class="forgot-link" @click="openReset">
              忘记密码？
            </el-button>
          </div>
        </el-form-item>
        <el-form-item v-if="isRegister" label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            size="large"
            placeholder="请再次输入密码"
            show-password
            @keyup.enter="onSubmit"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          @click="onSubmit"
        >
          {{ isRegister ? '注 册' : '登 录' }}
        </el-button>
      </el-form>

      <div class="account-switch">
        <template v-if="isRegister">
          <span>已有账号？</span>
          <el-button link type="primary" size="small" @click="switchMode('login')">返回登录</el-button>
        </template>
        <template v-else>
          <span>还没有账号？</span>
          <el-button link type="primary" size="small" @click="switchMode('register')">注册账号</el-button>
        </template>
      </div>

      <div v-if="!isRegister" class="demo-account">
        <span>演示账号：admin / admin123 · 邮箱 admin@demo.local</span>
        <el-button link type="primary" size="small" @click="fillDemo">一键填入</el-button>
      </div>
    </section>

    <el-dialog
      v-model="resetVisible"
      title="找回密码"
      width="440px"
      :close-on-click-modal="false"
      @closed="onResetClosed"
    >
      <el-steps :active="resetStep" simple class="reset-steps">
        <el-step title="验证身份" />
        <el-step title="校验验证码" />
        <el-step title="设置新密码" />
      </el-steps>

      <el-form v-if="resetStep === 0" label-position="top" @submit.prevent>
        <el-form-item label="所属租户">
          <el-select v-model="resetForm.tenantId" filterable style="width: 100%">
            <el-option v-for="t in tenants" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="resetForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="绑定邮箱">
          <el-input v-model="resetForm.email" placeholder="请输入注册时绑定的邮箱" clearable />
        </el-form-item>
        <p class="reset-tip muted">将向绑定邮箱发送 6 位验证码，用于校验账号归属。</p>
      </el-form>

      <el-form v-else-if="resetStep === 1" label-position="top" @submit.prevent>
        <el-form-item label="验证码">
          <el-input
            v-model="resetForm.code"
            maxlength="6"
            placeholder="请输入 6 位数字验证码"
            @keyup.enter="onVerifyCode"
          />
        </el-form-item>
        <el-alert v-if="demoCode" type="warning" :closable="false" show-icon class="demo-code">
          <template #title>演示环境未配置 SMTP，验证码：{{ demoCode }}</template>
        </el-alert>
        <p class="reset-tip muted">验证码 {{ resetCodeSeconds }} 秒内有效，请勿泄露给他人。</p>
      </el-form>

      <el-form v-else label-position="top" @submit.prevent>
        <el-form-item label="新密码">
          <el-input v-model="resetForm.newPassword" type="password" show-password placeholder="请输入新密码">
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
          <PasswordStrength :password="resetForm.newPassword" :policy="policy" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="resetForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            @keyup.enter="onResetSubmit"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <template v-if="resetStep === 0">
          <el-button type="primary" :loading="resetLoading" @click="onSendCode">发送验证码</el-button>
        </template>
        <template v-else-if="resetStep === 1">
          <el-button :disabled="countdown > 0" :loading="resetLoading" @click="onSendCode">
            {{ countdown > 0 ? `重新发送(${countdown}s)` : '重新发送' }}
          </el-button>
          <el-button type="primary" :loading="resetLoading" @click="onVerifyCode">验证并下一步</el-button>
        </template>
        <template v-else>
          <el-button @click="resetStep = 1">上一步</el-button>
          <el-button type="primary" :loading="resetLoading" @click="onResetSubmit">确认重置</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import {
  fetchPasswordPolicy,
  fetchTenants,
  login,
  register,
  resetPassword,
  sendResetCode,
  verifyResetCode
} from '@/api/auth'
import PasswordStrength from '@/components/PasswordStrength.vue'
import type { PasswordPolicy, TenantOption } from '@/types/api'
import { DEFAULT_TENANT, saveSession, setTenant } from '@/store/auth'
import { DEFAULT_PASSWORD_POLICY, passwordErrorMessage } from '@/utils/password'

const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance>()
const loading = ref(false)
const mode = ref<'login' | 'register'>('login')
const isRegister = computed(() => mode.value === 'register')

const tenants = ref<TenantOption[]>([])
const tenantLoading = ref(false)
const policy = ref<PasswordPolicy>({ ...DEFAULT_PASSWORD_POLICY })
const resetCodeSeconds = ref(300)

const passwordPlaceholder = computed(
  () => `需 ${policy.value.minLength}-${policy.value.maxLength} 位，至少 ${policy.value.minClasses} 类字符`
)

async function loadTenants(): Promise<void> {
  tenantLoading.value = true
  try {
    const list = await fetchTenants()
    tenants.value = list
    // 如果当前默认租户在列表里就保持，否则选第一个
    if (!list.some((t) => t.id === form.tenantId) && list.length > 0) {
      form.tenantId = list[0].id
    }
  } catch (error) {
    ElMessage.warning('租户列表加载失败，使用默认租户')
  } finally {
    tenantLoading.value = false
  }
}

async function loadPolicy(): Promise<void> {
  try {
    policy.value = await fetchPasswordPolicy()
  } catch {
    // 接口异常时使用前端默认规则，登录/注册主流程不受影响
  }
}

onMounted(() => {
  loadTenants()
  loadPolicy()
})

onBeforeUnmount(() => stopCountdown())

const form = reactive({
  tenantId: DEFAULT_TENANT,
  username: '',
  password: '',
  confirmPassword: '',
  displayName: '',
  email: ''
})

function validateConfirmPassword(
  _rule: unknown,
  value: string,
  callback: (error?: string | Error) => void
): void {
  if (value === form.password) {
    callback()
  } else {
    callback(new Error('两次输入的密码不一致'))
  }
}

function validatePolicyPassword(
  _rule: unknown,
  value: string,
  callback: (error?: string | Error) => void
): void {
  const message = passwordErrorMessage(value, policy.value)
  callback(message ? new Error(message) : undefined)
}

const loginRules: FormRules = {
  tenantId: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const registerRules = computed<FormRules>(() => ({
  tenantId: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]{3,32}$/, message: '用户名需为 3-32 位字母、数字或下划线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入绑定邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePolicyPassword, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}))

const activeRules = computed(() => (isRegister.value ? registerRules.value : loginRules))

function switchMode(next: 'login' | 'register'): void {
  mode.value = next
  form.password = ''
  form.confirmPassword = ''
  formRef.value?.clearValidate()
}

function fillDemo(): void {
  form.username = 'admin'
  form.password = 'admin123'
}

async function onSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const username = form.username.trim()
    const result = isRegister.value
      ? await register({
          username,
          password: form.password,
          displayName: form.displayName.trim() || undefined,
          email: form.email.trim()
        })
      : await login(username, form.password)
    saveSession(result.token, result.username, result.role, result.tenantId || form.tenantId)
    setTenant(result.tenantId || form.tenantId)
    ElMessage.success(isRegister.value ? '注册成功，已自动登录' : '登录成功')
    const redirect = (route.query.redirect as string) || '/files'
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : (isRegister.value ? '注册失败' : '登录失败'))
  } finally {
    loading.value = false
  }
}

// ---------------- 找回密码 ----------------
const resetVisible = ref(false)
const resetStep = ref(0)
const resetLoading = ref(false)
const resetTicket = ref('')
const demoCode = ref('')
const countdown = ref(0)
let countdownTimer: number | undefined

const resetForm = reactive({
  tenantId: DEFAULT_TENANT,
  username: '',
  email: '',
  code: '',
  newPassword: '',
  confirmPassword: ''
})

function openReset(): void {
  resetStep.value = 0
  resetTicket.value = ''
  demoCode.value = ''
  countdown.value = 0
  resetForm.tenantId = form.tenantId || DEFAULT_TENANT
  resetForm.username = form.username.trim()
  resetForm.email = ''
  resetForm.code = ''
  resetForm.newPassword = ''
  resetForm.confirmPassword = ''
  resetVisible.value = true
}

function onResetClosed(): void {
  stopCountdown()
  countdown.value = 0
}

function startCountdown(seconds: number): void {
  stopCountdown()
  countdown.value = seconds
  countdownTimer = window.setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      stopCountdown()
    }
  }, 1000)
}

function stopCountdown(): void {
  if (countdownTimer !== undefined) {
    window.clearInterval(countdownTimer)
    countdownTimer = undefined
  }
}

function resetError(message: unknown): void {
  ElMessage.error(message instanceof Error ? message.message : '操作失败，请稍后重试')
}

async function onSendCode(): Promise<void> {
  const username = resetForm.username.trim()
  const email = resetForm.email.trim()
  if (!username) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    ElMessage.warning('请输入正确的绑定邮箱')
    return
  }
  resetLoading.value = true
  try {
    const result = await sendResetCode({ tenantId: resetForm.tenantId, username, email })
    demoCode.value = result.demoCode || ''
    resetCodeSeconds.value = result.expiresInSeconds || 300
    resetStep.value = 1
    startCountdown(60)
    ElMessage.success(result.delivered ? '验证码已发送至绑定邮箱' : '演示环境验证码已生成，请查看下方提示')
  } catch (error) {
    resetError(error)
  } finally {
    resetLoading.value = false
  }
}

async function onVerifyCode(): Promise<void> {
  if (!/^\d{6}$/.test(resetForm.code.trim())) {
    ElMessage.warning('请输入 6 位数字验证码')
    return
  }
  resetLoading.value = true
  try {
    resetTicket.value = await verifyResetCode({
      tenantId: resetForm.tenantId,
      username: resetForm.username.trim(),
      email: resetForm.email.trim(),
      code: resetForm.code.trim()
    })
    resetStep.value = 2
    ElMessage.success('验证码校验通过，请设置新密码')
  } catch (error) {
    resetError(error)
  } finally {
    resetLoading.value = false
  }
}

async function onResetSubmit(): Promise<void> {
  const message = passwordErrorMessage(resetForm.newPassword, policy.value)
  if (message) {
    ElMessage.warning(message)
    return
  }
  if (resetForm.newPassword !== resetForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  resetLoading.value = true
  try {
    await resetPassword({
      tenantId: resetForm.tenantId,
      username: resetForm.username.trim(),
      resetTicket: resetTicket.value,
      newPassword: resetForm.newPassword
    })
    ElMessage.success('密码重置成功，请使用新密码登录')
    resetVisible.value = false
    form.username = resetForm.username.trim()
    form.password = ''
  } catch (error) {
    resetError(error)
  } finally {
    resetLoading.value = false
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 64px;
  min-height: 100%;
  padding: 40px 6vw;
  overflow-x: hidden;
  overflow-y: auto;
  background: #0f172a;
}

.login-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(1000px 520px at 10% 0%, rgba(37, 99, 235, 0.45), transparent 60%),
    radial-gradient(900px 480px at 85% 100%, rgba(14, 165, 164, 0.35), transparent 60%),
    linear-gradient(140deg, #0b1220, #16243d);
}

.login-hero,
.login-card {
  position: relative;
  z-index: 1;
}

.login-hero {
  max-width: 560px;
  color: #e2e8f0;
}

.hero-badge {
  display: inline-block;
  margin-bottom: 20px;
  padding: 5px 12px;
  border: 1px solid rgba(148, 197, 255, 0.35);
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 0.5px;
  color: #bcd8ff;
}

.login-hero h1 {
  margin: 0 0 16px;
  font-size: 36px;
  line-height: 1.25;
  font-weight: 700;
  color: #ffffff;
}

.hero-desc {
  margin: 0 0 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #94a3b8;
}

.hero-list {
  margin: 0 0 28px;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
  color: #cbd5e1;
}

.hero-list li {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-list .el-icon {
  color: #60a5fa;
  font-size: 16px;
}

.hero-note {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.login-card {
  width: 380px;
  max-width: 100%;
  padding: 32px 30px 24px;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 24px 60px rgba(2, 8, 23, 0.35);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.card-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #0ea5a4);
  color: #fff;
  font-size: 20px;
}

.card-head h2 {
  margin: 0 0 2px;
  font-size: 19px;
}

.card-head p {
  margin: 0;
}

.pwd-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 110%;
}

.forgot-link {
  height: auto;
  padding: 0;
  font-size: 12px;
}

.submit-btn {
  width: 100%;
  margin-top: 6px;
  letter-spacing: 4px;
}

.account-switch {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--muted);
}

.demo-account {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
  color: var(--muted);
}

.reset-steps {
  margin-bottom: 18px;
}

.reset-tip {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 18px;
}

.demo-code {
  margin-top: 4px;
}

@media (max-width: 900px) {
  .login-page {
    flex-direction: column;
    gap: 28px;
    padding: 32px 20px;
  }

  .login-hero {
    text-align: center;
  }

  .login-hero h1 {
    font-size: 26px;
  }

  .hero-list {
    display: none;
  }

  .login-card {
    width: 100%;
    max-width: 400px;
  }
}
</style>
