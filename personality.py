"""人格系统 — 多人设管理、关键词过滤、评论决策与生成"""

import json
import random
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PersonaConfig:
    name: str
    identity: str
    style: str
    weight: int = 1
    keywords: list[str] = field(default_factory=list)
    ai_trigger: str = "自由发挥"
    target_video: bool = True
    target_comments: bool = True
    comment_probability: float = 0.25


SYSTEM_PROMPT_TEMPLATE = """你是一个抖音用户，正在刷抖音视频。你的人设如下：

【人格描述】
{personality}

【评论风格】
{style}

【规则】
1. 评论必须自然口语化，像真实用户在抖音发的评论
2. 评论长度控制在 10-50 个字
3. 不要使用任何 AI 痕迹的语言（如"作为一个"、"我认为"、"值得注意的是"等）
4. 可以适当使用 emoji 但不要过多
5. 不要生成标题或编号，直接输出评论内容
"""

ANALYSIS_PROMPT = """判断这个视频或评论区是否值得评论。值得评论的情况包括但不限于：
- 逻辑谬误、事实错误、价值观问题 → 反驳纠正
- 有趣、感人、涨知识、值得夸奖 → 表扬鼓励
- 有争议性话题、值得讨论 → 发表观点

视频内容：
{content}

评论区热门评论：
{comments}

人格：{personality}
触发条件：{trigger}

直接输出 JSON（不要思考过程）：
{{"should_comment": true/false, "target": "video或comment", "reason": "一句话说明为什么值得评论", "target_comment": "如果要回复某条评论，复制原文；否则为空", "angle": "评论角度（表扬/反驳/调侃/科普等）"}}"""

COMMENT_PROMPT = """根据以下信息生成一条抖音评论。

视频内容：
{content}

已有热门评论：
{existing_comments}

我的人格：{personality}
评论风格：{style}
评论角度：{angle}

直接输出评论内容，不要加引号或任何额外格式。"""

REPLY_PROMPT = """你正在回复抖音上别人的评论。

视频内容：{content}
对方评论：{target_comment}
我的人格：{personality}
评论风格：{style}

直接输出你的回复（10-50字），口语化，不要加引号或格式。"""


class PersonalityEngine:
    def __init__(self, ai_engine, config: dict):
        self.ai = ai_engine
        self.personas: list[PersonaConfig] = self._parse_personas(config)

    def _parse_personas(self, config: dict) -> list[PersonaConfig]:
        """解析多人设配置，兼容旧的单对象格式"""
        # 新格式：personas 数组
        if "personas" in config:
            raw_list = config["personas"]
            return [self._build_persona(p) for p in raw_list]

        # 旧格式：personality 单对象，自动转换
        old = config.get("personality", config)
        return [self._build_persona_from_legacy(old)]

    def _build_persona(self, p: dict) -> PersonaConfig:
        topics = p.get("topics", {})
        strategy = p.get("strategy", {})
        return PersonaConfig(
            name=p.get("name", "未命名"),
            identity=p.get("identity", "一个普通的抖音用户"),
            style=p.get("style", "温和"),
            weight=p.get("weight", 1),
            keywords=topics.get("keywords", []) if isinstance(topics, dict) else [],
            ai_trigger=topics.get("ai_trigger", "自由发挥") if isinstance(topics, dict) else "自由发挥",
            target_video=strategy.get("target_video", True),
            target_comments=strategy.get("target_comments", True),
            comment_probability=strategy.get("comment_probability", 0.25),
        )

    def _build_persona_from_legacy(self, old: dict) -> PersonaConfig:
        """将旧的 personality 单对象转换为 PersonaConfig"""
        return PersonaConfig(
            name="默认人设",
            identity=old.get("description", "一个普通的抖音用户"),
            style=old.get("comment_style", "温和"),
            weight=1,
            keywords=[],
            ai_trigger=old.get("trigger", "自由发挥"),
            comment_probability=old.get("comment_probability", 0.2),
        )

    def pick_persona(self) -> PersonaConfig:
        """按权重随机选取一个人设"""
        if len(self.personas) == 1:
            return self.personas[0]
        weights = [p.weight for p in self.personas]
        return random.choices(self.personas, weights=weights, k=1)[0]

    def _keyword_match(self, text: str, keywords: list[str]) -> bool:
        """关键词匹配（OR 逻辑），关键词为空则不过滤"""
        if not keywords:
            return True
        return any(kw in text for kw in keywords)

    def analyze_content(self, content_text: str, comments_text: str = "",
                        persona: PersonaConfig | None = None) -> dict:
        """分析视频内容和评论区，决定是否评论"""
        if persona is None:
            persona = self.personas[0]

        # 概率过滤
        if random.random() > persona.comment_probability:
            return {"should_comment": False, "reason": "概率过滤", "angle": ""}

        # 关键词过滤
        if not self._keyword_match(content_text, persona.keywords):
            return {"should_comment": False, "reason": "关键词不匹配", "angle": ""}

        prompt = ANALYSIS_PROMPT.format(
            content=content_text[:500],
            comments=comments_text[:800] if comments_text else "（未读取评论区）",
            personality=persona.identity,
            trigger=persona.ai_trigger,
        )

        response = self.ai.chat(
            messages=[
                {"role": "system", "content": "你是一个 JSON 输出器。用户给你内容，你只输出 JSON，不输出任何其他文字。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        try:
            text = response.strip()
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    if "should_comment" in part:
                        text = part.replace("json", "", 1).strip()
                        break
            json_start = text.rfind('{"should_comment"')
            if json_start < 0:
                json_start = text.rfind('{')
            if json_start < 0:
                json_start = text.find('{')
            if json_start >= 0:
                text = text[json_start:]
            brace_count = 0
            end_idx = -1
            for i, ch in enumerate(text):
                if ch == "{":
                    brace_count += 1
                elif ch == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx > 0:
                text = text[:end_idx]
            result = json.loads(text)
            if "should_comment" in result:
                return result
            return {"should_comment": False, "reason": "格式错误", "angle": ""}
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"无法解析 AI 决策响应: {response[:100]}")
            return {"should_comment": False, "reason": "解析失败", "angle": ""}

    def generate_comment(self, content_text: str, existing_comments: str = "",
                         target_comment: str = "",
                         persona: PersonaConfig | None = None) -> str:
        """生成评论文本（支持回复某条评论）"""
        if persona is None:
            persona = self.personas[0]

        if target_comment:
            prompt = REPLY_PROMPT.format(
                content=content_text[:300],
                target_comment=target_comment[:200],
                personality=persona.identity,
                style=persona.style,
            )
        else:
            prompt = COMMENT_PROMPT.format(
                content=content_text[:500],
                existing_comments=existing_comments or "（暂无评论）",
                personality=persona.identity,
                style=persona.style,
                angle="自由发挥",
            )

        comment = self.ai.chat(
            messages=[
                {"role": "system",
                 "content": f"你是抖音用户。人格：{persona.identity}\n风格：{persona.style}\n直接输出评论内容（10-50字），口语化，不要分析、不要思考、不要格式。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=500,
        )

        # 清理 MiniMax 的思考过程
        comment = comment.strip()
        think_close = chr(60) + "/" + "think" + chr(62)
        if think_close in comment:
            parts = comment.split(think_close)
            comment = parts[-1].strip()

        comment = comment.strip('"').strip("'")
        if comment.startswith("评论：") or comment.startswith("评论:"):
            comment = comment[3:].strip()

        if len(comment) < 3:
            return ""

        return comment
