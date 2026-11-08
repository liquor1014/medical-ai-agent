package com.medicalai.report;

import com.medicalai.common.Result;
import com.medicalai.report.dto.ReportDetailDTO;
import com.medicalai.report.dto.ReportSummaryDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 报表接口：列表 / 详情 / CSV 导出
 */
@RestController
@RequestMapping("/api/reports")
@RequiredArgsConstructor
public class ReportController {

    private final ReportService reportService;

    @GetMapping
    public Result<List<ReportSummaryDTO>> list() {
        return Result.success(reportService.list());
    }

    @GetMapping("/{id}")
    public Result<ReportDetailDTO> detail(@PathVariable Long id) {
        return Result.success(reportService.detail(id));
    }

    @GetMapping("/{id}/export")
    public ResponseEntity<byte[]> export(@PathVariable Long id) {
        byte[] content = reportService.exportCsv(id);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=\"report-" + id + ".csv\"")
                .contentType(MediaType.parseMediaType("text/csv;charset=UTF-8"))
                .body(content);
    }
}
