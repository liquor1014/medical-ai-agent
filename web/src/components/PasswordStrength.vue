<template>
  <div class="pwd-strength">
    <div class="strength-track">
      <div class="strength-bar" :class="levelClass" :style="{ width: percent + '%' }"></div>
    </div>
    <ul class="rule-list">
      <li :class="{ ok: check.length }">
        <el-icon><CircleCheck v-if="check.length" /><CircleClose v-else /></el-icon>
        <span>长度 {{ policy.minLength }}-{{ policy.maxLength }} 位</span>
      </li>
      <li :class="{ ok: check.classes }">
        <el-icon><CircleCheck v-if="check.classes" /><CircleClose v-else /></el-icon>
        <span>至少 {{ policy.minClasses }} 类字符（已含 {{ check.classCount }} 类：大写 / 小写 / 数字 / 特殊）</span>
      </li>
      <li :class="{ ok: check.noSpace }">
        <el-icon><CircleCheck v-if="check.noSpace" /><CircleClose v-else /></el-icon>
        <span>不包含空格</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { evaluatePassword } from '@/utils/password'
import type { PasswordPolicy } from '@/types/api'

const props = defineProps<{
  password: string
  policy: PasswordPolicy
}>()

const check = computed(() => evaluatePassword(props.password, props.policy))

const percent = computed(() => {
  if (!props.password) return 0
  const passed = [check.value.length, check.value.classes, check.value.noSpace].filter(Boolean).length
  return (passed / 3) * 100
})

const levelClass = computed(() => {
  if (check.value.valid) return 'is-strong'
  if (percent.value >= 67) return 'is-medium'
  return 'is-weak'
})
</script>

<style scoped>
.pwd-strength {
  width: 100%;
  margin-top: 6px;
}

.strength-track {
  height: 4px;
  border-radius: 999px;
  background: #eef2f7;
  overflow: hidden;
}

.strength-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.2s ease, background-color 0.2s ease;
}

.strength-bar.is-weak {
  background: #ef4444;
}

.strength-bar.is-medium {
  background: #f59e0b;
}

.strength-bar.is-strong {
  background: #16a34a;
}

.rule-list {
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rule-list li {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  line-height: 18px;
  color: #94a3b8;
}

.rule-list li.ok {
  color: #16a34a;
}

.rule-list .el-icon {
  font-size: 13px;
}
</style>
