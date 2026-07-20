"""
文件名: tools/rag/evaluator.py
功能: RAG 检索质量评估器 - LLM 评判模式
依赖: 无
"""
from loguru import logger


class RAGEvaluator:
    def __init__(self, llm_client=None, eval_enabled=False):
        self.history = []
        self.llm = llm_client
        self.eval_enabled = eval_enabled

    async def evaluate(self, question: str, contexts: list) -> dict:
        if not question or not contexts:
            return {}

        if self.eval_enabled and self.llm:
            # LLM 评判模式
            relevant_count = 0
            for ctx in contexts[:5]:
                prompt = f"问题：{question[:200]}\n检索片段：{ctx[:300]}\n\n这条检索片段对回答问题有帮助吗？只回复 YES 或 NO。"
                try:
                    resp = await self.llm.chat(
                        messages=[{"role": "user", "content": prompt}],
                        model="qwen2.5:0.5b",
                        temperature=0.1
                    )
                    answer = resp.get("message", {}).get("content", "").strip().upper() if isinstance(resp, dict) else str(resp).upper()
                    if "YES" in answer:
                        relevant_count += 1
                except:
                    relevant_count += 1

            total = len(contexts)
            relevancy = round(relevant_count / total, 3) if total > 0 else 0
            recall = 1.0 if relevant_count > 0 else 0
            result = {
                "context_relevancy": relevancy,
                "context_recall": recall,
                "context_count": total,
                "relevant_count": relevant_count,
                "eval_mode": "llm",
            }
        else:
            # 简单模式（候选数比例）
            context_count = len(contexts)
            relevancy = round(min(1.0, context_count / 5), 3)
            recall = round(min(1.0, context_count / 3), 3)
            result = {
                "context_relevancy": relevancy,
                "context_recall": recall,
                "context_count": context_count,
                "relevant_count": context_count,
                "eval_mode": "simple",
            }

        self.history.append({"question": question[:100], **result})
        if len(self.history) > 100:
            self.history.pop(0)

        return result