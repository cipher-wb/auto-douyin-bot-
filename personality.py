"""人格系统 — 管理人格设定、评论决策、评论生成"""

import json
import logging

logger = logging.getLogger(__name__)

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

ANALYSIS_PROMPT = """判断这个视频或评论区是否存在以下问题：
1. 逻辑谬误（以偏概全、偷换概念、滑坡谬误、因果倒置等）
2. 事实错误（明显错误的常识、数据、历史、科学知识等）
3. 价值观问题（歧视、双标、道德绑架、仇富/仇穷等）

视频内容：
{content}

评论区热门评论：
{comments}

人格：{personality}
触发条件：{trigger}

直接输出 JSON（不要思考过程）：
{{"should_comment": true/false, "target": "video或comment", "reason": "一句话说明问题在哪", "target_comment": "如果有问题的评论，复制原文；否则为空", "angle": "反驳角度"}}"""

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

直接输出你的回复（10-50字），口语化，犀利反驳，不要加引号或格式。"""


class PersonalityEngine:
    def __init__(self, ai_engine, personality_config: dict):
        self.ai = ai_engine
        self.description = personality_config.get("description", "一个普通的抖音用户")
        self.style = personality_config.get("comment_style", "温和")
        self.probability = personality_config.get("comment_probability", 0.2)
        self.trigger = personality_config.get("trigger", "")
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            personality=self.description,
            style=self.style,
        )

    def analyze_content(self, content_text: str, comments_text: str = "") -> dict:
        """分析视频内容和评论区，决定是否评论"""
        import random
        if random.random() > self.probability:
            return {"should_comment": False, "reason": "概率过滤", "angle": ""}

        prompt = ANALYSIS_PROMPT.format(
            content=content_text[:500],
            comments=comments_text[:800] if comments_text else "（未读取评论区）",
            personality=self.description,
            trigger=self.trigger or "只回复存在逻辑谬误、事实错误或价值观问题的内容",
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
            # 尝试解析 JSON 响应
            text = response.strip()
            # 去掉 markdown 代码块
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    if "should_comment" in part:
                        text = part.replace("json", "", 1).strip()
                        break
            # MiniMax 会先输出思考过程再输出 JSON
            # 找到包含 should_comment 的 JSON 块
            json_start = text.rfind('{"should_comment"')
            if json_start < 0:
                json_start = text.rfind('{')
            if json_start < 0:
                json_start = text.find('{')
            if json_start >= 0:
                text = text[json_start:]
            # 找到匹配的 } 截断尾部多余文字
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

    def generate_comment(self, content_text: str, existing_comments: str = "", target_comment: str = "") -> str:
        """生成评论文本（支持回复某条评论）"""
        if target_comment:
            # 楼中楼回复模式
            prompt = REPLY_PROMPT.format(
                content=content_text[:300],
                target_comment=target_comment[:200],
                personality=self.description,
                style=self.style,
            )
        else:
            # 普通评论模式
            prompt = COMMENT_PROMPT.format(
                content=content_text[:500],
                existing_comments=existing_comments or "（暂无评论）",
                personality=self.description,
                style=self.style,
                angle="自由发挥",
            )

        comment = self.ai.chat(
            messages=[
                {"role": "system", "content": f"你是抖音用户。人格：{self.description}\n风格：{self.style}\n直接输出评论内容（10-50字），口语化，不要分析、不要思考、不要格式。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=500,
        )

        # 清理 MiniMax 的思考过程（模型会先输出 <think...>思考</think...> 再输出实际内容）
        comment = comment.strip()
        think_close = chr(60) + "/" + "think" + chr(62)  # </think...>
        if think_close in comment:
            # 取最后一个 </think...> 之后的内容
            parts = comment.split(think_close)
            comment = parts[-1].strip()

        comment = comment.strip('"').strip("'")
        if comment.startswith("评论：") or comment.startswith("评论:"):
            comment = comment[3:].strip()

        if len(comment) < 3:
            return ""

        return comment
