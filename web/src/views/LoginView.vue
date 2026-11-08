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
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            :placeholder="isRegister ? '6-64 位密码' : '请输入密码'"
            show-password
            @keyup.enter="onSubmit"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
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
        <span>演示账号：admin / admin123</span>
        <el-button link type="primary" size="small" @click="fillDemo">一键填入</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { login, register } from '@/api/auth'
import { DEFAULT_TENANT, saveSession, setTenant } from '@/store/auth'

const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance>()
const loading = ref(false)
const mode = ref<'login' | 'register'>('login')
const isRegister = computed(() => mode.value === 'register')

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  displayName: ''
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

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]{3,32}$/, message: '用户名需为 3-32 位字母、数字或下划线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6-64 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const activeRules = computed(() => (isRegister.value ? registerRules : loginRules))

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
          displayName: form.displayName.trim() || undefined
        })
      : await login(username, form.password)
    saveSession(result.token, result.username)
    setTenant(DEFAULT_TENANT)
    ElMessage.success(isRegister.value ? '注册成功，已自动登录' : '登录成功')
    const redirect = (route.query.redirect as string) || '/files'
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : (isRegister.value ? '注册失败' : '登录失败'))
  } finally {
    loading.value = false
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
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
  color: var(--muted);
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
