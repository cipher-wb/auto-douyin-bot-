"""评论动作模块 — 在抖音中执行评论操作（支持楼中楼）"""

import time
import logging

logger = logging.getLogger(__name__)


class CommentAction:
    def __init__(self, adb_controller, screen_reader):
        self.adb = adb_controller
        self.reader = screen_reader

    def open_comments(self) -> bool:
        """打开评论区"""
        logger.info("打开评论区...")
        self.adb.tap_comment_button()
        time.sleep(2.5)
        content = self.reader.capture_and_analyze()
        if any(kw in content.raw_text for kw in ["说点什么", "写评论", "输入评论", "期待你的评论"]):
            logger.info("评论区已打开")
            return True
        logger.warning("评论区可能未打开，继续尝试...")
        return True

    def read_existing_comments(self) -> str:
        """读取当前页面的已有评论"""
        content = self.reader.capture_and_analyze()
        return content.raw_text

    def post_comment(self, comment_text: str) -> bool:
        """发布一条顶级评论"""
        logger.info(f"准备发布评论: {comment_text}")
        self.adb.tap_comment_input()
        time.sleep(2.0)
        self.adb.input_text(comment_text)
        time.sleep(1.5)
        self.adb.tap_comment_send()
        time.sleep(1.5)
        self.adb.close_keyboard()
        time.sleep(0.5)
        logger.info("评论已发送")
        return True

    def reply_to_comment(self, comment_text: str, reply_x: int, reply_y: int) -> bool:
        """回复某条评论（楼中楼）"""
        logger.info(f"回复评论 @({reply_x},{reply_y}): {comment_text}")
        # 1. 点击该评论的回复按钮
        self.adb.tap_reply_button(reply_x, reply_y)
        time.sleep(2.0)
        # 2. 输入回复
        self.adb.input_text(comment_text)
        time.sleep(1.5)
        # 3. 点击发送
        self.adb.tap_comment_send()
        time.sleep(1.5)
        self.adb.close_keyboard()
        time.sleep(0.5)
        logger.info("回复已发送")
        return True

    def close_comments(self):
        """关闭评论区，返回视频页面"""
        self.adb.press_back()
        time.sleep(1.5)
        self.adb.close_keyboard()
        time.sleep(0.5)

    def execute_comment_flow(self, comment_text: str) -> bool:
        """完整的评论流程（仅顶级评论，兼容旧调用）"""
        try:
            if not self.open_comments():
                return False
            time.sleep(1.0)
            if not self.post_comment(comment_text):
                return False
            time.sleep(2.0)
            self.close_comments()
            for _ in range(3):
                content = self.reader.capture_and_analyze()
                if _is_video_page(content.raw_text):
                    return True
                self.adb.press_back()
                time.sleep(1.5)
            return True
        except Exception as e:
            logger.error(f"评论流程异常: {e}")
            for _ in range(3):
                self.adb.press_back()
                time.sleep(1.0)
            return False

    def execute_smart_comment_flow(self, video_content: str, personality_engine) -> dict:
        """智能评论流程：打开评论区 → 读取评论 → AI判断谬误 → 评论/回复 → 关闭
        返回 {"success": bool, "type": "video"|"comment"|"", "comment": str}
        """
        result = {"success": False, "type": "", "comment": ""}
        try:
            # 1. 打开评论区
            if not self.open_comments():
                return result
            time.sleep(1.0)

            # 2. 读取评论列表（结构化）
            comment_items = self.reader.extract_comments()
            comments_text = ""
            if comment_items:
                lines = []
                for i, c in enumerate(comment_items[:8]):
                    lines.append(f"[{i}] {c.username}: {c.content}")
                comments_text = "\n".join(lines)
                logger.info(f"读取到 {len(comment_items)} 条评论")

            # 3. AI 分析（视频内容 + 评论区）是否有谬误
            decision = personality_engine.analyze_content(video_content, comments_text)
            should = decision.get("should_comment", False)
            target = decision.get("target", "video")
            reason = decision.get("reason", "")
            target_comment_text = decision.get("target_comment", "")

            if not should:
                logger.info(f"AI 跳过: {reason}")
                self.close_comments()
                result["type"] = "skip"
                return result

            logger.info(f"AI 决定{target}评论: {reason}")

            if target == "comment" and target_comment_text and comment_items:
                # 4a. 楼中楼回复：找到匹配的评论
                matched = None
                for c in comment_items:
                    # 模糊匹配：评论内容的前几个字在 target_comment_text 中
                    if c.content and len(c.content) > 2 and c.content[:8] in target_comment_text:
                        matched = c
                        break
                if not matched:
                    # fallback: 用第一条评论
                    matched = comment_items[0]
                    logger.warning(f"未精确匹配评论，使用第一条: {matched.username}")

                reply = personality_engine.generate_comment(
                    video_content, target_comment=matched.content
                )
                if reply and len(reply) >= 3:
                    logger.info(f"回复 @{matched.username}: {reply}")
                    success = self.reply_to_comment(reply, matched.reply_btn_x, matched.reply_btn_y)
                    result = {"success": success, "type": "comment", "comment": reply}
                else:
                    logger.warning("生成的回复太短，跳过")
            else:
                # 4b. 回复视频（顶级评论）
                comment = personality_engine.generate_comment(video_content)
                if comment and len(comment) >= 3:
                    logger.info(f"评论视频: {comment}")
                    success = self.post_comment(comment)
                    result = {"success": success, "type": "video", "comment": comment}
                else:
                    logger.warning("生成的评论太短，跳过")

            time.sleep(2.0)
            self.close_comments()

            # 5. 确保返回视频页面
            for _ in range(3):
                content = self.reader.capture_and_analyze()
                if _is_video_page(content.raw_text):
                    return result
                self.adb.press_back()
                time.sleep(1.5)
            return result
        except Exception as e:
            logger.error(f"智能评论流程异常: {e}", exc_info=True)
            for _ in range(3):
                self.adb.press_back()
                time.sleep(1.0)
            return result


def _is_video_page(text: str) -> bool:
    """判断是否在视频播放页面"""
    keywords = ["未点赞", "喜欢", "评论", "分享", "音乐", "推荐"]
    matches = sum(1 for kw in keywords if kw in text)
    return matches >= 3
