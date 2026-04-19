"""人格系统 — 三人设管理、内容分类、评论决策与生成"""

import json
import random
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 内容分类关键词
WARM_KEYWORDS = [
    "猫", "狗", "小猫", "小狗", "萌娃", "宝宝", "可爱", "风景", "日落", "夕阳",
    "海边", "手工", "美食", "治愈", "温暖", "感动", "花", "小动物", "宠物",
    "奶猫", "奶狗", "兔子", "仓鼠", "樱花", "彩虹", "星空", "猫咪", "狗狗",
    "动物", "花园", "甜品", "蛋糕", "面包", "亲子", "满月", "森林", "瀑布",
    "草原", "湖泊", "雪山", "萤火虫", "向日葵", "薰衣草",
]

AGGRESSIVE_KEYWORDS = [
    "彩礼", "神药", "偏方", "秘方", "迷信", "反智", "女拳", "男拳",
    "性别对立", "伪科学", "包治百病", "根治", "祖传秘方",
    "贩卖焦虑", "毒鸡汤", "成功学", "阴谋论", "以偏概全", "偷换概念",
    "不转不是", "必买", "震惊",
]

BEAUTY_KEYWORDS = [
    "擦边", "热舞", "辣妹", "黑丝", "丝袜", "比基尼", "泳装", "美腿",
    "吊带", "一字马", "下腰", "扭腰", "美背", "蜜桃臀", "马甲线",
]


@dataclass
class PersonaConfig:
    name: str
    identity: str
    style: str
    persona_type: str = "rational"
    weight: int = 1
    keywords: list[str] = field(default_factory=list)
    ai_trigger: str = "自由发挥"
    target_video: bool = True
    target_comments: bool = True
    comment_probability: float = 0.25


ANALYSIS_PROMPT = """分析这个抖音视频，找出最值得评论的角度。

视频内容：
{content}

评论区热门评论：
{comments}

人格：{personality}
触发条件：{trigger}

直接输出 JSON（不要思考过程）：
{{"target": "video或comment", "angle": "具体什么角度（短句）", "target_comment": "如果要回复某条评论，复制原文；否则为空"}}"""

# --- 三种人设的评论生成 prompt ---

WARM_COMMENT_PROMPT = """针对这个视频写一条温暖治愈的评论。

视频内容：
{content}

我的人格：{personality}
评论风格：{style}
评论角度：{angle}

参考案例（模仿语气，不要照抄）：
- 「哎呀妈呀这也太犯规了吧……一团小毛球直接把我心偷走了🥹 谁家宝贝啊，我想偷偷抱回家养着～❤️」
- 「卧槽这地方像从画里走出来的一样……人站在里面会不会觉得自己也变成仙了😭 好想背个包就去」
- 「这画面太戳人了……小朋友的爱真的好干净啊🥹 看得我眼睛有点酸」

要求：
- 温柔治愈，像邻家朋友在哄你开心
- 句尾爱拖长音～，多用❤️😍🥹😭
- 语言故意不规整、口语化、偶尔抽象比喻
- 偶尔爆粗口反差萌（如"卧槽太可爱了"）
- 15-50字

直接输出评论内容，不要加引号或任何额外格式。"""

AGGRESSIVE_COMMENT_PROMPT = """针对这个视频的问题生成一条犀利评论。

视频内容：
{content}

我的人格：{personality}
评论风格：{style}
要揭穿的问题：{angle}

参考案例（模仿语气，不要照抄）：
- 「哈哈哈哈哈30万还嫌少？醒醒吧兄弟，你这不叫娶媳妇，叫花钱买儿媳妇啊😂 彩礼本质就是把婚姻变成交易，逻辑上就他妈说不通」
- 「又来了又来了，宝贝们醒醒吧😤 现代医学是双盲实验+数据堆出来的，你的是祖传秘方+口口相传？逻辑呢？证据呢？」
- 「尊重？尊重是拿钱砸出来的？那我建议你直接去菜市场买个男人得了🤡 逻辑闭环都给你整漏了」

要求：
- 嘴臭但逻辑无懈可击，骂人不带脏字但字字扎心
- 带"哈哈哈""醒醒吧""哥们儿""宝贝""逻辑呢？"口癖
- 用反问、讽刺、类比让评论有传播力
- 涉及医学/科学问题用数据碾压
- 表情包用😂😤🤡
- 15-50字，口语化

直接输出评论内容，不要加引号或任何额外格式。"""

RATIONAL_COMMENT_PROMPT = """针对这个视频写一条理性分析的评论。

视频内容：
{content}

我的人格：{personality}
评论风格：{style}
评论角度：{angle}

参考案例（模仿语气，不要照抄）：
- 「其实吧，这事儿两头都难。年轻人压力确实大，但光骂也没用。从数据看，供应少+投资属性太强才是主因……现实就这么操蛋，但总得往前走🤔」
- 「我个人觉得各有长处，关键不是站队，而是理性点，命是自己的。」
- 「这事儿性质确实恶劣，该罚就罚。但也别一棍子打死整个行业……监管跟得上才能真正解决👍」

要求：
- 冷静客观，把事情掰开揉碎讲清楚
- 用"其实""从数据看""我个人觉得"开头
- 语气平但有力量，不偏激也不圣母
- 偶尔加🤔👍
- 15-50字，口语化但有条理

直接输出评论内容，不要加引号或任何额外格式。"""

# --- 三种人设的回复 prompt ---

WARM_REPLY_PROMPT = """你正在回复抖音上一条评论，用温柔的方式。

视频内容：{content}
对方评论：{target_comment}
我的人格：{personality}
评论风格：{style}

要求：温柔回应，用～❤️😍等，口语化，10-50字
直接输出回复，不要加引号或格式。"""

AGGRESSIVE_REPLY_PROMPT = """你正在回复抖音上一条有问题的评论，犀利回击。

视频内容：{content}
对方评论：{target_comment}
我的人格：{personality}
评论风格：{style}

要求：嘴臭+逻辑无懈可击，用反问讽刺揭示荒谬，涉及科学用数据碾压，口语化，10-50字
直接输出回复，不要加引号或格式。"""

RATIONAL_REPLY_PROMPT = """你正在回复抖音上一条评论，理性讨论。

视频内容：{content}
对方评论：{target_comment}
我的人格：{personality}
评论风格：{style}

要求：冷静回应，讲道理摆事实，不偏激不圣母，口语化但有条理，10-50字
直接输出回复，不要加引号或格式。"""

# --- 人设对应的系统提示 ---
PERSONA_SYSTEM = {
    "warm": "你是{identity}\n风格：{style}\n说话不规整、口语化、带表情包，偶尔爆粗口反差萌。直接输出一条评论（15-50字），不要分析过程、不要格式。",
    "aggressive": "你是{identity}\n风格：{style}\n嘴臭但逻辑无懈可击，骂人不带脏字但字字扎心。涉及医学/科学就用循证数据碾压。直接输出一条犀利评论（15-50字），口语化，不要分析过程、不要格式。",
    "rational": "你是{identity}\n风格：{style}\n冷静客观，把事情掰开揉碎讲清楚。不偏激不圣母。直接输出一条理性评论（15-50字），口语化，不要分析过程、不要格式。",
}


class PersonalityEngine:
    def __init__(self, ai_engine, config: dict):
        self.ai = ai_engine
        self.personas: list[PersonaConfig] = self._parse_personas(config)

    def _parse_personas(self, config: dict) -> list[PersonaConfig]:
        if "personas" in config:
            return [self._build_persona(p) for p in config["personas"]]
        old = config.get("personality", config)
        return [self._build_persona_from_legacy(old)]

    def _build_persona(self, p: dict) -> PersonaConfig:
        topics = p.get("topics", {})
        strategy = p.get("strategy", {})
        return PersonaConfig(
            name=p.get("name", "未命名"),
            identity=p.get("identity", "一个普通的抖音用户"),
            style=p.get("style", "温和"),
            persona_type=p.get("type", "rational"),
            weight=p.get("weight", 1),
            keywords=topics.get("keywords", []) if isinstance(topics, dict) else [],
            ai_trigger=topics.get("ai_trigger", "自由发挥") if isinstance(topics, dict) else "自由发挥",
            target_video=strategy.get("target_video", True),
            target_comments=strategy.get("target_comments", True),
            comment_probability=strategy.get("comment_probability", 0.25),
        )

    def _build_persona_from_legacy(self, old: dict) -> PersonaConfig:
        return PersonaConfig(
            name="默认人设",
            identity=old.get("description", "一个普通的抖音用户"),
            style=old.get("comment_style", "温和"),
            persona_type="rational",
            weight=1,
            keywords=[],
            ai_trigger=old.get("trigger", "自由发挥"),
            comment_probability=old.get("comment_probability", 0.2),
        )

    def classify_content(self, content_text: str) -> str:
        """基于关键词的内容分类，返回 warm/aggressive/beauty/rational"""
        if any(kw in content_text for kw in WARM_KEYWORDS):
            return "warm"
        if any(kw in content_text for kw in BEAUTY_KEYWORDS):
            return "beauty"
        if any(kw in content_text for kw in AGGRESSIVE_KEYWORDS):
            return "aggressive"
        return "rational"

    def select_persona_by_type(self, content_type: str) -> PersonaConfig:
        """根据内容类型选择人设，beauty 映射到 warm"""
        search_type = "warm" if content_type == "beauty" else content_type
        for p in self.personas:
            if p.persona_type == search_type:
                return p
        for p in self.personas:
            if p.persona_type == "rational":
                return p
        return self.personas[0]

    def pick_persona(self) -> PersonaConfig:
        """按权重随机选取人设（兼容旧调用）"""
        if len(self.personas) == 1:
            return self.personas[0]
        weights = [p.weight for p in self.personas]
        return random.choices(self.personas, weights=weights, k=1)[0]

    def analyze_content(self, content_text: str, comments_text: str = "",
                        persona: PersonaConfig | None = None) -> dict:
        """分析视频内容，找出最值得评论的角度"""
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
            result.setdefault("target", "video")
            result.setdefault("angle", "自由发挥")
            result.setdefault("target_comment", "")
            return result
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"无法解析 AI 决策响应: {response[:100]}")
            return {"target": "video", "angle": "自由发挥", "target_comment": ""}

    def _get_comment_prompt(self, persona: PersonaConfig) -> str:
        if persona.persona_type == "warm":
            return WARM_COMMENT_PROMPT
        elif persona.persona_type == "aggressive":
            return AGGRESSIVE_COMMENT_PROMPT
        return RATIONAL_COMMENT_PROMPT

    def _get_reply_prompt(self, persona: PersonaConfig) -> str:
        if persona.persona_type == "warm":
            return WARM_REPLY_PROMPT
        elif persona.persona_type == "aggressive":
            return AGGRESSIVE_REPLY_PROMPT
        return RATIONAL_REPLY_PROMPT

    def _get_system_prompt(self, persona: PersonaConfig) -> str:
        template = PERSONA_SYSTEM.get(persona.persona_type, PERSONA_SYSTEM["rational"])
        return template.format(identity=persona.identity, style=persona.style)

    def generate_comment(self, content_text: str, existing_comments: str = "",
                         target_comment: str = "",
                         persona: PersonaConfig | None = None,
                         angle: str = "") -> str:
        """生成评论文本"""
        if persona is None:
            persona = self.personas[0]

        if target_comment:
            prompt = self._get_reply_prompt(persona).format(
                content=content_text[:300],
                target_comment=target_comment[:200],
                personality=persona.identity,
                style=persona.style,
            )
        else:
            prompt = self._get_comment_prompt(persona).format(
                content=content_text[:500],
                personality=persona.identity,
                style=persona.style,
                angle=angle or "自由发挥",
            )

        comment = self.ai.chat(
            messages=[
                {"role": "system", "content": self._get_system_prompt(persona)},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=500,
        )

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
