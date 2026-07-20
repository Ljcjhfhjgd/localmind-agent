"""
文件名: agent/orchestrator/master.py
功能: 多 Agent 协作 - 主 Agent（任务规划 + 调度 + 汇总）
依赖: agent.orchestrator.workers
"""
import json
from pathlib import Path
from loguru import logger


class MasterAgent:
    """主 Agent：任务规划 + 子 Agent 调度 + 结果汇总"""

    def __init__(self, llm, workers: dict, max_rounds: int = 3):
        self.llm = llm
        self.workers = workers
        self.max_rounds = max_rounds
        self.prompts_dir = Path("agent/prompts/templates")

    def _load_prompt(self, name: str) -> str:
        path = self.prompts_dir / f"{name}.txt"
        if path.exists():
            return path.read_text(encoding='utf-8')
        return ""

    async def run(self, user_message: str) -> tuple:
        """执行完整的多 Agent 协作流程，返回 (答案, 步骤列表)"""
        plan = await self._plan(user_message)
        logger.info(f"[MasterAgent] 计划: {json.dumps(plan, ensure_ascii=False)}")

        if not plan:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": user_message}],
                temperature=0.7
            )
            return resp.get("message", {}).get("content", ""), []

        results = await self._execute(plan)

        for round_num in range(self.max_rounds):
            failed = [r for r in results if r.get("status") not in ("ok", "needs_improvement")]
            if not failed:
                logger.info(f"[MasterAgent] 所有任务完成")
                break
            logger.info(f"[MasterAgent] 第{round_num + 1}轮重试，失败任务: {len(failed)}")
            retry_results = await self._execute(failed)
            results = self._merge(results, retry_results)

        answer = await self._summarize(user_message, results)
        return answer, results

    async def _plan(self, user_message: str, file_context: str = None) -> list:
        """将用户目标拆解为子任务列表"""
        template = self._load_prompt("agent_planner")
        if not template:
            return [{"role": "search", "task": user_message}]

        # 如果有文件上下文，拼入用户消息
        full_message = user_message
        if file_context:
            full_message = f"用户问题：{user_message}\n{file_context}"

        prompt = template.format(
            worker_names=list(self.workers.keys()),
            user_message=full_message
        )

        for attempt in range(3):
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            content = resp.get("message", {}).get("content", "").strip()
            content = content.replace("```json", "").replace("```", "").strip()

            try:
                plan = json.loads(content)
                if isinstance(plan, list):
                    if len(plan) == 0:
                        return []
                    plan = [
                        {"role": s, "task": user_message} if isinstance(s, str) else s
                        for s in plan
                    ]
                    logger.info(f"[MasterAgent] 计划: {json.dumps(plan, ensure_ascii=False)}")
                    return plan
            except json.JSONDecodeError:
                logger.warning(f"[MasterAgent] 计划解析失败(第{attempt+1}次): {content[:100]}")

        return [{"role": "search", "task": user_message}]

    async def _execute(self, plan: list) -> list:
        """执行子任务列表"""
        results = []
        for step in plan:
            role = step.get("role", "search")
            task = step.get("task", "")
            worker = self.workers.get(role)
            if worker:
                try:
                    result = await worker.run(task, context=results)
                    results.append(result)
                    logger.info(f"[MasterAgent] {role} 完成: {str(result.get('result', ''))[:80]}")
                except Exception as e:
                    logger.error(f"[MasterAgent] {role} 失败: {e}")
                    results.append({"role": role, "task": task, "result": str(e), "status": "error"})
            else:
                logger.warning(f"[MasterAgent] 未知角色: {role}")
        return results

    def _merge(self, original: list, retry: list) -> list:
        """将重试结果合并回原始结果列表"""
        merged = []
        retry_idx = 0
        for r in original:
            if r.get("status") not in ("ok", "needs_improvement") and retry_idx < len(retry):
                merged.append(retry[retry_idx])
                retry_idx += 1
            else:
                merged.append(r)
        return merged

    async def _summarize(self, question: str, results: list) -> str:
        """汇总所有子任务结果，生成最终回答"""
        template = self._load_prompt("agent_summarizer")
        results_text = json.dumps(results, ensure_ascii=False)

        if template:
            prompt = template.format(question=question, results_text=results_text)
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
        else:
            resp = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个 AI 助手，根据给定的信息回答用户问题。直接给出完整答案。"},
                    {"role": "user", "content": f"问题：{question}\n\n参考资料：{results_text}"}
                ],
                temperature=0.5,
            )
        return resp.get("message", {}).get("content", "")