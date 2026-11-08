package com.medicalai.model;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.medicalai.common.BusinessException;
import com.medicalai.common.Result;
import com.medicalai.common.TenantContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * 模型健康接口：透传 AI 服务的模型配置、调用统计、日志与试调用。
 */
@Slf4j
@RestController
@RequestMapping("/api/models")
@RequiredArgsConstructor
public class ModelController {

    private final ObjectMapper objectMapper;

    @Value("${app.ai-service.base-url:http://localhost:8000}")
    private String aiServiceUrl;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    @GetMapping("/health")
    public Result<JsonNode> health() {
        return Result.success(get("/api/models/health", Duration.ofSeconds(20)));
    }

    @GetMapping("/logs")
    public Result<JsonNode> logs(@RequestParam(defaultValue = "50") int limit) {
        int safeLimit = Math.min(200, Math.max(1, limit));
        return Result.success(get("/api/models/logs?limit=" + safeLimit, Duration.ofSeconds(20)));
    }

    @PostMapping("/switch")
    public Result<JsonNode> switchRoute(@RequestBody JsonNode body) {
        return Result.success(post("/api/models/switch", body, Duration.ofSeconds(20)));
    }

    @PostMapping("/test")
    public Result<JsonNode> test(@RequestBody(required = false) JsonNode body) {
        ObjectNode payload = body != null && body.isObject()
                ? ((ObjectNode) body).deepCopy()
                : objectMapper.createObjectNode();
        payload.put("tenant_id", TenantContext.getTenantId());
        if (!payload.hasNonNull("question")) {
            payload.put("question", "用一句话说明当前使用的是哪个模型");
        }
        if (!payload.hasNonNull("task")) {
            payload.put("task", "chat");
        }
        log.info("模型试调用: task={}, tenant={}", payload.get("task"), TenantContext.getTenantId());
        return Result.success(post("/api/models/test", payload, Duration.ofSeconds(90)));
    }

    private JsonNode get(String path, Duration timeout) {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(aiServiceUrl + path))
                .timeout(timeout)
                .GET()
                .build();
        return execute(request);
    }

    private JsonNode post(String path, JsonNode payload, Duration timeout) {
        String body;
        try {
            body = objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new BusinessException(500, "请求序列化失败");
        }
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(aiServiceUrl + path))
                .header("Content-Type", "application/json; charset=utf-8")
                .timeout(timeout)
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        return execute(request);
    }

    private JsonNode execute(HttpRequest request) {
        try {
            HttpResponse<String> response = httpClient.send(
                    request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200) {
                throw new BusinessException(
                        response.statusCode(), "AI 服务返回错误: " + extractDetail(response.body()));
            }
            return objectMapper.readTree(response.body());
        } catch (IOException e) {
            log.warn("调用 AI 服务失败: {}", e.getMessage());
            throw new BusinessException(502, "AI 服务不可用，请确认 8000 端口服务已启动");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BusinessException(502, "模型服务调用被中断");
        }
    }

    private String extractDetail(String body) {
        try {
            JsonNode node = objectMapper.readTree(body);
            if (node.hasNonNull("detail")) {
                return node.get("detail").asText();
            }
            if (node.hasNonNull("message")) {
                return node.get("message").asText();
            }
        } catch (Exception ignored) {
            // 非 JSON 错误体
        }
        return body == null || body.isBlank() ? "未知错误" : body;
    }
}
