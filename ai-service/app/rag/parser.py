"""多模态文档解析：PDF / DOCX / TXT / MD / 图片，输出结构化块（文本/表格/图片）。"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import List

from app.rag.ocr import image_metadata, ocr_image

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")

_TABLE_SPLIT_RE = re.compile(r"\s{2,}|\t+")


@dataclass
class ParsedBlock:
    page_no: int
    block_type: str  # text | table | image
    content: str
    section: str = ""
    metadata: dict = field(default_factory=dict)


def parse_blocks(file_bytes: bytes, file_name: str) -> List[ParsedBlock]:
    """解析文件为结构化块列表。"""
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        return _parse_pdf_blocks(file_bytes)
    if lower.endswith(".docx"):
        return _parse_docx_blocks(file_bytes)
    if lower.endswith(IMAGE_EXTENSIONS):
        return _parse_image_blocks(file_bytes, file_name)
    if lower.endswith(".txt") or lower.endswith(".md"):
        text = file_bytes.decode("utf-8", errors="ignore")
        return _parse_text_blocks(text, page_no=1)
    # 兜底：按文本处理
    text = file_bytes.decode("utf-8", errors="ignore")
    return _parse_text_blocks(text, page_no=1)


def extract_text(file_bytes: bytes, file_name: str) -> List[tuple[int, str]]:
    """兼容旧接口：返回 [(page_no, text)]（仅文本块）。"""
    pages: dict[int, list[str]] = {}
    for block in parse_blocks(file_bytes, file_name):
        if block.block_type == "text":
            pages.setdefault(block.page_no, []).append(block.content)
    return [(p, "\n".join(parts)) for p, parts in sorted(pages.items())]


# ---------------- PDF ----------------

def _parse_pdf_blocks(file_bytes: bytes) -> List[ParsedBlock]:
    try:
        return _parse_pdf_with_plumber(file_bytes)
    except ImportError:
        logger.info("pdfplumber 未安装，使用 pypdf 文本解析")
    except Exception as e:
        logger.warning("pdfplumber 解析失败，降级 pypdf: %s", e)
    return _parse_pdf_with_pypdf(file_bytes)


def _parse_pdf_with_plumber(file_bytes: bytes) -> List[ParsedBlock]:
    import pdfplumber  # type: ignore

    blocks: List[ParsedBlock] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            tables = _normalize_tables(page.extract_tables() or [])
            for rows in tables:
                blocks.append(ParsedBlock(
                    page_no=i,
                    block_type="table",
                    content=_rows_to_markdown(rows),
                    section=f"第 {i} 页表格",
                    metadata={"rows": len(rows), "cols": max(len(r) for r in rows), "source": "pdfplumber"},
                ))
            if page_text:
                blocks.append(ParsedBlock(page_no=i, block_type="text", content=page_text))
            elif not tables:
                blocks.append(ParsedBlock(
                    page_no=i,
                    block_type="image",
                    content=f"（第 {i} 页为扫描页，未提取到文本）",
                    metadata={"scanned": True, "engine": "none"},
                ))
    logger.info("PDF(pdfplumber) 解析完成: %d 页, %d 块", len(pdf.pages), len(blocks))
    return blocks


def _parse_pdf_with_pypdf(file_bytes: bytes) -> List[ParsedBlock]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(io.BytesIO(file_bytes))
    blocks: List[ParsedBlock] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            blocks.append(ParsedBlock(
                page_no=i,
                block_type="image",
                content=f"（第 {i} 页为扫描页，未提取到文本）",
                metadata={"scanned": True, "engine": "none"},
            ))
            continue
        blocks.extend(_split_ordered(text, page_no=i))
    logger.info("PDF(pypdf) 解析完成: %d 页, %d 块", len(reader.pages), len(blocks))
    return blocks


# ---------------- DOCX / 文本 ----------------

def _parse_docx_blocks(file_bytes: bytes) -> List[ParsedBlock]:
    try:
        from docx import Document  # type: ignore

        doc = Document(io.BytesIO(file_bytes))
        blocks: List[ParsedBlock] = []
        for table in doc.tables:
            rows = _normalize_tables([[cell.text for cell in row.cells] for row in table.rows])
            for r in rows:
                blocks.append(ParsedBlock(
                    page_no=1, block_type="table", content=_rows_to_markdown(r),
                    section="文档表格",
                    metadata={"rows": len(r), "cols": max(len(x) for x in r), "source": "python-docx"},
                ))
        text = "\n".join(p.text for p in doc.paragraphs).strip()
        if text:
            blocks.extend(_split_ordered(text, page_no=1))
        return blocks
    except ImportError:
        logger.warning("python-docx 未安装，docx 按文本兜底")
        return _parse_text_blocks(file_bytes.decode("utf-8", errors="ignore"), page_no=1)


def _parse_text_blocks(text: str, page_no: int) -> List[ParsedBlock]:
    return _split_ordered(text, page_no=page_no)


# ---------------- 图片 ----------------

def _parse_image_blocks(file_bytes: bytes, file_name: str) -> List[ParsedBlock]:
    text, engine = ocr_image(file_bytes, file_name)
    meta = {"engine": engine, **image_metadata(file_bytes)}
    if not text:
        text = f"（图片文件 {file_name}，未识别到文字）"
    return [ParsedBlock(page_no=1, block_type="image", content=text, section=file_name, metadata=meta)]


# ---------------- 表格识别与序列化 ----------------

def _split_ordered(text: str, page_no: int) -> List[ParsedBlock]:
    """按行扫描，将连续表格行归为 table 块，其余归为 text 块。"""
    blocks: List[ParsedBlock] = []
    text_lines: List[str] = []
    table_lines: List[str] = []

    def flush_text():
        if text_lines:
            content = "\n".join(text_lines).strip()
            if content:
                section = _guess_section(text_lines)
                blocks.append(ParsedBlock(page_no=page_no, block_type="text", content=content, section=section))
            text_lines.clear()

    def flush_table():
        if not table_lines:
            return
        rows = _lines_to_rows(table_lines)
        if rows and len(rows) >= 2 and max(len(r) for r in rows) >= 2:
            blocks.append(ParsedBlock(
                page_no=page_no, block_type="table", content=_rows_to_markdown(rows),
                section="表格",
                metadata={"rows": len(rows), "cols": max(len(r) for r in rows), "source": "text-heuristic"},
            ))
        else:
            text_lines.extend(table_lines)
        table_lines.clear()

    for raw in text.split("\n"):
        line = raw.rstrip()
        if _is_table_line(line):
            flush_text()
            table_lines.append(line)
        else:
            flush_table()
            text_lines.append(line)

    flush_table()
    flush_text()
    return blocks


def _is_table_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
        return True
    return len(_TABLE_SPLIT_RE.split(s)) >= 2


def _lines_to_rows(lines: List[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in lines:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
        else:
            cells = [c.strip() for c in _TABLE_SPLIT_RE.split(s) if c.strip()]
        # 跳过 markdown 分隔行（|---|---|）
        if cells and all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if cells:
            rows.append(cells)
    return rows


def _normalize_tables(raw_tables: list) -> list:
    """标准化 pdfplumber/docx 表格，过滤空表与过小表。"""
    result = []
    for table in raw_tables:
        rows = [
            [(cell or "").strip() for cell in row]
            for row in table
            if row and any((cell or "").strip() for cell in row)
        ]
        if len(rows) >= 2 and max(len(r) for r in rows) >= 2:
            result.append(rows)
    return result


def _rows_to_markdown(rows: List[List[str]]) -> str:
    """表格转为 markdown，便于文本检索与展示。"""
    width = max(len(r) for r in rows)
    normalized = [r + [""] * (width - len(r)) for r in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for r in normalized[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _guess_section(lines: List[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) <= 40:
            return stripped
    return ""
