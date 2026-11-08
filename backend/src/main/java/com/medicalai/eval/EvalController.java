package com.medicalai.eval;

import com.fasterxml.jackson.databind.JsonNode;
import com.medicalai.common.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 评测看板接口：返回最新一次评测指标与明细
 */
@RestController
@RequestMapping("/api/eval")
@RequiredArgsConstructor
public class EvalController {

    private final EvalService evalService;

    @GetMapping("/latest")
    public Result<JsonNode> latest() {
        return Result.success(evalService.latest());
    }

    @GetMapping("/items")
    public Result<JsonNode> items(
            @RequestParam(defaultValue = "") String keyword,
            @RequestParam(defaultValue = "") String type,
            @RequestParam(defaultValue = "") String result,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return Result.success(evalService.items(keyword, type, result, page, size));
    }
}
