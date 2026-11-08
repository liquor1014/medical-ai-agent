"""分块：文本按大小+重叠切分；表格/图片各自成块并保留类型与元数据。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from app.rag.parser import ParsedBlock

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


@dataclass
class Chunk:
    page_no: int
    section: str
    content: str
    chunk_type: str = "text"
    metadata: dict = field(default_factory=dict)


def chunk_blocks(blocks: List[ParsedBlock],
                 chunk_size: int = CHUNK_SIZE,
                 overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    """结构化块 → Chunk 列表。表格/图片整块保留。"""
    chunks: List[Chunk] = []
    for block in blocks:
        if block.block_type in ("table", "image"):
            content = block.content.strip()
            if content:
                chunks.append(Chunk(
                    page_no=block.page_no,
                    section=block.section,
                    content=content,
                    chunk_type=block.block_type,
                    metadata=block.metadata,
                ))
            continue
        chunks.extend(_chunk_text_block(block, chunk_size, overlap))
    return chunks


def _chunk_text_block(block: ParsedBlock, chunk_size: int, overlap: int) -> List[Chunk]:
    text = block.content
    if not text or not text.strip():
        return []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: List[Chunk] = []
    buffer = ""
    section = block.section
    for para in paragraphs:
        if not section and len(para) < 40:
            section = para
        if len(buffer) + len(para) <= chunk_size:
            buffer = (buffer + "\n" + para).strip()
        else:
            if buffer:
                chunks.append(Chunk(page_no=block.page_no, section=section, content=buffer))
            if overlap > 0 and len(buffer) > overlap:
                buffer = buffer[-overlap:] + "\n" + para
            else:
                buffer = para
    if buffer:
        chunks.append(Chunk(page_no=block.page_no, section=section, content=buffer))
    return chunks


def chunk_text(pages: List[Tuple[int, str]],
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    """兼容旧接口：纯文本页 → Chunk。"""
    blocks = [
        ParsedBlock(page_no=page_no, block_type="text", content=text)
        for page_no, text in pages
    ]
    return chunk_blocks(blocks, chunk_size, overlap)
