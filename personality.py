"""人格系统 — 多人设管理、评论决策与生成"""

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


ANALYSIS_PROMPT = """分析这个抖音视频，找出最值得犀利评论的点。

视频内容：
{content}

评论区热门评论：
{comments}

人格：{personality}
触发条件：{trigger}

重点关注以下问题：
1. 伪科学和虚假医学（无证据的偏方、老中医的荒谬理论、缺乏双盲实验的疗法、把个例当规律的骗术）
2. 逻辑谬误（以偏概全、偷换概念、因果倒置、滑坡谬误、稻草人谬误）
3. 虚假内容（编造故事、伪造数据、摆拍假装真实）
4. 陈腐套路（贩卖焦虑、毒鸡汤、成功学、标题党、无脑跟风）

直接输出 JSON（不要思考过程）：
{{"target": "video或comment", "angle": "具体什么问题（一个短句，如'以偏概全'/'没有RCT数据'/'偏方害人'等）", "target_comment": "如果要回复某条评论，复制原文；否则为空"}}"""

COMMENT_PROMPT = """针对这个视频的问题生成一条犀利评论。

视频内容：
{content}

已有热门评论：
{existing_comments}

我的人格：{personality}
评论风格：{style}
要揭穿的问题：{angle}

要求：
- 一针见血，直戳要害，不要废话
- 嘴臭但逻辑无懈可击，骂人不带脏字但字字扎心
- 如果涉及医学/科学问题，用循证医学数据或科学事实碾压
- 用反问、讽刺、类比等手法让评论有传播力
- 像真实抖音用户说的，口语化，不要书面语
- 15-50字

直接输出评论内容，不要加引号或任何额外格式。"""

REPLY_PROMPT = """你正在回复抖音上一条有问题的评论。

视频内容：{content}
对方评论：{target_comment}
我的人格：{personality}
评论风格：{style}

要求：
- 嘴臭+逻辑无懈可击，骂人不带脏字但让人哑口无言
- 如果涉及医学/科学问题，用循证医学数据碾压对方
- 用反问或讽刺揭示对方逻辑的荒谬
- 口语化，像真实抖音用户
- 10-50字

直接输出你的回复，不要加引号或格式。"""


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

    def analyze_content(self, content_text: str, comments_text: str = "",
                        persona: PersonaConfig | None = None) -> dict:
        """分析视频内容，找出最值得犀利评论的点"""
        if persona is None:
            persona = self.personas[0]

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
                    if "target" in part:
                        text = part.replace("json", "", 1).strip()
                        break
            json_start = text.rfind('{"target"')
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
            # 补全缺失字段
            result.setdefault("target", "video")
            result.setdefault("angle", "自由发挥")
            result.setdefault("target_comment", "")
            return result
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"无法解析 AI 决策响应: {response[:100]}")
            return {"target": "video", "angle": "自由发挥", "target_comment": ""}

    def generate_comment(self, content_text: str, existing_comments: str = "",
                         target_comment: str = "",
                         persona: PersonaConfig | None = None,
                         angle: str = "") -> str:
        """生成犀利评论文本"""
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
                angle=angle or "自由发挥",
            )

        comment = self.ai.chat(
            messages=[
                {"role": "system",
                 "content": f"你是{persona.identity}\n风格：{persona.style}\n嘴臭但逻辑无懈可击，骂人不带脏字但字字扎心。涉及医学/科学就用循证数据碾压。直接输出一条犀利评论（15-50字），口语化，不要分析过程、不要格式。"},
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
