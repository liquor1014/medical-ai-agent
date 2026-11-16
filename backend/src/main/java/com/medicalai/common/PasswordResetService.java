package com.medicalai.common;

import com.medicalai.common.dto.ForgotCodeResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.Duration;
import java.time.LocalDate;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 找回密码：身份校验 -> 邮箱验证码 -> 一次性重置凭证 -> 重置新密码
 * 未配置 SMTP 时自动降级为演示模式（验证码随响应返回并写入日志），便于本地体验
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PasswordResetService {

    private static final String KEY_PREFIX = "auth:reset:";
    private static final int MAX_VERIFY_ATTEMPTS = 5;
    private static final SecureRandom RANDOM = new SecureRandom();

    private final UserRepository userRepository;
    private final StringRedisTemplate redis;
    private final PasswordPolicy passwordPolicy;
    private final PasswordEncoder passwordEncoder;
    private final SessionStore sessionStore;
    private final ObjectProvider<JavaMailSender> mailSenderProvider;

    @Value("${app.tenant.default-tenant:hospital-demo}")
    private String defaultTenant;

    @Value("${app.auth.reset.code-ttl-seconds:300}")
    private long codeTtlSeconds;

    @Value("${app.auth.reset.ticket-ttl-seconds:600}")
    private long ticketTtlSeconds;

    @Value("${app.auth.reset.interval-seconds:60}")
    private long intervalSeconds;

    @Value("${app.auth.reset.daily-limit:10}")
    private int dailyLimit;

    @Value("${spring.mail.host:}")
    private String mailHost;

    @Value("${spring.mail.from:no-reply@medical-ai.local}")
    private String mailFrom;

    /**
     * 发送验证码：校验用户身份（用户名 + 绑定邮箱）后生成 6 位验证码
     */
    public ForgotCodeResponse sendCode(String requestTenantId, String username, String email) {
        String tenantId = resolveTenant(requestTenantId);
        UserAccount user = requireUser(tenantId, username, email);

        String cooldownKey = KEY_PREFIX + "cooldown:" + tenantId + ":" + username;
        if (Boolean.TRUE.equals(redis.hasKey(cooldownKey))) {
            long remain = redis.getExpire(cooldownKey, TimeUnit.SECONDS);
            throw new BusinessException(429, "验证码发送过于频繁，请 " + Math.max(1, remain) + " 秒后再试");
        }

        String dailyKey = KEY_PREFIX + "daily:" + tenantId + ":" + username + ":" + LocalDate.now();
        Long dailyCount = redis.opsForValue().increment(dailyKey);
        if (dailyCount != null && dailyCount == 1) {
            redis.expire(dailyKey, Duration.ofDays(1));
        }
        if (dailyCount != null && dailyCount > dailyLimit) {
            throw new BusinessException(429, "今日验证码发送次数已达上限，请明天再试");
        }

        String code = String.format("%06d", RANDOM.nextInt(1_000_000));
        String codeKey = codeKey(tenantId, username);
        redis.opsForValue().set(codeKey, code, Duration.ofSeconds(codeTtlSeconds));
        redis.delete(verifyAttemptsKey(tenantId, username));
        redis.opsForValue().set(cooldownKey, "1", Duration.ofSeconds(intervalSeconds));

        boolean delivered = sendMail(user.getEmail(), code);
        if (!delivered) {
            log.warn("[DEMO] 未配置 SMTP，找回密码验证码: {} (tenant={}, username={})",
                    code, tenantId, username);
        } else {
            log.info("找回密码验证码已发送: tenant={}, username={}, email={}", tenantId, username, maskEmail(user.getEmail()));
        }
        return new ForgotCodeResponse(delivered, delivered ? null : code, (int) codeTtlSeconds);
    }

    /**
     * 校验验证码，通过后签发一次性重置凭证（resetTicket）
     */
    public String verifyCode(String requestTenantId, String username, String email, String code) {
        String tenantId = resolveTenant(requestTenantId);
        requireUser(tenantId, username, email);

        String codeKey = codeKey(tenantId, username);
        String storedCode = redis.opsForValue().get(codeKey);
        if (storedCode == null) {
            throw new BusinessException(400, "验证码已过期或不存在，请重新获取");
        }

        String attemptKey = verifyAttemptsKey(tenantId, username);
        Long attempts = redis.opsForValue().increment(attemptKey);
        if (attempts != null && attempts == 1) {
            redis.expire(attemptKey, Duration.ofSeconds(codeTtlSeconds));
        }
        if (attempts != null && attempts > MAX_VERIFY_ATTEMPTS) {
            redis.delete(codeKey);
            redis.delete(attemptKey);
            throw new BusinessException(400, "验证码错误次数过多，请重新获取");
        }
        if (!storedCode.equals(code)) {
            throw new BusinessException(400, "验证码错误");
        }

        redis.delete(codeKey);
        redis.delete(attemptKey);
        String ticket = UUID.randomUUID().toString().replace("-", "");
        redis.opsForValue().set(ticketKey(ticket), tenantId + "|" + username,
                Duration.ofSeconds(ticketTtlSeconds));
        return ticket;
    }

    /**
     * 使用重置凭证提交新密码（凭证一次性有效）
     */
    public void resetPassword(String requestTenantId, String username, String ticket, String newPassword) {
        String tenantId = resolveTenant(requestTenantId);
        String ticketKey = ticketKey(ticket);
        String ticketValue = redis.opsForValue().get(ticketKey);
        if (ticketValue == null) {
            throw new BusinessException(400, "重置凭证无效或已过期，请重新获取验证码");
        }
        if (!ticketValue.equals(tenantId + "|" + username)) {
            throw new BusinessException(400, "重置凭证与账号不匹配，请重新获取验证码");
        }

        passwordPolicy.validate(newPassword);
        UserAccount user = userRepository.findByUsername(username);
        if (user == null) {
            throw new BusinessException(404, "账号不存在");
        }
        if (passwordEncoder.matches(newPassword, user.getPasswordHash())) {
            throw new BusinessException(400, "新密码不能与原密码相同");
        }

        userRepository.updatePassword(username, passwordEncoder.encode(newPassword));
        userRepository.clearLoginState(username);
        sessionStore.removeAllForUser(username);
        redis.delete(ticketKey);
        log.info("用户重置密码成功: {}/{}", tenantId, username);
    }

    private UserAccount requireUser(String tenantId, String username, String email) {
        UserAccount user = userRepository.findByUsername(username);
        // 统一提示，避免通过找回密码接口枚举账号
        if (user == null || user.getEmail() == null || user.getEmail().isBlank()
                || !user.getEmail().equalsIgnoreCase(email.trim())) {
            throw new BusinessException(400, "用户名与邮箱不匹配，请确认账号信息");
        }
        if (!"active".equalsIgnoreCase(user.getStatus())) {
            throw new BusinessException(403, "账号已被禁用，请联系管理员");
        }
        return user;
    }

    private boolean sendMail(String to, String code) {
        if (mailHost == null || mailHost.isBlank()) {
            return false;
        }
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        if (sender == null) {
            return false;
        }
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(mailFrom);
            message.setTo(to);
            message.setSubject("【医疗 AI Agent】密码重置验证码");
            message.setText("您正在重置账号密码，验证码：" + code + "\n\n"
                    + "验证码 " + (codeTtlSeconds / 60) + " 分钟内有效，请勿泄露给他人。\n"
                    + "如非本人操作，请忽略本邮件。");
            sender.send(message);
            return true;
        } catch (Exception e) {
            log.error("验证码邮件发送失败: to={}, error={}", maskEmail(to), e.getMessage());
            throw new BusinessException(500, "验证码邮件发送失败，请稍后重试");
        }
    }

    private String resolveTenant(String requestTenantId) {
        if (requestTenantId != null && !requestTenantId.isBlank()) {
            return requestTenantId.trim();
        }
        String tenantId = TenantContext.getTenantId();
        return (tenantId == null || tenantId.isBlank()) ? defaultTenant : tenantId;
    }

    private String codeKey(String tenantId, String username) {
        return KEY_PREFIX + "code:" + tenantId + ":" + username;
    }

    private String verifyAttemptsKey(String tenantId, String username) {
        return KEY_PREFIX + "verify:" + tenantId + ":" + username;
    }

    private String ticketKey(String ticket) {
        return KEY_PREFIX + "ticket:" + ticket;
    }

    private String maskEmail(String email) {
        if (email == null || !email.contains("@")) {
            return email;
        }
        int at = email.indexOf('@');
        String name = email.substring(0, at);
        String masked = name.length() <= 2 ? name.charAt(0) + "*" : name.charAt(0) + "***" + name.charAt(name.length() - 1);
        return masked + email.substring(at);
    }
}
