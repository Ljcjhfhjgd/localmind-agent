"""
文件名: tools/rag/chunker.py
功能: 文档语义分块器 - 按段落和标题智能切分文档
依赖: 无
"""
import re
from typing import List


class TextChunker:
    """文档语义分块器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str, source_name: str = "") -> List[dict]:
        """将文本切分为语义块"""
        if not text or not text.strip():
            return []

        lines = text.split('\n')
        chunks = []
        current = ""
        current_section = ""

        for line in lines:
            # 检测标题
            if re.match(r'^#{1,4}\s', line):
                if current.strip():
                    chunks.append(current.strip())
                    current = ""
                current_section = line.strip('#').strip()
                continue

            # 空行处理
            if not line.strip() and current:
                if len(current) > self.chunk_size * 0.8:
                    chunks.append(current.strip())
                    current = ""
                else:
                    current += "\n"
                continue

            current += line + "\n"

            # 达到 chunk_size 就切
            if len(current) >= self.chunk_size:
                chunks.append(current.strip())
                # 保留重叠部分
                overlap = current[-self.chunk_overlap:] if len(current) > self.chunk_overlap else ""
                current = overlap

        if current.strip():
            chunks.append(current.strip())

        # 合并短块
        merged = self._merge_short_chunks(chunks)

        result = []
        for i, chunk in enumerate(merged):
            source = source_name
            if current_section:
                source += f" # {current_section}"
            result.append({
                "content": chunk,
                "source": source,
                "chunk_index": i,
            })

        return result

    def _merge_short_chunks(self, chunks: List[str]) -> List[str]:
        """合并过短的块"""
        merged = []
        buffer = ""
        for chunk in chunks:
            if len(buffer) + len(chunk) <= self.chunk_size:
                buffer += ("\n\n" + chunk) if buffer else chunk
            else:
                if buffer:
                    merged.append(buffer)
                buffer = chunk
        if buffer:
            merged.append(buffer)
        return merged if merged else [chunks[0]] if chunks else []