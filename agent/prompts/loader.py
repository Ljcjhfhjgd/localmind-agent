"""
文件名: agent/prompts/loader.py
功能: 提示词加载器 - 从文件加载提示词模板
依赖: pathlib
"""
from pathlib import Path


class PromptLoader:
    """提示词加载器"""

    def __init__(self, prompt_dir: str = None):
        if prompt_dir is None:
            prompt_dir = Path(__file__).parent / "templates"
        self.dir = Path(prompt_dir)
        self._cache = {}

    def get(self, name: str) -> str:
        """获取提示词内容"""
        if name in self._cache:
            return self._cache[name]

        # 尝试 .txt
        path = self.dir / f"{name}.txt"
        if path.exists():
            content = path.read_text(encoding='utf-8')
            self._cache[name] = content
            return content

        return ""

    def get_all(self) -> dict:
        """获取所有提示词"""
        result = {}
        for f in self.dir.glob("*.txt"):
            name = f.stem
            result[name] = self.get(name)
        return result