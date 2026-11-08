package com.medicalai.common;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;

/**
 * JWT 签发与校验（HS256）
 */
@Slf4j
@Service
public class JwtTokenService {

    private final SecretKey key;
    private final Duration ttl;

    public JwtTokenService(@Value("${app.auth.jwt.secret}") String secret,
                           @Value("${app.auth.jwt.expire-hours:12}") long expireHours) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.ttl = Duration.ofHours(expireHours);
    }

    public Duration getTtl() {
        return ttl;
    }

    /**
     * 签发 Token，jti 用于关联 Redis 会话
     */
    public String createToken(UserAccount user, String jti) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(user.getUsername())
                .id(jti)
                .claim("tenantId", user.getTenantId())
                .claim("displayName", user.getDisplayName())
                .claim("role", user.getRole())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    /**
     * 校验签名与过期时间，失败返回 null
     */
    public TokenPayload parse(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return new TokenPayload(
                    claims.getSubject(),
                    claims.get("tenantId", String.class),
                    claims.get("displayName", String.class),
                    claims.get("role", String.class),
                    claims.getId(),
                    claims.getExpiration().toInstant());
        } catch (JwtException | IllegalArgumentException e) {
            log.debug("Token 校验失败: {}", e.getMessage());
            return null;
        }
    }

    public record TokenPayload(String username, String tenantId, String displayName,
                               String role, String jti, Instant expiresAt) {
    }
}
