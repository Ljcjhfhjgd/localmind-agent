"""
文件名: tools/rag/engine.py
功能: RAG 检索引擎 - FAISS + BM25 混合检索 + 去重 + 上下文压缩 + LLM 评判
依赖: faiss-cpu, numpy, httpx, rank_bm25
运行: 需要先 pip install faiss-cpu numpy httpx rank_bm25
"""
import json
import hashlib
import re
import shutil
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import httpx
from rank_bm25 import BM25Okapi
from loguru import logger
from .chunker import TextChunker
from .evaluator import RAGEvaluator


class RAGEngine:
    """RAG 检索引擎"""

    def __init__(self, ollama_url: str = "http://localhost:11434", config: dict = None):
        self.ollama_url = ollama_url
        self.config = config or {}

        rag_cfg = self.config.get("tools", {}).get("rag", {})
        self.embed_model = rag_cfg.get("embed_model", "bge-m3")
        self.chunk_size = rag_cfg.get("chunk_size", 500)
        self.chunk_overlap = rag_cfg.get("chunk_overlap", 50)
        self.summary_model = rag_cfg.get("summary_model", "qwen2.5:3b-instruct")
        self.top_k = rag_cfg.get("top_k", 5)
        self.rerank_top_k = rag_cfg.get("rerank_top_k", 3)

        self.data_path = Path("data/rag_db")
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.chunker = TextChunker(self.chunk_size, self.chunk_overlap)
        eval_enabled = rag_cfg.get("eval_enabled", False)
        self.evaluator = RAGEvaluator(eval_enabled=eval_enabled)
        self._bm25_cache = {}
        self._index_cache = {}

        logger.info(f"RAG 引擎初始化完成: embed={self.embed_model}, chunk={self.chunk_size}")

    # ========== 嵌入 ==========
    async def _get_embedding(self, text: str) -> list:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text[:3000]}
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])

    async def _get_embeddings_batch(self, texts: list) -> np.ndarray:
        embeddings = []
        for text in texts:
            emb = await self._get_embedding(text)
            embeddings.append(emb)
        return np.array(embeddings, dtype=np.float32)

    # ========== 分词 ==========
    def _tokenize(self, text: str) -> list:
        tokens = []
        buf = ""
        for ch in text:
            if ch.isalpha() and ord(ch) < 128:
                buf += ch
            else:
                if buf:
                    tokens.append(buf.lower())
                    buf = ""
                if ch.strip():
                    tokens.append(ch)
        if buf:
            tokens.append(buf.lower())
        return tokens

    def _get_bm25(self, doc_name: str) -> Optional[Tuple]:
        if doc_name in self._bm25_cache:
            return self._bm25_cache[doc_name]

        meta_path = self.data_path / doc_name / "metadata.json"
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            documents = [c["content"] for c in metadata.get("chunks", [])]
            if not documents:
                return None
            tokenized = [self._tokenize(doc) for doc in documents]
            bm25 = BM25Okapi(tokenized)
            self._bm25_cache[doc_name] = (bm25, documents, metadata.get("chunks", []))
            return self._bm25_cache[doc_name]
        except Exception:
            return None

    # ========== 索引管理 ==========
    def _get_or_load_index(self, doc_name: str):
        if doc_name in self._index_cache:
            return self._index_cache[doc_name]

        faiss_path = self.data_path / doc_name / "index.faiss"
        meta_path = self.data_path / doc_name / "metadata.json"

        if not faiss_path.exists() or not meta_path.exists():
            return None

        try:
            import faiss
            index = faiss.read_index(str(faiss_path))
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            self._index_cache[doc_name] = (index, metadata)
            return (index, metadata)
        except Exception:
            return None

    def _get_all_dir_names(self) -> list:
        if not self.data_path.exists():
            return []
        return [d.name for d in self.data_path.iterdir() if d.is_dir() and (d / "metadata.json").exists()]

    # ========== 文档管理 ==========
    def list_collections(self) -> list:
        names = []
        if not self.data_path.exists():
            return names
        for d in self.data_path.iterdir():
            if d.is_dir() and (d / "metadata.json").exists():
                try:
                    with open(d / "metadata.json", 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    names.append(meta.get("display_name", d.name))
                except:
                    names.append(d.name)
        return names

    def delete_collection(self, display_name: str):
        for d in self.data_path.iterdir():
            if d.is_dir() and (d / "metadata.json").exists():
                try:
                    with open(d / "metadata.json", 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    if meta.get("display_name") == display_name:
                        shutil.rmtree(d)
                        self._bm25_cache.pop(d.name, None)
                        self._index_cache.pop(d.name, None)
                        logger.info(f"删除知识库: {display_name}")
                        return
                except:
                    pass

    def _find_duplicate(self, file_hash: str) -> Optional[str]:
        for d in self.data_path.iterdir():
            if d.is_dir() and (d / "metadata.json").exists():
                try:
                    with open(d / "metadata.json", 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    if meta.get("file_hash") == file_hash:
                        return meta.get("display_name", d.name)
                except:
                    pass
        return None

    def _read_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == '.pdf':
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == '.docx':
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        else:
            try:
                return path.read_text(encoding='utf-8')
            except:
                return path.read_text(encoding='gbk')

    # ========== 索引文档 ==========
    async def index_document(self, file_path: str, doc_name: str = None) -> dict:
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "error": "文件不存在"}

            original_name = doc_name or path.stem
            text = self._read_file(path)

            if not text.strip():
                return {"success": False, "error": "文件内容为空"}

            file_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
            dup_name = self._find_duplicate(file_hash)
            if dup_name:
                return {"success": True, "duplicate": True, "message": f"文件已存在: {dup_name}"}

            chunks = self.chunker.split(text, source_name=original_name)
            if not chunks:
                return {"success": False, "error": "分块失败"}

            chunk_texts = [c["content"] for c in chunks]
            embeddings = await self._get_embeddings_batch(chunk_texts)

            import time
            import faiss

            dir_name = f"doc_{int(time.time())}"
            doc_dir = self.data_path / dir_name
            doc_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, doc_dir / "original")

            dimension = embeddings.shape[1]
            index = faiss.IndexFlatIP(dimension)
            faiss.normalize_L2(embeddings)
            index.add(embeddings)
            faiss.write_index(index, str(doc_dir / "index.faiss"))

            metadata = {
                "display_name": original_name,
                "dir_name": dir_name,
                "file_hash": file_hash,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "embedding_dim": dimension,
            }
            with open(doc_dir / "metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            self._bm25_cache.pop(dir_name, None)
            self._index_cache.pop(dir_name, None)

            logger.info(f"索引完成: {original_name}, {len(chunks)} 块")
            return {"success": True, "chunks": len(chunks), "collection": original_name}

        except Exception as e:
            logger.error(f"索引失败: {e}")
            return {"success": False, "error": str(e)}

    # ========== 检索 ==========
    async def get_context(self, query: str, top_k: int = None, selected_docs: list = None) -> dict:
        try:
            k = top_k or self.top_k
            if not query or not query.strip():
                return {"content": "", "relevant": False, "count": 0}

            query_embedding = np.array([await self._get_embedding(query)], dtype=np.float32)
            import faiss
            faiss.normalize_L2(query_embedding)

            all_docs = self._get_all_dir_names()
            if not all_docs:
                return {"content": "", "relevant": False, "count": 0}

            if selected_docs:
                selected_dirs = set()
                for d in all_docs:
                    meta_path = self.data_path / d / "metadata.json"
                    if meta_path.exists():
                        try:
                            with open(meta_path, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                            if meta.get("display_name", d) in selected_docs:
                                selected_dirs.add(d)
                        except:
                            pass
                docs_to_search = list(selected_dirs) if selected_dirs else all_docs
            else:
                docs_to_search = all_docs

            if not docs_to_search:
                return {"content": "请在文件池中选择要检索的文档", "relevant": False, "count": 0}

            merged = {}
            for doc_name in docs_to_search:
                try:
                    loaded = self._get_or_load_index(doc_name)
                    if loaded:
                        index, metadata = loaded
                        chunks = metadata.get("chunks", [])
                        if chunks:
                            search_k = min(k, len(chunks))
                            distances, indices = index.search(query_embedding, search_k)
                            for i, dist in zip(indices[0], distances[0]):
                                if 0 <= i < len(chunks):
                                    chunk = chunks[i]
                                    content = chunk["content"] if isinstance(chunk, dict) else str(chunk)
                                    source = chunk.get("source", doc_name) if isinstance(chunk, dict) else doc_name
                                    if content.strip():
                                        key = content[:100]
                                        score = float(dist)
                                        if key not in merged or score > merged[key]["score"]:
                                            merged[key] = {"content": content, "source": source, "score": score}
                except:
                    pass

                try:
                    bm25_data = self._get_bm25(doc_name)
                    if bm25_data:
                        bm25, documents, chunks = bm25_data
                        tokenized_query = self._tokenize(query)
                        scores = bm25.get_scores(tokenized_query)
                        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
                        for idx, score in ranked[:k]:
                            if score > 0 and idx < len(documents):
                                doc = documents[idx]
                                source = chunks[idx].get("source", doc_name) if idx < len(chunks) and isinstance(chunks[idx], dict) else doc_name
                                if doc.strip():
                                    key = doc[:100]
                                    normalized_score = score / (1.0 + score)
                                    if key not in merged or normalized_score > merged[key]["score"]:
                                        merged[key] = {"content": doc, "source": source, "score": normalized_score}
                except:
                    pass

            if not merged:
                return {"content": "", "relevant": False, "count": 0}

            candidates = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:self.rerank_top_k]

            lines = ["📚 知识库检索结果：\n"]
            for i, item in enumerate(candidates, 1):
                source = item.get("source", "未知")
                content = item["content"].strip()[:500]
                lines.append("---")
                lines.append(f"[来源 {i}: {source}]")
                lines.append(content)
                context_text = "\n".join(lines)
                context_text = re.sub(r'\n{3,}', '\n\n', context_text)
            # LLM 评判检索质量
            eval_result = await self.evaluator.evaluate(query, [c["content"][:300] for c in candidates])
            logger.info(f"检索质量: 相关{eval_result.get('relevant_count',0)}/{eval_result.get('context_count',0)}, 相关性={eval_result.get('context_relevancy',0)}, 召回={eval_result.get('context_recall',0)}")

            logger.info(f"检索完成: {len(candidates)} 条, {len(context_text)} 字")
            return {
                "content": context_text,
                "relevant": True,
                "count": len(candidates)
            }

        except Exception as e:
            logger.error(f"检索失败: {e}")
            return {"content": "", "relevant": False, "count": 0}

    # ========== 上下文压缩 ==========
    async def compress_context(self, context: str, query: str) -> str:
        if len(context) <= 3000:
            return context

        prompt = (
            "将以下检索结果压缩为500字以内的摘要，保留关键事实和数字。\n\n"
            f"检索结果：\n{context[:5000]}\n\n"
            f"用户问题：{query}\n\n"
            "压缩结果："
        )

        try:
            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.post(f"{self.ollama_url}/api/chat", json={
                    "model": self.summary_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 300}
                })
                compressed = resp.json().get("message", {}).get("content", "").strip()
                if compressed:
                    logger.info(f"压缩: {len(context)} → {len(compressed)} 字")
                    return compressed
        except Exception as e:
            logger.warning(f"压缩失败: {e}")
        return context[:3000]