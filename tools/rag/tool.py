"""
文件名: tools/rag/tool.py
功能: RAG 知识库检索工具 - 实现 BaseTool 接口
依赖: tools.base, tools.rag.engine
"""
from loguru import logger
from ..base import BaseTool
from .engine import RAGEngine


class RAGTool(BaseTool):
    name = "rag_search"
    description = "搜索本地知识库，获取相关文档内容"
    priority = 30
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询"}
        },
        "required": ["query"]
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.engine = None

    def on_mount(self, agent):
        super().on_mount(agent)
        self.engine = RAGEngine(
            ollama_url=agent.llm.base_url if agent else "http://localhost:11434",
            config=self.config,
        )
        # 注入 LLM 客户端给评估器
        if self.engine and agent:
            self.engine.evaluator.llm = agent.llm

    def can_handle(self, message: str, ctx: dict = None) -> bool:
        if not self.enabled or not ctx:
            return False
        if ctx.get("has_file"):
            return False
        if ctx.get("selected_docs"):
            return True
        return ctx.get("knowledge_mode", False)

    async def execute(self, message: str, ctx: dict = None) -> dict:
        try:
            selected_docs = (ctx or {}).get("selected_docs", []) if ctx else []
            rewritten_query = await self._rewrite_query(message)
            result = await self.engine.get_context(rewritten_query, selected_docs=selected_docs)

            if result and result.get("content"):
                content = result["content"]
                if len(content) > 3000:
                    content = await self.engine.compress_context(content, rewritten_query)
                return {"result": content}

            return {"result": "知识库中没有找到相关内容"}

        except Exception as e:
            logger.error(f"RAG 执行失败: {e}")
            return {"result": f"检索失败: {e}"}

    async def _rewrite_query(self, message: str) -> str:
        if not self.agent:
            return message

        try:
            recent = self.agent.conversation.get_recent_messages(6)
            history = "\n".join(
                f"{'用户' if m['role'] == 'user' else '助手'}: {str(m['content'])[:200]}"
                for m in recent
            )

            prompt = self.agent.prompts.get("query_rewrite", "")
            if not prompt:
                return message
            prompt = prompt.format(history=history, question=message)

            resp = await self.agent.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model="qwen2.5:3b-instruct"
            )
            rewritten = resp.get("content", "").strip()

            if rewritten and len(rewritten) > 2:
                logger.info(f"查询改写: '{message[:30]}' → '{rewritten[:50]}'")
                return rewritten
        except Exception as e:
            logger.debug(f"查询改写失败: {e}")

        return message