package com.medicalai.eval;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.medicalai.common.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 评测结果读取：直接返回 ai-service 评测脚本生成的 JSON 结果
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EvalService {

    private final ObjectMapper objectMapper;

    @Value("${app.eval.result-file:../data/eval/eval_results_v1.json}")
    private String resultFile;

    public JsonNode latest() {
        Path path = resolveResultFile();
        try {
            return objectMapper.readTree(Files.readString(path, StandardCharsets.UTF_8));
        } catch (IOException e) {
            log.error("评测结果读取失败: {}", path, e);
            throw new BusinessException(500, "评测结果读取失败");
        }
    }

    /**
     * 服务端检索评测用例：支持关键词、类型、结果筛选与服务端分页
     */
    public ObjectNode items(String keyword, String type, String result, int page, int size) {
        JsonNode report = latest();
        JsonNode rawItems = report.path("items");

        String key = keyword == null ? "" : keyword.trim().toLowerCase(Locale.ROOT);
        String safeType = type == null ? "" : type.trim();
        String safeResult = result == null ? "" : result.trim();

        List<JsonNode> matched = new ArrayList<>();
        if (rawItems.isArray()) {
            for (JsonNode item : rawItems) {
                if (!safeType.isEmpty() && !safeType.equals(item.path("type").asText(""))) {
                    continue;
                }
                boolean passed = item.path("passed").asBoolean(false);
                if ("passed".equals(safeResult) && !passed) {
                    continue;
                }
                if ("failed".equals(safeResult) && passed) {
                    continue;
                }
                if (!key.isEmpty()
                        && !item.path("question").asText("").toLowerCase(Locale.ROOT).contains(key)) {
                    continue;
                }
                matched.add(item);
            }
        }

        int safeSize = Math.min(100, Math.max(1, size));
        int safePage = Math.max(1, page);
        int from = Math.min(matched.size(), (safePage - 1) * safeSize);
        int to = Math.min(matched.size(), from + safeSize);

        ObjectNode out = objectMapper.createObjectNode();
        ArrayNode arr = out.putArray("items");
        matched.subList(from, to).forEach(arr::add);
        out.put("total", matched.size());
        out.put("page", safePage);
        out.put("size", safeSize);
        out.put("keyword", key);
        out.put("type", safeType);
        out.put("result", safeResult);
        return out;
    }

    /**
     * 兼容从仓库根目录或 backend 目录启动的情况
     */
    private Path resolveResultFile() {
        List<String> candidates = List.of(
                resultFile,
                "../data/eval/eval_results_v1.json",
                "data/eval/eval_results_v1.json",
                "medical-ai-agent/data/eval/eval_results_v1.json");
        for (String candidate : candidates) {
            Path path = Path.of(candidate).toAbsolutePath().normalize();
            if (Files.exists(path)) {
                return path;
            }
        }
        throw new BusinessException(404, "暂无评测结果，请先运行 ai-service 的评测脚本");
    }
}
