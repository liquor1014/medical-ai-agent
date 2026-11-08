package com.medicalai.audit;

import com.medicalai.audit.dto.AuditLogDTO;
import com.medicalai.audit.dto.AuditPageDTO;
import com.medicalai.common.TenantContext;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/**
 * 审计查询业务逻辑
 */
@Service
@RequiredArgsConstructor
public class AuditService {

    private static final int MAX_PAGE_SIZE = 50;

    private final AuditRepository auditRepository;

    public AuditPageDTO list(int page, int size, String action, String result) {
        int safePage = Math.max(1, page);
        int safeSize = Math.min(MAX_PAGE_SIZE, Math.max(1, size));
        String tenantId = TenantContext.getTenantId();

        AuditPageDTO dto = new AuditPageDTO();
        dto.setPage(safePage);
        dto.setSize(safeSize);
        dto.setTotal(auditRepository.count(tenantId, action, result));
        dto.setItems(auditRepository.findPage(
                tenantId, action, result, (safePage - 1) * safeSize, safeSize));
        dto.setCounts(auditRepository.countsByResult(tenantId));
        dto.setLast24h(auditRepository.countLast24h(tenantId));
        dto.setActions(auditRepository.distinctActions(tenantId));
        return dto;
    }
}
