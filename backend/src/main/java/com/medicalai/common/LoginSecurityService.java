package com.medicalai.common;

import com.medicalai.audit.AuditRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;

/**
 * 登录安全：失败计数、临时锁定、锁定安全提醒
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LoginSecurityService {

    private final UserRepository userRepository;
    private final AuditRepository auditRepository;

    @Value("${app.auth.login.max-failures:5}")
    private int maxFailures;

    @Value("${app.auth.login.lock-minutes:15}")
    private long lockMinutes;

    /**
     * 登录前检查锁定状态；锁定已过期则自动解锁
     */
    public void assertNotLocked(UserAccount user) {
        OffsetDateTime lockedUntil = user.getLockedUntil();
        if (lockedUntil == null) {
            return;
        }
        if (lockedUntil.isAfter(OffsetDateTime.now())) {
            long remainMinutes = Math.max(1, ChronoUnit.MINUTES.between(OffsetDateTime.now(), lockedUntil));
            throw new BusinessException(423, "账号已锁定，请在 " + remainMinutes + " 分钟后重试，或联系管理员解锁");
        }
        userRepository.clearExpiredLock(user.getUsername());
        user.setFailedAttempts(0);
        user.setLockedUntil(null);
    }

    /**
     * 记录一次登录失败：达到阈值则锁定账号并记录安全提醒
     */
    public void recordFailure(UserAccount user) {
        int attempts = userRepository.incrementFailedAttempts(user.getUsername());
        int remaining = maxFailures - attempts;
        if (remaining <= 0) {
            OffsetDateTime lockedUntil = OffsetDateTime.now().plusMinutes(lockMinutes);
            userRepository.lockAccount(user.getUsername(), lockedUntil);
            String message = "连续登录失败 " + attempts + " 次，账号已锁定 " + lockMinutes + " 分钟";
            log.warn("[SECURITY_ALERT] {} | username={}, lockedUntil={}",
                    message, user.getUsername(), lockedUntil);
            try {
                auditRepository.insertSecurityEvent(user.getTenantId(), user.getId(),
                        "LOGIN_LOCKED", "locked");
            } catch (Exception e) {
                log.warn("写入锁定审计日志失败: {}", e.getMessage());
            }
            throw new BusinessException(423, message);
        }
        throw new BusinessException(401, "用户名或密码错误，还可尝试 " + remaining + " 次");
    }

    /**
     * 登录成功：清空失败计数与锁定状态
     */
    public void recordSuccess(UserAccount user) {
        userRepository.markLoginSuccess(user.getUsername());
    }

    public int getMaxFailures() {
        return maxFailures;
    }

    public long getLockMinutes() {
        return lockMinutes;
    }
}
