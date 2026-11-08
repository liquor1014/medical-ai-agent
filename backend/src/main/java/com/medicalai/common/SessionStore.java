package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;

/**
 * Redis 会话存储：auth:session:{jti} -> username，TTL 与 JWT 一致
 */
@Service
@RequiredArgsConstructor
public class SessionStore {

    private final StringRedisTemplate redis;

    @Value("${app.auth.session.prefix:auth:session:}")
    private String prefix;

    public void save(String jti, String username, Duration ttl) {
        redis.opsForValue().set(prefix + jti, username, ttl);
    }

    public boolean exists(String jti) {
        return Boolean.TRUE.equals(redis.hasKey(prefix + jti));
    }

    public void remove(String jti) {
        redis.delete(prefix + jti);
    }
}
