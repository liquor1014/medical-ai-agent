package com.medicalai.file;

import com.medicalai.common.BusinessException;
import com.medicalai.common.TenantContext;
import com.medicalai.file.dto.DocumentDTO;
import com.medicalai.file.dto.FileUploadResponse;
import com.medicalai.file.entity.Document;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.UUID;

/**
 * 文件服务：上传到 MinIO + 元数据入库 + 触发异步解析
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FileService {

    private final MinioClient minioClient;
    private final FileRepository fileRepository;
    private final AsyncParseService asyncParseService;

    @Value("${app.minio.bucket:medical-docs}")
    private String bucket;

    /**
     * 上传文件
     */
    public FileUploadResponse upload(MultipartFile file) {
        String tenantId = TenantContext.getTenantId();
        String originalName = file.getOriginalFilename();
        if (originalName == null) {
            originalName = "unknown";
        }

        // 生成 object key: {tenantId}/{uuid}_{filename}
        String objectKey = tenantId + "/" + UUID.randomUUID().toString().replace("-", "") + "_" + originalName;

        // 推断文档类型
        String docType = detectDocType(originalName);

        try {
            // 上传到 MinIO
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(bucket)
                    .object(objectKey)
                    .stream(file.getInputStream(), file.getSize(), -1)
                    .contentType(file.getContentType())
                    .build());
            log.info("文件已上传到 MinIO: bucket={}, object={}", bucket, objectKey);
        } catch (Exception e) {
            log.error("MinIO 上传失败", e);
            throw new BusinessException("文件上传失败: " + e.getMessage());
        }

        // 入库
        Document doc = new Document();
        doc.setTenantId(tenantId);
        doc.setFileName(originalName);
        doc.setObjectKey(objectKey);
        doc.setDocType(docType);
        Long docId = fileRepository.insert(doc);
        log.info("文档元数据已入库: id={}, file={}", docId, originalName);

        // 异步触发解析
        asyncParseService.parseDocumentAsync(docId, objectKey, tenantId, docType);

        return new FileUploadResponse(docId, originalName, "pending");
    }

    /**
     * 文档列表
     */
    public List<DocumentDTO> list() {
        return fileRepository.listByTenant(TenantContext.getTenantId()).stream()
                .map(this::toDTO)
                .toList();
    }

    /**
     * 文档详情
     */
    public DocumentDTO detail(Long id) {
        Document doc = fileRepository.findById(id, TenantContext.getTenantId());
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }
        return toDTO(doc);
    }

    /**
     * 删除文档（MinIO + DB）
     */
    public void delete(Long id) {
        String tenantId = TenantContext.getTenantId();
        Document doc = fileRepository.findById(id, tenantId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }
        try {
            minioClient.removeObject(RemoveObjectArgs.builder()
                    .bucket(bucket)
                    .object(doc.getObjectKey())
                    .build());
        } catch (Exception e) {
            log.warn("MinIO 删除对象失败（忽略）: {}", doc.getObjectKey(), e);
        }
        fileRepository.deleteById(id, tenantId);
        log.info("文档已删除: id={}", id);
    }

    private String detectDocType(String filename) {
        String lower = filename.toLowerCase();
        if (lower.endsWith(".pdf")) return "pdf";
        if (lower.endsWith(".docx") || lower.endsWith(".doc")) return "docx";
        if (lower.endsWith(".txt")) return "txt";
        if (lower.endsWith(".md")) return "md";
        if (lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg")
                || lower.endsWith(".bmp") || lower.endsWith(".tif") || lower.endsWith(".tiff")
                || lower.endsWith(".webp")) {
            return "image";
        }
        return "unknown";
    }

    private DocumentDTO toDTO(Document d) {
        DocumentDTO dto = new DocumentDTO();
        dto.setId(d.getId());
        dto.setTenantId(d.getTenantId());
        dto.setFileName(d.getFileName());
        dto.setObjectKey(d.getObjectKey());
        dto.setDocType(d.getDocType());
        dto.setStatus(d.getStatus());
        dto.setPageCount(d.getPageCount());
        dto.setChunkCount(d.getChunkCount());
        dto.setCreatedAt(d.getCreatedAt());
        return dto;
    }
}
