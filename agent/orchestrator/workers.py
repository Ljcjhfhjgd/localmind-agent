"""
文件名: agent/orchestrator/workers.py
功能: 多 Agent 协作 - 子 Agent（搜索/代码/审查/天气/翻译/时间/计算）
依赖: tools.base
"""
import json
import re
from loguru import logger


def _format_context(context: list, max_len: int = 500) -> str:
    """将前置步骤结果格式化为简洁的上下文字符串"""
    if not context:
        return ""
    lines = ["\n## 前置任务已完成\n"]
    for item in context:
        role = item.get("role", "")
        task = item.get("task", "")
        result = item.get("result", "")
        # 截断过长结果
        if len(result) > max_len:
            result = result[:max_len] + "..."
        role_labels = {
            "search": "搜索", "code": "代码", "review": "审查",
            "weather": "天气", "translate": "翻译", "time": "时间",
            "calculate": "计算", "summarizer": "汇总", "planner": "规划"
        }
        label = role_labels.get(role, role)
        lines.append(f"- [{label}] {task}\n  结果: {result}")
        # 传递文件数据给 CodeAgent
        if item.get("file_data"):
            lines.append(f"  文件内容: {item['file_data'][:max_len]}")
    return "\n".join(lines)


class SearchAgent:
    """搜索 Agent：关键词生成 + 搜索 + 信息提取"""

    def __init__(self, llm, search_tool):
        self.llm = llm
        self.search_tool = search_tool

    async def run(self, task: str, context: list = None) -> dict:
        ctx_str = _format_context(context) if context else ""

        keywords_resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"{ctx_str}\n\n为完成以下任务，生成一个百度搜索关键词，只输出关键词：{task}"}],
            temperature=0.1
        )
        keywords = keywords_resp.get("message", {}).get("content", "").strip()
        logger.info(f"[SearchAgent] 关键词: {keywords}")

        raw = await self.search_tool.execute("", {"query": keywords})
        raw_text = raw.get("result", "") if isinstance(raw, dict) else str(raw)

        summary_resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"从以下搜索结果中提取与'{task}'最相关的3条信息：\n{raw_text[:3000]}"}],
            temperature=0.3
        )
        return {
            "role": "search",
            "task": task,
            "keywords": keywords,
            "result": summary_resp.get("message", {}).get("content", ""),
            "status": "ok"
        }


class CodeAgent:
    """代码 Agent：代码生成 + 执行，支持文件数据"""

    def __init__(self, llm, code_tool):
        self.llm = llm
        self.code_tool = code_tool

    async def run(self, task: str, context: list = None) -> dict:
        ctx_str = _format_context(context) if context else ""

        # 从 context 中提取文件数据
        file_data = ""
        if context:
            for item in reversed(context):
                if item.get("file_data"):
                    file_data = item["file_data"]
                    break

        prompt = f"{ctx_str}\n\n用 Python 完成以下任务，只输出代码，不要解释。必须用 print() 输出结果：{task}"
        if file_data:
            prompt += f"\n\n文件数据：{file_data[:2000]}"

        code_resp = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        code = code_resp.get("message", {}).get("content", "").strip()
        code = code.replace("```python", "").replace("```", "").strip()
        logger.info(f"[CodeAgent] 代码长度: {len(code)}")

        result = await self.code_tool.execute("", {"code": code})
        result_text = result.get("result", "") if isinstance(result, dict) else str(result)
        return {
            "role": "code",
            "task": task,
            "code": code,
            "result": result_text,
            "status": "ok"
        }


class ReviewAgent:
    """审查 Agent：质量检查"""

    def __init__(self, llm):
        self.llm = llm

    async def run(self, task: str, context: list = None) -> dict:
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        check_resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"检查以下内容是否准确、完整。如果合格回复'合格'，如果有问题指出具体问题。\n任务：{task}\n内容：{context_str}"}],
            temperature=0.3
        )
        result = check_resp.get("message", {}).get("content", "")
        return {
            "role": "review",
            "task": task,
            "result": result,
            "status": "ok" if "合格" in result else "needs_improvement"
        }


class WeatherAgent:
    """天气 Agent：城市提取 + 查询"""

    def __init__(self, llm, weather_tool):
        self.llm = llm
        self.weather_tool = weather_tool

    async def run(self, task: str, context: list = None) -> dict:
        source = task
        if context:
            for prev in reversed(context):
                prev_result = prev.get("result", "")
                if prev_result and any(c in prev_result for c in ['天气', '温度', '°C']):
                    continue
                if prev.get("role") in ("search", "time"):
                    source = prev.get("result", task) + " " + task
                    break

        city_resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"从以下内容中提取一个城市名，只输出城市名：{source}"}],
            temperature=0.1
        )
        city = city_resp.get("message", {}).get("content", "").strip()
        logger.info(f"[WeatherAgent] 城市: {city}")

        result = await self.weather_tool.execute("", {"city": city})
        return {
            "role": "weather",
            "task": task,
            "city": city,
            "result": result.get("result", "") if isinstance(result, dict) else str(result),
            "status": "ok"
        }


class TranslateAgent:
    """翻译 Agent：从上下文提取待翻译内容 + 翻译"""

    def __init__(self, llm, translate_tool):
        self.llm = llm
        self.translate_tool = translate_tool

    async def run(self, task: str, context: list = None) -> dict:
        source_text = task
        if context:
            for prev in reversed(context):
                prev_result = prev.get("result", "")
                if prev_result and prev.get("role") in ("weather", "search", "time", "calculate", "code"):
                    source_text = prev_result
                    break

        info_resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"从以下内容中提取要翻译的文本和目标语言。输出 JSON：{{\"text\": \"...\", \"target\": \"...\"}}\n任务：{task}\n待翻译内容：{source_text}"}],
            temperature=0.1
        )
        try:
            info = json.loads(info_resp.get("message", {}).get("content", "{}"))
        except json.JSONDecodeError:
            info = {"text": source_text, "target": "英文"}

        result = await self.translate_tool.execute("", info)
        return {
            "role": "translate",
            "task": task,
            "target": info.get("target", "英文"),
            "result": result.get("result", "") if isinstance(result, dict) else str(result),
            "status": "ok"
        }


class TimeAgent:
    """时间 Agent：获取当前时间"""

    def __init__(self, llm, time_tool):
        self.llm = llm
        self.time_tool = time_tool

    async def run(self, task: str, context: list = None) -> dict:
        result = await self.time_tool.execute("", {})
        return {
            "role": "time",
            "task": task,
            "result": result.get("result", "") if isinstance(result, dict) else str(result),
            "status": "ok"
        }


class CalculateAgent:
    """计算 Agent：表达式提取 + 计算"""

    def __init__(self, llm, calculate_tool):
        self.llm = llm
        self.calculate_tool = calculate_tool

    async def run(self, task: str, context: list = None) -> dict:
        source = task
        if context:
            for prev in reversed(context):
                prev_result = prev.get("result", "")
                if prev_result and prev.get("role") in ("search", "time"):
                    source = prev_result + " " + task
                    break

        expr_resp = await self.llm.chat(
            messages=[{"role": "user", "content": f"从以下内容中提取数学表达式，只输出表达式：{source}"}],
            temperature=0.1
        )
        expr = expr_resp.get("message", {}).get("content", "").strip()
        logger.info(f"[CalculateAgent] 表达式: {expr}")

        # 验证表达式只含合法字符
        if not re.match(r'^[\d\s\+\-\*\/\(\)\.\%]+$', expr):
            return {
                "role": "calculate",
                "task": task,
                "expression": expr,
                "result": f"错误: '{expr}' 不是有效的纯数学表达式，请用 code Agent 生成 Python 代码计算",
                "status": "error"
            }

        result = await self.calculate_tool.execute("", {"expression": expr})
        return {
            "role": "calculate",
            "task": task,
            "expression": expr,
            "result": result.get("result", "") if isinstance(result, dict) else str(result),
            "status": "ok"
        }