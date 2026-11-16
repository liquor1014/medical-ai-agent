package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/**
 * Redis 会话存储：auth:session:{jti} -> username，TTL 与 JWT 一致
 * 同时维护 auth:user-sessions:{username} 集合，便于改密 / 重置密码时批量吊销会话
 * （用户名全局唯一，无需按租户分隔）
 */
@Service
@RequiredArgsConstructor
public class SessionStore {

    private final StringRedisTemplate redis;

    @Value("${app.auth.session.prefix:auth:session:}")
    private String prefix;

    @Value("${app.auth.session.user-prefix:auth:user-sessions:}")
    private String userPrefix;

    public void save(String jti, String tenantId, String username, Duration ttl) {
        redis.opsForValue().set(prefix + jti, username, ttl);
        String userKey = userKey(username);
        redis.opsForSet().add(userKey, jti);
        redis.expire(userKey, ttl);
    }

    public boolean exists(String jti) {
        return Boolean.TRUE.equals(redis.hasKey(prefix + jti));
    }

    public void remove(String jti) {
        redis.delete(prefix + jti);
    }

    /**
     * 吊销某个用户除 keepJti 外的所有会话（修改密码时保留当前登录）
     */
    public void removeOtherSessions(String username, String keepJti) {
        revoke(username, keepJti);
    }

    /**
     * 吊销某个用户的全部会话（重置密码后强制重新登录）
     */
    public void removeAllForUser(String username) {
        revoke(username, null);
    }

    private void revoke(String username, String keepJti) {
        String userKey = userKey(username);
        Set<String> jtis = redis.opsForSet().members(userKey);
        if (jtis == null || jtis.isEmpty()) {
            return;
        }
        List<String> revokeJtis = new ArrayList<>();
        for (String jti : jtis) {
            if (keepJti != null && keepJti.equals(jti)) {
                continue;
            }
            redis.delete(prefix + jti);
            revokeJtis.add(jti);
        }
        if (!revokeJtis.isEmpty()) {
            redis.opsForSet().remove(userKey, revokeJtis.toArray());
        }
    }

    private String userKey(String username) {
        return userPrefix + username;
    }
}
