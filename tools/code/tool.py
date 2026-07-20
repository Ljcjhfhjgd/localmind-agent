"""
文件名: tools/code/tool.py
功能: 代码执行工具 - 安全沙箱执行 Python 代码 + 代码模型生成
依赖: tools.base
"""
import ast
import operator
import re
import subprocess
import tempfile
import os
from loguru import logger
from ..base import BaseTool


class CodeTool(BaseTool):
    name = "execute_code"
    description = "执行Python代码，用于计算和数据处理。支持自然语言描述需求。"
    priority = 45
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python代码或自然语言描述"}
        },
        "required": ["code"]
    }

    DANGEROUS = ['rm -rf', 'sudo', 'os.system', 'subprocess', '__import__',
                 'eval(', 'exec(', 'shutil.rmtree', 'import os', 'import subprocess']

    async def execute(self, message: str, ctx: dict = None) -> dict:
        task = ""
        if isinstance(ctx, dict):
            task = ctx.get("code", "")
        elif isinstance(ctx, str):
            task = ctx.strip()

        if not task:
            return {"result": "错误: 没有代码"}

        # 判断是自然语言还是代码
        is_natural = any(kw in task for kw in [
            '计算', '求', '判断', '生成', '写一个', '找出', '列出', '统计',
            '算', '总和', '个数', '有多少', '哪些'
        ])

        if is_natural:
            code = await self._generate_code(task)
            if not code:
                return {"result": "错误: 代码生成失败"}
        else:
            code = task

        # 安全检查
        for d in self.DANGEROUS:
            if d in code:
                return {"result": f"安全限制: 包含禁止的关键词 '{d}'"}

        # 注入 DataFrame（如果有）
        if self.agent and hasattr(self.agent, 'conversation'):
            df = self.agent.conversation.last_df
            if df is not None:
                code = f"import pandas as pd\ndf = pd.DataFrame({df.to_dict()})\n" + code

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                f.flush()

            result = subprocess.run(
                ['python', f.name],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8'
            )
            os.unlink(f.name)

            if result.returncode == 0:
                out = result.stdout.strip()
                return {"result": f"执行成功:\n{out}" if out else "执行成功（无输出）"}
            return {"result": f"执行失败:\n{result.stderr}"}

        except subprocess.TimeoutExpired:
            return {"result": "执行超时（10秒限制）"}
        except Exception as e:
            return {"result": f"执行错误: {e}"}

    async def _generate_code(self, task: str) -> str:
        """用 coder 模型生成代码"""
        prompt = f"""用 Python 生成可执行代码来解决以下问题。只输出代码，不要解释。

        规则：
        - 必须用 print() 输出最终结果
        - for/if 必须换行写
        - 代码简洁高效
        - 不要 markdown 代码块标记
        - 不要使用 input() 或 scanf，所有数据直接在代码中定义
        - 只支持 Python，不执行 C/Java/JavaScript 等其他语言

        问题：{task}

        代码："""

        try:
            resp = await self.agent.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model="qwen2.5-coder:1.5b",
                temperature=0.1,
            )
            code = resp.get("message", {}).get("content", "").strip()
            code = re.sub(r'^```\w*\n?', '', code)
            code = re.sub(r'\n?```$', '', code)
            logger.info(f"[代码生成] {task[:30]} -> {len(code)} 字符")
            return code
        except Exception as e:
            logger.warning(f"[代码生成] 失败: {e}")
            return ""


class CalculateTool(BaseTool):
    name = "calculate"
    description = "执行数学表达式计算"
    priority = 46
    parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，如 '2+3*4'"}
        },
        "required": ["expression"]
    }

    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def _safe_eval(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return self.ALLOWED_OPS[type(node.op)](self._safe_eval(node.left), self._safe_eval(node.right))
        if isinstance(node, ast.UnaryOp):
            return self.ALLOWED_OPS[type(node.op)](self._safe_eval(node.operand))
        raise ValueError("不支持的表达式")

    async def execute(self, message: str, ctx: dict = None) -> dict:
        expr = ctx.get("expression") if ctx else ""
        if not expr:
            return {"result": "错误: 没有表达式"}

        try:
            tree = ast.parse(expr, mode='eval')
            result = self._safe_eval(tree.body)
            return {"result": f"{expr} = {result}"}
        except Exception as e:
            return {"result": f"计算失败: {e}"}