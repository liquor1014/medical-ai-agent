package com.medicalai.file;

import com.medicalai.common.TenantContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

/**
 * 异步解析服务：调用 AI 服务解析文档
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AsyncParseService {

    private final FileRepository fileRepository;

    @Value("${app.ai-service.base-url:http://localhost:8000}")
    private String aiServiceUrl;

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 异步解析文档（@Async 方法必须由 Spring 代理调用，不能在同类内部调用）
     */
    @Async
    public void parseDocumentAsync(Long docId, String objectKey, String tenantId, String docType) {
        // @Async 运行在新线程，TenantContext(ThreadLocal) 不会自动传递，需手动设置
        TenantContext.setTenantId(tenantId);
        try {
            log.info("开始解析文档: docId={}, objectKey={}", docId, objectKey);

            // 先把状态改为 parsing
            fileRepository.updateParseResult(docId, "parsing", 0, 0);

            // 调用 AI 服务 /api/parse
            String url = aiServiceUrl + "/api/parse";
            Map<String, Object> body = Map.of(
                    "doc_id", docId,
                    "object_key", objectKey,
                    "tenant_id", tenantId,
                    "doc_type", docType
            );
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

            @SuppressWarnings("unchecked")
            Map<String, Object> response = restTemplate.postForObject(url, request, Map.class);

            if (response != null) {
                int pageCount = response.get("page_count") != null ? ((Number) response.get("page_count")).intValue() : 0;
                int chunkCount = response.get("chunk_count") != null ? ((Number) response.get("chunk_count")).intValue() : 0;
                fileRepository.updateParseResult(docId, "completed", pageCount, chunkCount);
                log.info("文档解析完成: docId={}, pages={}, chunks={}", docId, pageCount, chunkCount);
            } else {
                fileRepository.updateParseResult(docId, "failed", 0, 0);
            }
        } catch (Exception e) {
            log.error("文档解析失败: docId={}", docId, e);
            try {
                fileRepository.updateParseResult(docId, "failed", 0, 0);
            } catch (Exception ex) {
                log.error("更新解析状态失败", ex);
            }
        } finally {
            TenantContext.clear();
        }
    }
}
