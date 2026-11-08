package com.medicalai.audit.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 审计日志分页结果
 */
@Data
public class AuditPageDTO {

    private List<AuditLogDTO> items;
    private long total;
    private int page;
    private int size;

    /** 按结果分类的计数，如 success / rejected */
    private Map<String, Long> counts;

    /** 近 24 小时记录数 */
    private long last24h;

    /** 当前租户出现过的动作类型，用于筛选 */
    private List<String> actions;
}
