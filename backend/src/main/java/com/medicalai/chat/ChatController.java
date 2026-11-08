package com.medicalai.chat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.medicalai.chat.dto.ChatRequest;
import com.medicalai.common.TenantContext;
import com.medicalai.common.UserContext;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * 对话接口：鉴权后透传 AI 服务的 SSE 流
 */
@Slf4j
@RestController
@RequestMapping("/api/chat")
public class ChatController {

    @Value("${app.ai-service.base-url:http://localhost:8000}")
    private String aiServiceUrl;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@Valid @RequestBody ChatRequest req) {
        String tenantId = TenantContext.getTenantId();
        String username = UserContext.getUsername();
        log.info("对话请求: user={}, tenant={}, question={}", username, tenantId, req.getQuestion());

        SseEmitter emitter = new SseEmitter(300_000L); // 5 分钟超时

        Map<String, String> payload = new HashMap<>();
        payload.put("question", req.getQuestion());
        payload.put("tenant_id", tenantId);
        payload.put("session_id", req.getSessionId() == null ? "" : req.getSessionId());

        String body;
        try {
            body = objectMapper.writeValueAsString(payload);
        } catch (Exception e) {
            log.error("JSON 序列化失败", e);
            emitter.completeWithError(e);
            return emitter;
        }
        log.info("发送给 AI 服务的 body: {}", body);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(aiServiceUrl + "/api/chat/stream"))
                .header("Content-Type", "application/json; charset=utf-8")
                .timeout(Duration.ofSeconds(300))
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();

        httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofInputStream())
                .thenAccept(response -> {
                    log.info("AI 服务响应状态: {}", response.statusCode());
                    if (response.statusCode() != 200) {
                        try {
                            String errorBody = new String(response.body().readAllBytes(), StandardCharsets.UTF_8);
                            log.error("AI 服务返回错误: status={}, body={}", response.statusCode(), errorBody);
                            emitter.send(SseEmitter.event().name("error").data(errorBody));
                            emitter.complete();
                        } catch (Exception e) {
                            emitter.completeWithError(e);
                        }
                        return;
                    }
                    try (InputStream is = response.body();
                         BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {

                        String eventName = null;
                        StringBuilder dataBuf = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) {
                            if (line.startsWith("event:")) {
                                eventName = line.substring(6).trim();
                            } else if (line.startsWith("data:")) {
                                if (dataBuf.length() > 0) dataBuf.append("\n");
                                dataBuf.append(line.substring(5).trim());
                            } else if (line.isEmpty()) {
                                // 空行表示一个事件块结束
                                if (dataBuf.length() > 0) {
                                    SseEmitter.SseEventBuilder event = SseEmitter.event().data(dataBuf.toString());
                                    if (eventName != null) {
                                        event.name(eventName);
                                    }
                                    emitter.send(event);
                                    eventName = null;
                                    dataBuf.setLength(0);
                                }
                            }
                        }
                        // 处理最后一个事件块（可能没有尾随空行）
                        if (dataBuf.length() > 0) {
                            SseEmitter.SseEventBuilder event = SseEmitter.event().data(dataBuf.toString());
                            if (eventName != null) {
                                event.name(eventName);
                            }
                            emitter.send(event);
                        }
                        emitter.complete();
                        log.info("SSE 流传输完成");
                    } catch (Exception e) {
                        log.error("SSE 流处理失败", e);
                        emitter.completeWithError(e);
                    }
                })
                .exceptionally(ex -> {
                    log.error("调用 AI 服务失败", ex);
                    emitter.completeWithError(ex);
                    return null;
                });

        return emitter;
    }
}
