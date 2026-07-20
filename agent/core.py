"""
文件名: agent/core.py
功能: LocalMindAgent 主类
"""
import json
import base64
import uuid
import re
import io
import asyncio
from pathlib import Path
from datetime import datetime
from typing import AsyncGenerator, Optional
import numpy as np
import yaml
import httpx
from PIL import Image as PILImage
from loguru import logger

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms
from torchvision.models import resnet50

from llm import LLMClient, StreamHandler
from tools import create_default_registry
from tools.registry import ToolRegistry
from .conversation import Conversation
from .prompts import PromptLoader


class LocalMindAgent:
    """LocalMind Agent 主类"""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.llm = LLMClient(self.config)
        self.stream = StreamHandler(self.config)

        mode_models = self.config.get("ollama", {}).get("mode_models", {})
        self.mode_models = mode_models
        self.current_mode = "normal"
        self.model = mode_models.get("default", "qwen2.5:7b-instruct")
        self.vision_model = mode_models.get("vision", "minicpm-v:latest")
        self.xray_judge_model = mode_models.get("xray_judge", "llava:7b")
        self.title_model = mode_models.get("title", "qwen2.5:3b-instruct")

        xray_cfg = self.config.get("xray", {})
        self.ood_stats_path = Path(xray_cfg.get("ood_stats_path", "tools/xray/xray_models/contrastive_ood_stats.json"))
        self.ood_model_path = Path(xray_cfg.get("ood_model_path", "tools/xray/xray_models/best_model.pth"))

        self.conversation = Conversation()
        self._title_generated = False

        self.prompts = PromptLoader()

        self.tools: ToolRegistry = create_default_registry(self.config)
        self._mount_all_tools()

        settings_path = Path("data/settings.json")
        if settings_path.exists():
            try:
                user_settings = json.loads(settings_path.read_text(encoding='utf-8'))
                if user_settings.get("email", {}).get("senderEmail"):
                    self.config.setdefault("email", {})["sender_email"] = user_settings["email"]["senderEmail"]
                if user_settings.get("email", {}).get("authCode"):
                    self.config.setdefault("email", {})["auth_code"] = user_settings["email"]["authCode"]
                if user_settings.get("tools"):
                    for tool_name, enabled in user_settings["tools"].items():
                        self.config.setdefault("tools", {}).setdefault(tool_name, {})["enabled"] = enabled
                logger.info("已加载用户设置覆盖")
            except Exception as e:
                logger.warning(f"加载用户设置失败: {e}")

        self._apply_mode_tools("normal")

        self._is_cancelled = False
        self._xray_results_cache = None

        logger.info(f"LocalMindAgent 初始化完成, 模式: {self.current_mode}, 模型: {self.model}")

    def _mount_all_tools(self):
        for tool in self.tools.get_all():
            tool.on_mount(self)

    def _apply_mode_tools(self, mode: str):
        mode_tools = {
            "normal": [],
            "agent": ["web_search", "execute_code", "calculate", "get_current_time","get_weather", "translate", "summarize_url"],
            "rag": ["rag_search"],
            "xray": ["xray_diagnose"],
            "email": ["send_email"],
        }
        allowed_tools = mode_tools.get(mode, [])
        if mode == "normal":
            for tool in self.tools.get_all():
                tool.enabled = True
        else:
            for tool in self.tools.get_all():
                tool.enabled = False
            for tool_name in allowed_tools:
                tool = self.tools.get(tool_name)
                if tool:
                    tool.enabled = True
        memory_tools = ["remember", "recall"]
        for tool_name in memory_tools:
            tool = self.tools.get(tool_name)
            if tool:
                tool.enabled = (mode == "normal")
        enabled_tools = [t.name for t in self.tools.get_enabled()]
        logger.info(f"模式 [{mode}] 启用工具: {enabled_tools}")

    def switch_mode(self, mode: str) -> dict:
        if mode not in self.mode_models:
            return {"status": "error", "message": f"未知模式: {mode}"}
        self.current_mode = mode
        self.model = self.mode_models[mode]
        self.conversation.current_mode = mode
        self._title_generated = False
        self._apply_mode_tools(mode)
        if mode == "rag":
            self.conversation.knowledge_mode = True
        else:
            self.conversation.knowledge_mode = False
        logger.info(f"切换模式: {mode} → {self.model}")
        return {"status": "ok", "mode": mode, "model": self.model}

    def toggle_knowledge_mode(self) -> dict:
        self.conversation.knowledge_mode = not self.conversation.knowledge_mode
        status = "开启" if self.conversation.knowledge_mode else "关闭"
        logger.info(f"知识库模式: {status}")
        return {"status": "ok", "knowledge_mode": self.conversation.knowledge_mode}

    def cancel(self):
        self._is_cancelled = True

    def create_conversation(self) -> str:
        self._title_generated = False
        self._xray_results_cache = None
        self.conversation.current_mode = self.current_mode
        return self.conversation.create(self.current_mode)

    def switch_conversation(self, conv_id: str) -> bool:
        self._title_generated = False
        return self.conversation.switch(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        return self.conversation.delete(conv_id)

    def list_conversations(self) -> list:
        return self.conversation.list_all()

    def list_conversations_by_mode(self, mode: str) -> list:
        return self.conversation.list_by_mode(mode)

    def list_all_modes_conversations(self) -> dict:
        return self.conversation.list_all_modes()

    def get_history(self) -> list:
        return self.conversation.messages

    def clear_history(self):
        self.conversation.clear()

    def _parse_file(self, filename: str, content: bytes) -> str:
        try:
            text = content.decode('utf-8', errors='ignore')
        except:
            return f"[无法解析文件: {filename}]"
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if ext in ('xlsx', 'xls'):
            try:
                import pandas as pd
                from io import BytesIO
                df = pd.read_excel(BytesIO(content))
                self.conversation.last_df = df
                return f"工作表: {df.shape[0]}行 x {df.shape[1]}列\n列名: {', '.join(str(c) for c in df.columns)}\n{df.head(10).to_string(index=False)}"
            except Exception as e:
                self.conversation.last_df = None
                return f"[Excel解析失败: {e}]"
        if ext == 'csv':
            try:
                import pandas as pd
                from io import StringIO
                df = pd.read_csv(StringIO(text))
                self.conversation.last_df = df
                return f"CSV: {df.shape[0]}行 x {df.shape[1]}列\n{df.head(10).to_string(index=False)}"
            except Exception:
                self.conversation.last_df = None
        if len(text) > 3000:
            text = text[:3000] + "\n...(内容已截断)"
        return text

    def _is_memory_enabled(self) -> bool:
        settings_path = Path("data/settings.json")
        if settings_path.exists():
            try:
                user_settings = json.loads(settings_path.read_text(encoding='utf-8'))
                return user_settings.get("memory", {}).get("enabled", True)
            except:
                pass
        return True

    def _load_memory_text(self) -> str:
        if not self._is_memory_enabled():
            return ""
        memory_path = self.config.get("data", {}).get("personal_memory", "data/personal_memory.json")
        memory_file = Path(memory_path) if memory_path else Path("data/personal_memory.json")
        try:
            if memory_file.exists():
                memories = json.loads(memory_file.read_text(encoding='utf-8'))
                if memories:
                    lines = []
                    for m in memories[-20:]:
                        content = m.get("content", "")
                        if content:
                            lines.append(f"- {content}")
                    if lines:
                        return "\n\n# 用户个人信息\n" + "\n".join(lines) + "\n"
        except Exception:
            pass
        return ""

    # ========== 核心对话 ==========
    async def chat(
        self,
        message: str,
        files: list = None,
        search_on: bool = False,
        skip_user_message: bool = False,
        selected_docs: list = None,
    ) -> AsyncGenerator[dict, None]:
        self._is_cancelled = False

        if not self.conversation.current_id:
            self.create_conversation()

        ctx = await self._step_parse_input(message, files)
        if selected_docs:
            ctx["selected_docs"] = selected_docs
        if self.current_mode == "xray":
            user_display = datetime.now().strftime("%m-%d %H:%M")
            self._update_title(user_display)
        else:
            user_display = ctx["original_message"] or ""

        user_files = []
        for img in ctx.get("images", []):
            user_files.append({"name": img["name"], "type": "image", "path": img.get("path", "")})
        for f in ctx.get("files", []):
            user_files.append({"name": f["name"], "type": "file"})

        if not skip_user_message:
            self.conversation.add_message("user", user_display, files=user_files if user_files else None)

        if not self._title_generated and self.current_mode != "xray":
            self._title_generated = True
            title = await self._generate_title()
            if title:
                yield {"type": "title", "content": title}

        if ctx.get("files") and not ctx.get("has_image"):
            yield {"type": "think", "content": f"正在分析 {len(ctx['files'])} 个文件..."}

        if ctx.get("has_image"):
            if self.current_mode == "xray":
                async for event in self._step_xray_diagnose(ctx):
                    yield event
                extra = {}
                if self._xray_results_cache:
                    extra["xrayResults"] = self._xray_results_cache
                self.conversation.add_message("assistant", "", **extra)
                await self.conversation.save()
                yield {"type": "done", "content": ""}
                return
            else:
                async for event in self._step_analyze_image(ctx):
                    yield event

        if ctx.get("files") and not ctx.get("has_image"):
            yield {"type": "think", "content": "文件分析完成"}

        ctx = await self._step_rag_search(ctx)

        async for event in self._step_memory(ctx):
            yield event

        if self.current_mode == "agent":
            async for event in self._step_agent_router(ctx):
                yield event
            await self.conversation.save()
            yield {"type": "done", "content": ""}
            return

        if ctx.get("rag_sources"):
            yield {"type": "refs", "content": ctx["rag_sources"]}
        messages = self._build_messages(ctx)
        full_response = ""

        try:
            async for event in self.stream.stream(messages, self.model):
                if self._is_cancelled:
                    break
                if event["type"] == "text":
                    full_response += event["content"]
                elif event["type"] == "think":
                    pass
                yield event
        except Exception as e:
            logger.error(f"流式生成失败: {e}")
            if full_response:
                self._save_partial(full_response)
            raise

        if self._is_cancelled:
            extra = {}
            if self._xray_results_cache:
                extra["xrayResults"] = self._xray_results_cache
            if full_response:
                self.conversation.add_message("assistant", full_response + "\n\n⏹ 已停止生成", stopped=True, **extra)
            else:
                self.conversation.add_message("assistant", "", stopped=True, **extra)
            await self.conversation.save()
            yield {"type": "cancelled", "content": full_response}
        elif full_response:
            extra = {}
            if self._xray_results_cache:
                extra["xrayResults"] = self._xray_results_cache
            # 保存分析状态和追问建议
            if ctx.get("analyze_done"):
                extra["analyzeStatus"] = f"已分析 {len(ctx.get('images', []))} 张图片"
            if self.current_mode == "normal":
                suggestions = await self._generate_suggestions(message, full_response)
                if suggestions:
                    extra["suggestions"] = suggestions
            self.conversation.add_message("assistant", full_response, **extra)
            await self.conversation.save()

        if full_response and not self._is_cancelled and self.current_mode == "normal":
            suggestions = extra.get("suggestions", [])
            if suggestions:
                yield {"type": "suggestions", "content": suggestions}

        yield {"type": "done", "content": ""}

        if ctx.get("is_single_use_file"):
            yield {"type": "meta", "content": "single_use_file"}

    async def _step_parse_input(self, message: str, files: list) -> dict:
        ctx = {
            "original_message": message or "",
            "processed_message": message or "",
            "files": [], "images": [], "has_image": False, "has_file": False,
            "is_xray": False, "vision_descriptions": [], "is_single_use_file": False,
            "tools_called": [], "agent_tools_called": [], "rag_context": "", "_file_text": "",
        }
        if not files:
            return ctx
        for f in files:
            file_name = f.get("name", "")
            file_content = f.get("content", b"")
            ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
            if ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'):
                ctx["has_image"] = True
                ctx["has_file"] = True
                b64 = base64.b64encode(file_content).decode()
                safe_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
                temp_path = Path("data/uploads") / safe_name
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_bytes(file_content)
                ctx["images"].append({"name": file_name, "base64": b64, "path": str(temp_path)})
            elif ext in ('xlsx', 'xls', 'csv', 'pdf', 'txt', 'doc', 'docx', 'py', 'js', 'json', 'md'):
                ctx["has_file"] = True
                ctx["is_single_use_file"] = True
                parsed = self._parse_file(file_name, file_content)
                ctx["files"].append({"name": file_name, "summary": parsed[:800]})
        file_text = ""
        if ctx["files"]:
            file_summaries = "\n".join([f"- {f['name']}: {f['summary']}" for f in ctx["files"]])
            if not ctx["images"]:
                prompt = self.prompts.get("multi_file")
                if prompt:
                    ctx["processed_message"] = prompt.format(message=message or "请总结这些文件的内容", summaries=file_summaries)
                else:
                    ctx["processed_message"] = f"用户上传了以下文件并说：{message or '请总结这些文件'}\n\n{file_summaries}"
            else:
                file_text = "\n\n---\n同时上传的文件内容：\n" + file_summaries
        if ctx["images"] and not message and not ctx["files"]:
            ctx["processed_message"] = "请描述这些图片"
        ctx["_file_text"] = file_text
        return ctx

    async def _step_analyze_image(self, ctx: dict) -> AsyncGenerator[dict, None]:
        if not ctx.get("images"):
            return
        descriptions = []
        desc_prompt = self.prompts.get("vision_describe")
        if not desc_prompt:
            desc_prompt = "请详细描述这张图片的内容，包括主要物体、人物、场景、文字等。"
        for idx, img in enumerate(ctx["images"]):
            yield {"type": "think", "content": f"正在分析图片 {idx+1}/{len(ctx['images'])}..."}
            try:
                async with httpx.AsyncClient(timeout=60) as c:
                    resp = await c.post(f"{self.llm.base_url}/api/chat", json={
                        "model": self.vision_model,
                        "messages": [{"role": "user", "content": desc_prompt, "images": [img["base64"]]}],
                        "stream": False
                    })
                    resp.raise_for_status()
                    desc = resp.json().get("message", {}).get("content", "")
                    descriptions.append(desc)
                    logger.info(f"图片 [{img['name']}] 描述: {desc[:80]}")
            except Exception as e:
                logger.warning(f"图片描述失败 [{img['name']}]: {e}")
                descriptions.append(f"[图片描述失败: {img['name']}]")
        ctx["vision_descriptions"] = descriptions
        if self.current_mode == "normal":
            yield {"type": "think", "content": f"已分析 {len(ctx['images'])} 张图片"}
            user_msg = ctx.get("original_message", "") or "请描述这些图片"
            if len(ctx["images"]) == 1:
                ctx["processed_message"] = (
                    f"用户上传了1张图片（{ctx['images'][0]['name']}），以下是AI描述：\n"
                    f"{descriptions[0]}\n\n"
                    f"用户说：{user_msg}\n\n请根据描述回答用户。"
                )
            else:
                desc_lines = [f"图片{idx+1}（{img['name']}）：{desc}" for idx, (img, desc) in enumerate(zip(ctx["images"], descriptions))]
                prompt = self.prompts.get("multi_image")
                if prompt:
                    ctx["processed_message"] = prompt.format(count=len(ctx["images"]), message=user_msg, descriptions="\n".join(desc_lines))
                else:
                    ctx["processed_message"] = f"用户上传了 {len(ctx['images'])} 张图片并说：{user_msg}\n\n图片描述：\n" + "\n".join(desc_lines)
        ctx["analyze_done"] = True
        yield {"type": "think", "content": "图片分析完成"}

    async def _step_xray_diagnose(self, ctx: dict) -> AsyncGenerator[dict, None]:
        if not ctx.get("images"):
            return
        images = ctx["images"]
        total = len(images)
        xray_results = []
        all_rejected = True
        xray_tool = self.tools.get("xray_diagnose")
        if not xray_tool or not xray_tool.enabled:
            yield {"type": "xray_error", "content": "胸片诊断工具未启用"}
            return
        yield {"type": "think", "content": f"分析中...共 {total} 张胸片"}
        for idx, img in enumerate(images):
            if self._is_cancelled:
                break
            file_name = img["name"]
            image_bytes = base64.b64decode(img["base64"])
            yield {"type": "xray_progress", "content": {"current": idx + 1, "total": total, "file_name": file_name, "status": "checking"}}
            ood_pass = await asyncio.to_thread(self._contrastive_ood_check, image_bytes)
            if not ood_pass:
                xray_results.append({"file_name": file_name, "status": "rejected", "reason": "自动验证未通过，这不是胸部X光片", "retry_allowed": True})
                yield {"type": "xray_progress", "content": {"current": idx + 1, "total": total, "file_name": file_name, "status": "rejected"}}
                if (idx + 1) % 3 == 0 or idx == total - 1:
                    self._xray_results_cache = list(xray_results)
                    yield {"type": "xray_results", "content": list(xray_results)}
                continue
            yield {"type": "xray_progress", "content": {"current": idx + 1, "total": total, "file_name": file_name, "status": "diagnosing"}}
            try:
                result = await xray_tool.execute("", {"image_base64": img["base64"]})
                diagnose_result = result.get("result", "")
                all_probs = result.get("all_probs", {})
                logger.info(f"胸片 [{file_name}] 诊断完成")
                category = "建议复查"
                no_finding_prob = all_probs.get("no_finding_prob", 0) if all_probs else 0
                reason = ""
                cat_match = re.search(r'判定:\s*(正常|建议复查|异常)', diagnose_result)
                if cat_match:
                    category = cat_match.group(1)
                reason_match = re.search(r'理由:\s*(.+?)(?:\n|$)', diagnose_result)
                if reason_match:
                    reason = reason_match.group(1)
                xray_results.append({"file_name": file_name, "status": "ok", "category": category, "no_finding_prob": no_finding_prob, "reason": reason, "all_probs": all_probs})
                all_rejected = False
                yield {"type": "xray_progress", "content": {"current": idx + 1, "total": total, "file_name": file_name, "status": "ok"}}
            except Exception as e:
                logger.error(f"胸片 [{file_name}] 诊断失败: {e}")
                xray_results.append({"file_name": file_name, "status": "error", "reason": str(e), "retry_allowed": True})
                yield {"type": "xray_progress", "content": {"current": idx + 1, "total": total, "file_name": file_name, "status": "error"}}
            if (idx + 1) % 3 == 0 or idx == total - 1:
                self._xray_results_cache = list(xray_results)
                yield {"type": "xray_results", "content": list(xray_results)}
        self._xray_results_cache = xray_results
        if all_rejected and total == 1:
            yield {"type": "xray_rejected", "content": {"reason": "自动验证未通过，请上传胸部X光片", "retry_allowed": True}}

    async def generate_xray_report(self, conv_id: str, file_name: str) -> AsyncGenerator[dict, None]:
        data = self.conversation._load(conv_id)
        if not data:
            yield {"type": "error", "content": "对话不存在"}
            return
        assistant_msg = None
        assistant_idx = None
        for i, m in enumerate(data.get("messages", [])):
            if m.get("xrayResults"):
                assistant_msg = m
                assistant_idx = i
                break
        if not assistant_msg:
            yield {"type": "error", "content": "没有找到诊断结果"}
            return
        target = None
        for r in assistant_msg["xrayResults"]:
            if r["file_name"] == file_name and r["status"] == "ok":
                target = r
                break
        if not target:
            yield {"type": "error", "content": f"未找到 {file_name} 的诊断结果"}
            return
        if target.get("report"):
            yield {"type": "text", "content": target["report"]}
            yield {"type": "done", "content": ""}
            return
        all_probs = target.get("all_probs", {})
        diseases_str = ""
        if all_probs.get("diseases"):
            top5 = [d for d in all_probs["diseases"] if d["probability"] > 0][:5]
            diseases_str = "、".join([f"{d['disease_cn']}({d['probability']}%)" for d in top5])
        prompt = (
            f"请根据以下胸片 AI 诊断结果，生成诊断报告。\n\n"
            f"文件名：{file_name}\n判定：{target['category']}\n未见异常概率：{target['no_finding_prob']}%\n"
            f"依据：{target.get('reason', '')}\n主要可疑疾病：{diseases_str}\n\n"
            f"格式：\n**诊断报告**\n（概括）\n**解释**\n（通俗说明）\n**建议**\n（专业建议）\n"
            f"**特别提醒**\n本结果仅基于AI初步判断，不能替代专业医师诊断。"
        )
        xray_system = self.prompts.get("system_xray") or "你是一位放射科医生助手。"
        messages = [
            {"role": "system", "content": xray_system},
            {"role": "user", "content": prompt}
        ]
        full_report = ""
        try:
            async for event in self.stream.stream(messages, self.mode_models.get("fast", "qwen2.5:3b-instruct")):
                if event["type"] == "text":
                    full_report += event["content"]
                    yield event
            target["report"] = full_report
            data["messages"][assistant_idx] = assistant_msg
            data["updated_at"] = datetime.now().isoformat()
            path = self.conversation.storage / f"{conv_id}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            logger.info(f"胸片报告已缓存: {file_name}")
            yield {"type": "done", "content": ""}
        except Exception as e:
            logger.error(f"生成报告失败 [{file_name}]: {e}")
            yield {"type": "error", "content": str(e)}

    async def retry_single_xray(self, conv_id: str, file_name: str) -> AsyncGenerator[dict, None]:
        data = self.conversation._load(conv_id)
        if not data:
            yield {"type": "error", "content": "对话不存在"}
            return
        assistant_msg = None
        assistant_idx = None
        for i, m in enumerate(data.get("messages", [])):
            if m.get("xrayResults"):
                assistant_msg = m
                assistant_idx = i
                break
        if not assistant_msg:
            yield {"type": "error", "content": "没有找到诊断结果"}
            return
        xray_results = assistant_msg["xrayResults"]
        target = None
        target_idx = None
        for i, r in enumerate(xray_results):
            if r["file_name"] == file_name and r["status"] in ("rejected", "error"):
                target = r
                target_idx = i
                break
        if not target:
            yield {"type": "error", "content": f"未找到 {file_name} 或该图片状态不允许重新检测"}
            return
        img_path = None
        for m in data.get("messages", []):
            if m["role"] == "user" and m.get("files"):
                for f in m.get("files", []):
                    if f["name"] == file_name and f.get("path"):
                        img_path = f["path"]
                        break
        if not img_path or not Path(img_path).exists():
            yield {"type": "error", "content": f"图片文件不存在"}
            return
        image_bytes = Path(img_path).read_bytes()
        image_base64 = base64.b64encode(image_bytes).decode()
        yield {"type": "think", "content": f"正在使用视觉模型验证 {file_name}..."}
        vision_pass = await self._judge_with_vision(image_base64, "请仔细观察这张图片，判断它是否为胸部X光片。只回答：是 或 否。")
        xray_tool = self.tools.get("xray_diagnose")
        if not xray_tool:
            yield {"type": "error", "content": "诊断工具未启用"}
            return
        if not vision_pass:
            target["retry_allowed"] = True
            target["reason"] = "视觉模型判断这不是胸部X光片"
            assistant_msg["xrayResults"] = xray_results
            data["messages"][assistant_idx] = assistant_msg
            data["updated_at"] = datetime.now().isoformat()
            path = self.conversation.storage / f"{conv_id}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            yield {"type": "xray_retry_result", "content": {"file_name": file_name, "status": "rejected", "reason": target["reason"], "retry_allowed": True}}
            return
        yield {"type": "think", "content": f"视觉模型确认 {file_name} 为胸片，正在进行疾病诊断..."}
        try:
            result = await xray_tool.execute("", {"image_base64": image_base64})
            diagnose_result = result.get("result", "")
            all_probs = result.get("all_probs", {})
            category = "建议复查"
            no_finding_prob = all_probs.get("no_finding_prob", 0) if all_probs else 0
            reason = ""
            cat_match = re.search(r'判定:\s*(正常|建议复查|异常)', diagnose_result)
            if cat_match:
                category = cat_match.group(1)
            reason_match = re.search(r'理由:\s*(.+?)(?:\n|$)', diagnose_result)
            if reason_match:
                reason = reason_match.group(1)
            xray_results[target_idx] = {"file_name": file_name, "status": "ok", "category": category, "no_finding_prob": no_finding_prob, "reason": reason, "all_probs": all_probs}
            assistant_msg["xrayResults"] = xray_results
            data["messages"][assistant_idx] = assistant_msg
            data["updated_at"] = datetime.now().isoformat()
            path = self.conversation.storage / f"{conv_id}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            if self.conversation.current_id == conv_id:
                self.conversation.messages = data["messages"]
            yield {"type": "xray_retry_result", "content": xray_results[target_idx]}
        except Exception as e:
            logger.error(f"重新检测失败 [{file_name}]: {e}")
            yield {"type": "error", "content": str(e)}

    async def _step_multi_agent(self, ctx: dict) -> AsyncGenerator[dict, None]:
        from agent.orchestrator.master import MasterAgent
        from agent.orchestrator.workers import SearchAgent, CodeAgent, ReviewAgent, WeatherAgent, TranslateAgent, TimeAgent, CalculateAgent
        
        llm = self.llm
        planner_llm = LLMClient(self.config)
        planner_llm.default_model = self.mode_models.get("agent_planner", "qwen2.5:7b-instruct")
        
        master = MasterAgent(
            llm=planner_llm,
            workers={
                "search": SearchAgent(llm, self.tools.get("web_search")),
                "code": CodeAgent(llm, self.tools.get("execute_code")),
                "review": ReviewAgent(llm),
                "weather": WeatherAgent(llm, self.tools.get("get_weather")),
                "translate": TranslateAgent(llm, self.tools.get("translate")),
                "time": TimeAgent(llm, self.tools.get("get_current_time")),
                "calculate": CalculateAgent(llm, self.tools.get("calculate")),
            }
        )
        
        # 构建文件上下文给规划器
        file_context = ""
        if ctx.get("vision_descriptions"):
            file_context += "\n\n【用户上传的图片描述】\n" + "\n".join(ctx["vision_descriptions"])
        if ctx.get("files"):
            file_context += "\n\n【用户上传的文件内容】\n" + "\n".join([f"- {f['name']}: {f['summary']}" for f in ctx["files"]])
        
        # 0. 图片/文件分析状态（如果有的话）
        has_files = bool(ctx.get("vision_descriptions") or ctx.get("files"))
        analyze_task = ""
        analyze_result = ""
        if has_files:
            parts = []
            analyze_details = []
            if ctx.get("vision_descriptions"):
                parts.append(f"已分析 {len(ctx.get('images', []))} 张图片")
                analyze_details.append("【图片描述】\n" + "\n".join(ctx["vision_descriptions"]))
            if ctx.get("files"):
                parts.append(f"已分析 {len(ctx['files'])} 个文件")
                analyze_details.append("【文件内容】\n" + "\n".join([f"- {f['name']}: {f['summary']}" for f in ctx["files"]]))
            analyze_task = "、".join(parts)
            analyze_result = "\n\n".join(analyze_details) if analyze_details else ""
            yield {"type": "multi_agent_step", "content": {"status": "ok", "role": "analyzer", "task": analyze_task, "result": analyze_result}}
        
        # 1. 规划中 → 橙色圈
        planning_task = "正在分析任务..."
        yield {"type": "multi_agent_step", "content": {"status": "planning", "role": "planner", "task": planning_task, "result": ""}}
        
        plan = await master._plan(ctx["original_message"], file_context=file_context if file_context else None)
        
        # 2. 规划完成 → 对勾
        yield {"type": "multi_agent_step", "content": {"status": "ok", "role": "planner", "task": planning_task, "result": json.dumps(plan, ensure_ascii=False)}}
        
        if not plan:
            resp = await master.llm.chat(
                messages=[{"role": "user", "content": ctx["original_message"]}],
                temperature=0.7
            )
            answer = resp.get("message", {}).get("content", "")
            all_steps = []
            if has_files:
                all_steps.append({"status": "ok", "role": "analyzer", "task": analyze_task, "result": analyze_result})
            all_steps.append({"status": "ok", "role": "planner", "task": planning_task, "result": json.dumps(plan, ensure_ascii=False)})
            self.conversation.add_message("assistant", answer, multiAgentSteps=all_steps)
            yield {"type": "text", "content": answer}
            return
        
        # 构建文件数据列表，注入到子任务 context 中
        file_data_list = []
        for img in ctx.get("images", []):
            file_data_list.append({"role": "user", "task": f"图片: {img['name']}", "file_data": img.get("base64", "")[:3000]})
        for f in ctx.get("files", []):
            file_data_list.append({"role": "user", "task": f"文件: {f['name']}", "file_data": f.get("summary", "")[:3000]})
        
        # 3. 逐步执行子任务
        results = []
        for step in plan:
            role = step.get("role", "search")
            task = step.get("task", "")
            if isinstance(task, dict):
                task = json.dumps(task, ensure_ascii=False)
            elif not isinstance(task, str):
                task = str(task)
            
            # 子任务开始 → 橙色圈
            yield {"type": "multi_agent_step", "content": {"status": "running", "role": role, "task": task, "result": ""}}
            
            worker = master.workers.get(role)
            if worker:
                try:
                    result = await worker.run(task, context=file_data_list + results)
                    results.append(result)
                    # 子任务完成 → 对勾
                    yield {"type": "multi_agent_step", "content": {"status": "ok", "role": role, "task": task, "result": result.get("result", "")[:500], "keywords": result.get("keywords", ""), "city": result.get("city", ""), "target": result.get("target", ""), "code": result.get("code", "")}}
                except Exception as e:
                    results.append({"role": role, "task": task, "result": str(e), "status": "error"})
                    yield {"type": "multi_agent_step", "content": {"status": "error", "role": role, "task": task, "result": str(e)}}
            else:
                results.append({"role": role, "task": task, "result": "未知角色", "status": "error"})
                yield {"type": "multi_agent_step", "content": {"status": "error", "role": role, "task": task, "result": "未知角色"}}
        
        # 4. 汇总中 → 橙色圈
        summarizing_task = "正在汇总结果..."
        yield {"type": "multi_agent_step", "content": {"status": "summarizing", "role": "summarizer", "task": summarizing_task, "result": ""}}
        
        # 5. 流式输出汇总内容
        full_answer = ""
        sum_messages = [
            {"role": "user", "content": f"问题：{ctx['original_message']}\n\n参考资料：{json.dumps(results, ensure_ascii=False)}"}
        ]
        async for event in self.stream.stream(sum_messages, self.model):
            if event["type"] == "text":
                full_answer += event["content"]
                yield event
        
        # 6. 汇总完成 → 对勾，存汇总结果
        yield {"type": "multi_agent_step", "content": {"status": "ok", "role": "summarizer", "task": summarizing_task, "result": full_answer[:500]}}
        
        # 7. 构建完整步骤列表，持久化到 JSON
        all_steps = []
        if has_files:
            all_steps.append({"status": "ok", "role": "analyzer", "task": analyze_task, "result": analyze_result})
        all_steps.append({"status": "ok", "role": "planner", "task": planning_task, "result": json.dumps(plan, ensure_ascii=False)})
        for r in results:
            all_steps.append(r)
        all_steps.append({"status": "ok", "role": "summarizer", "task": summarizing_task, "result": full_answer})
        
        self.conversation.add_message("assistant", full_answer, multiAgentSteps=all_steps)

    async def _step_agent_router(self, ctx: dict) -> AsyncGenerator[dict, None]:
        async for event in self._step_multi_agent(ctx):
            yield event

    async def _judge_with_vision(self, image_base64: str, prompt: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.post(f"{self.llm.base_url}/api/chat", json={
                    "model": self.xray_judge_model,
                    "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
                    "stream": False
                })
                resp.raise_for_status()
                judge_text = resp.json().get("message", {}).get("content", "").strip()
                logger.info(f"视觉模型判断: {judge_text}")
                return judge_text.startswith("是") or "YES" in judge_text.upper()
        except Exception as e:
            logger.warning(f"视觉模型调用失败: {e}")
            return False

    def _contrastive_ood_check(self, image_bytes: bytes) -> bool:
        if not hasattr(self, '_ood_loaded'):
            self._ood_loaded = True
            if not self.ood_stats_path.exists():
                logger.warning("OOD统计量未找到，跳过检测")
                self._ood_encoder = None
                return True
            with open(self.ood_stats_path, 'r') as f:
                stats = json.load(f)
            self._ood_mean = np.array(stats['mean'])
            self._ood_inv_cov = np.array(stats['inv_cov'])
            self._ood_threshold = stats['threshold']
            self._ood_device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self._ood_encoder = self._load_ood_encoder()
        if self._ood_encoder is None:
            return True
        try:
            pil_img = PILImage.open(io.BytesIO(image_bytes)).convert('RGB')
            transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            img_tensor = transform(pil_img).unsqueeze(0).to(self._ood_device)
            with torch.no_grad():
                feature = self._ood_encoder(img_tensor).cpu().numpy()[0]
            diff = feature - self._ood_mean
            dist = np.sqrt(np.dot(np.dot(diff, self._ood_inv_cov), diff))
            logger.info(f"OOD距离: {dist:.2f}, 阈值: {self._ood_threshold}")
            return bool(dist <= self._ood_threshold)
        except Exception as e:
            logger.warning(f"OOD检测失败: {e}")
            return True

    def _load_ood_encoder(self):
        from cryptography.fernet import Fernet
        import io as _io
        KEY = b'3fik6HnQrKMunEXhtTdslF1utDaDTU_DnVWD1R_qpBo='
        enc_path = self.ood_model_path.with_suffix('.enc')
        if enc_path.exists():
            logger.info("加载加密 OOD 模型...")
            f = Fernet(KEY)
            decrypted = f.decrypt(enc_path.read_bytes())
            checkpoint = torch.load(_io.BytesIO(decrypted), map_location=self._ood_device, weights_only=True)
        elif self.ood_model_path.exists():
            logger.info("加载明文 OOD 模型...")
            checkpoint = torch.load(self.ood_model_path, map_location=self._ood_device, weights_only=True)
        else:
            logger.warning(f"OOD模型不存在")
            return None

        class OODEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                full_resnet = resnet50(weights=None)
                self.backbone = nn.Sequential(
                    full_resnet.conv1, full_resnet.bn1, full_resnet.relu, full_resnet.maxpool,
                    full_resnet.layer1, full_resnet.layer2, full_resnet.layer3, full_resnet.layer4,
                    full_resnet.avgpool
                )
                self.proj = nn.Linear(2048, 512)
            def forward(self, x):
                x = self.backbone(x)
                x = torch.flatten(x, 1)
                x = self.proj(x)
                return F.normalize(x, dim=1)

        model = OODEncoder()
        img_state = checkpoint.get('model_img_state_dict', {})
        key_mapping = [
            ('backbone.conv1', 'backbone.0'), ('backbone.bn1', 'backbone.1'),
            ('backbone.layer1', 'backbone.4'), ('backbone.layer2', 'backbone.5'),
            ('backbone.layer3', 'backbone.6'), ('backbone.layer4', 'backbone.7'),
            ('backbone.avgpool', 'backbone.8'),
        ]
        new_state = {}
        for old_key, value in img_state.items():
            key = old_key.replace('encoder.', '')
            for old_prefix, new_prefix in key_mapping:
                if key.startswith(old_prefix):
                    key = key.replace(old_prefix, new_prefix)
                    break
            new_state[key] = value
        model.load_state_dict(new_state, strict=False)
        model = model.to(self._ood_device)
        model.eval()
        logger.info("OOD编码器加载成功")
        return model

    async def _step_rag_search(self, ctx: dict) -> dict:
        ctx["rag_context"] = ""
        ctx["rag_sources"] = []
        rag_tool = self.tools.get("rag_search")
        if not rag_tool or not rag_tool.enabled:
            return ctx
        selected_docs = ctx.get("selected_docs", [])
        if not selected_docs:
            return ctx
        try:
            result = await rag_tool.execute(ctx["original_message"], {
                "has_file": ctx.get("has_file", False),
                "knowledge_mode": True,
                "selected_docs": selected_docs
            })
            ctx["rag_context"] = result.get("result", "")
            raw = result.get("result", "")
            source_items = re.findall(r'\[来源 \d+: (.+?)\]\n(.+?)(?=\n---|\n\[来源|\Z)', raw, re.DOTALL)
            seen = set()
            ctx["rag_sources"] = []
            for source, snippet in source_items:
                if source not in seen:
                    seen.add(source)
                    ctx["rag_sources"].append({"source": source, "snippet": snippet.strip()})
        except Exception as e:
            logger.warning(f"RAG 检索失败: {e}")
        return ctx

    def _match_memory_intent(self, message: str) -> str | None:
        msg = message.lower()
        remember_kw = ['记住', '帮我记', '记住我', '记一下', '别忘了', '备注一下', '记下来', '存档', '帮我记住']
        for kw in remember_kw:
            if kw in msg:
                return 'remember'
        recall_kw = ['我之前', '我叫什么', '我的名字', '还记得', '回忆', '之前说过', '你记得',
                     '我的猫', '我的狗', '我的宠物', '我喜欢', '我不喜欢', '我住在', '我的工作是',
                     '我是谁', '我叫啥', '怎么称呼我', '你知道我是谁吗', '知道我是谁']
        for kw in recall_kw:
            if kw in msg:
                return 'recall'
        return None

    async def _step_memory(self, ctx: dict) -> AsyncGenerator[dict, None]:
        if not self._is_memory_enabled():
            return
        message = ctx.get("original_message", "")
        intent = self._match_memory_intent(message)
        if not intent:
            return
        memory_tools = [t for t in self.tools.get_enabled() if t.name in ("remember", "recall")]
        if not memory_tools:
            return
        confirm_prompt = self.prompts.get("memory_confirm") or "判断用户是否真的在执行记忆操作。只回复 YES 或 NO。"
        try:
            resp = await self.llm.chat(
                messages=[{"role": "system", "content": confirm_prompt}, {"role": "user", "content": f"用户说：{message}\n\n意图是：{intent}\n\n这是记忆操作吗？只回复 YES 或 NO。"}],
                model="qwen2.5:3b-instruct", temperature=0.1
            )
            answer = resp.get("message", {}).get("content", "").strip().upper()
            if "YES" not in answer:
                return
            tool_name = "remember" if intent == "remember" else "recall"
            tool = self.tools.get(tool_name)
            if not tool:
                return
            if intent == "remember":
                yield {"type": "memory", "content": {"type": "remember", "status": "正在更新记忆..."}}
                result = await tool.execute("", {"content": message})
                ctx["tools_called"].append({"name": "remember", "result": str(result.get("result", result))})
                yield {"type": "memory", "content": {"type": "remember", "status": "记忆已更新", "result": str(result.get("result", result))}}
            elif intent == "recall":
                yield {"type": "memory", "content": {"type": "recall", "status": "正在搜索记忆..."}}
                result = await tool.execute("", {"query": ""})
                ctx["tools_called"].append({"name": "recall", "result": str(result.get("result", result))})
                yield {"type": "memory", "content": {"type": "recall", "status": "记忆搜索完成", "result": str(result.get("result", result))}}
        except Exception as e:
            logger.warning(f"记忆处理失败: {e}")

    def _build_messages(self, ctx: dict) -> list:
        memory_text = self._load_memory_text()
        role_name = getattr(self.conversation, "role_name", "")
        mode_system_map = {
            "normal": "system_normal", "agent": "system_agent", "rag": "system_rag",
            "xray": "system_xray", "email": "system_email", "reasoning": "system_reasoning",
        }
        reasoning_models = [self.mode_models.get("reasoning", ""), "deepseek-r1:8b", "deepseek-r1:7b", "qwen3:8b"]
        if self.model in reasoning_models:
            system_key = "system_reasoning"
        else:
            system_key = mode_system_map.get(self.current_mode, "system_normal")
        system_template = self.prompts.get(system_key) or self.prompts.get("system_normal")
        if role_name:
            role_prompt = self.prompts.get(f"role_{role_name}")
            system_prompt = role_prompt if role_prompt else system_template.format(memory_text=memory_text, df_info="", rag_context=ctx.get("rag_context", ""))
        else:
            system_prompt = system_template.format(memory_text=memory_text, df_info="", rag_context=ctx.get("rag_context", ""))
        if system_key == "system_normal" and not role_name:
            final_prompt = self.prompts.get("system_final")
            if final_prompt:
                system_prompt += "\n" + final_prompt
        messages = [{"role": "system", "content": system_prompt}]
        for m in self.conversation.get_recent_messages(6):
            c = str(m.get("content", ""))
            if c.startswith("[工具"):
                continue
            if len(c) > 500:
                c = c[:500] + "..."
            messages.append({"role": m["role"], "content": c})
        all_tools = ctx.get("tools_called", []) + ctx.get("agent_tools_called", [])
        if all_tools:
            messages.append({
                "role": "user",
                "content": f"用户问题：{ctx['original_message']}\n\n工具结果：\n" +
                           "\n".join([f"[{t['name']}]: {str(t['result'])[:1000]}" for t in all_tools]) +
                           "\n\n请基于工具结果回答。"
            })
        else:
            content = ctx["processed_message"]
            if ctx.get("_file_text"):
                content += ctx["_file_text"]
            messages.append({"role": "user", "content": content})
        return messages

    async def _generate_title(self) -> str:
        try:
            user_msg = ""
            for m in self.conversation.messages:
                if m["role"] == "user":
                    user_msg = m["content"].strip()
                    break
            if not user_msg: return ""
            user_msg = re.sub(r'^(记住|帮我记|记住我|记一下|别忘了|备注一下|记下来|存档|帮我记住)[：:\s]*', '', user_msg)
            prompt = self.prompts.get("title_gen")
            if not prompt: return ""
            resp = await self.llm.chat(messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg[:200]}], model=self.title_model)
            title = resp.get("message", {}).get("content", "").strip().replace('"', '').replace('"', '').replace('"', '').strip()
            if title and len(title) <= 20:
                self._update_title(title)
                return title
        except Exception as e:
            logger.debug(f"标题生成失败: {e}")
        return ""

    def _update_title(self, title: str):
        if not self.conversation.current_id: return
        path = self.conversation.storage / f"{self.conversation.current_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                data["title"] = title
                data["updated_at"] = datetime.now().isoformat()
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            except: pass
        index_path = self.conversation.storage / "index.json"
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding='utf-8'))
                for item in index:
                    if item["id"] == self.conversation.current_id:
                        item["title"] = title
                        break
                index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
            except: pass

    async def _generate_suggestions(self, question: str, answer: str) -> list:
        try:
            prompt = self.prompts.get("suggestions")
            if not prompt: return []
            prompt = prompt.format(question=question, answer=answer[:300])
            resp = await self.llm.chat(messages=[{"role": "user", "content": prompt}], model="qwen2.5:3b-instruct")
            text = resp.get("message", {}).get("content", "").strip()
            if text:
                suggestions = []
                for s in text.split('\n'):
                    s = s.strip()
                    if not s or len(s) > 25: continue
                    if any(w in s for w in ['你想', '你可以', '我推荐', '我建议', '我会', '我觉得', '有没有', '是否']): continue
                    if s.startswith('-') or s.startswith('*') or s[0].isdigit(): continue
                    suggestions.append(s)
                return suggestions[:3]
        except Exception as e:
            logger.debug(f"追问建议生成失败: {e}")
        return []

    def _save_partial(self, content: str, stopped: bool = False):
        if not self.conversation.current_id:
            return
        if content:
            self.conversation.add_message("assistant", content, partial=True)
        if stopped:
            if self.conversation.messages:
                last = self.conversation.messages[-1]
                if last.get("role") == "assistant":
                    last["stopped"] = True
                else:
                    self.conversation.add_message("assistant", "", stopped=True)
            else:
                self.conversation.add_message("assistant", "", stopped=True)
            self.conversation._save()