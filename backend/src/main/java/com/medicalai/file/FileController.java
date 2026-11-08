package com.medicalai.file;

import com.medicalai.common.Result;
import com.medicalai.file.dto.DocumentDTO;
import com.medicalai.file.dto.FileUploadResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 文件接口
 */
@RestController
@RequestMapping("/api/files")
@RequiredArgsConstructor
public class FileController {

    private final FileService fileService;

    /**
     * 上传文件
     */
    @PostMapping("/upload")
    public Result<FileUploadResponse> upload(@RequestParam("file") MultipartFile file) {
        return Result.success(fileService.upload(file));
    }

    /**
     * 文档列表
     */
    @GetMapping
    public Result<List<DocumentDTO>> list() {
        return Result.success(fileService.list());
    }

    /**
     * 文档详情
     */
    @GetMapping("/{id}")
    public Result<DocumentDTO> detail(@PathVariable Long id) {
        return Result.success(fileService.detail(id));
    }

    /**
     * 删除文档
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        fileService.delete(id);
        return Result.success();
    }
}
