import type { PasswordPolicy } from '@/types/api'

export const DEFAULT_PASSWORD_POLICY: PasswordPolicy = {
  minLength: 8,
  maxLength: 64,
  minClasses: 3,
  classes: ['大写字母', '小写字母', '数字', '特殊字符'],
  hint: '长度 8-64 位，至少包含大写字母、小写字母、数字、特殊字符中的 3 类，且不含空格'
}

export interface PasswordCheck {
  length: boolean
  classes: boolean
  noSpace: boolean
  classCount: number
  valid: boolean
}

/**
 * 与后端 PasswordPolicy 保持一致的密码校验
 */
export function evaluatePassword(password: string, policy: PasswordPolicy): PasswordCheck {
  const value = password || ''
  const classCount = [/[A-Z]/, /[a-z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(value)).length
  const length = value.length >= policy.minLength && value.length <= policy.maxLength
  const noSpace = value.length > 0 && !/\s/.test(value)
  const classes = classCount >= policy.minClasses
  return { length, classes, noSpace, classCount, valid: length && classes && noSpace }
}

/**
 * 返回第一条不满足的规则提示，全部满足返回 null
 */
export function passwordErrorMessage(password: string, policy: PasswordPolicy): string | null {
  if (!password) {
    return '请输入密码'
  }
  const check = evaluatePassword(password, policy)
  if (!check.length) {
    return `密码长度需为 ${policy.minLength}-${policy.maxLength} 位`
  }
  if (!check.noSpace) {
    return '密码不能包含空格'
  }
  if (!check.classes) {
    return `密码需包含大写字母、小写字母、数字、特殊字符中的至少 ${policy.minClasses} 类`
  }
  return null
}
