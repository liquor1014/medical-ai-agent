package com.medicalai.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 密码复杂度策略：长度 + 字符组合（注册、修改密码、重置密码统一校验）
 * 阈值可通过 app.auth.password.* 配置，前端通过 /api/auth/password/policy 获取同一份规则
 */
@Slf4j
@Component
public class PasswordPolicy {

    @Value("${app.auth.password.min-length:8}")
    private int minLength;

    @Value("${app.auth.password.max-length:64}")
    private int maxLength;

    @Value("${app.auth.password.min-classes:3}")
    private int minClasses;

    /**
     * 校验密码，不满足时抛出 400 业务异常（提示语可直接展示给用户）
     */
    public void validate(String password) {
        if (password == null || password.isBlank()) {
            throw new BusinessException(400, "密码不能为空");
        }
        if (password.length() < minLength || password.length() > maxLength) {
            throw new BusinessException(400, "密码长度需为 " + minLength + "-" + maxLength + " 位");
        }
        if (password.chars().anyMatch(Character::isWhitespace)) {
            throw new BusinessException(400, "密码不能包含空格");
        }
        int classes = countClasses(password);
        if (classes < minClasses) {
            throw new BusinessException(400, String.format(
                    "密码需包含大写字母、小写字母、数字、特殊字符中的至少 %d 类", minClasses));
        }
    }

    /**
     * 返回给前端的规则描述（用于实时提示，避免前后端规则不一致）
     */
    public Map<String, Object> describe() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("minLength", minLength);
        map.put("maxLength", maxLength);
        map.put("minClasses", minClasses);
        map.put("classes", new String[]{"大写字母", "小写字母", "数字", "特殊字符"});
        map.put("hint", "长度 " + minLength + "-" + maxLength + " 位，至少包含大写字母、小写字母、数字、特殊字符中的 "
                + minClasses + " 类，且不含空格");
        return map;
    }

    public int getMinLength() {
        return minLength;
    }

    public int getMaxLength() {
        return maxLength;
    }

    public int getMinClasses() {
        return minClasses;
    }

    /**
     * 统计密码命中的字符类别数（大写 / 小写 / 数字 / 特殊字符）
     */
    public int countClasses(String password) {
        boolean upper = false;
        boolean lower = false;
        boolean digit = false;
        boolean special = false;
        for (char c : password.toCharArray()) {
            if (Character.isUpperCase(c)) {
                upper = true;
            } else if (Character.isLowerCase(c)) {
                lower = true;
            } else if (Character.isDigit(c)) {
                digit = true;
            } else {
                special = true;
            }
        }
        return (upper ? 1 : 0) + (lower ? 1 : 0) + (digit ? 1 : 0) + (special ? 1 : 0);
    }
}
