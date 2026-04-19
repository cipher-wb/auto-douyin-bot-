"""屏幕识别模块 — 使用 ADB uiautomator 提取界面文字"""

import os
import re
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScreenContent:
    raw_text: str
    lines: list[str]
    screenshot_path: str


@dataclass
class CommentItem:
    username: str
    content: str
    reply_btn_x: int   # "回复"按钮中心 x
    reply_btn_y: int   # "回复"按钮中心 y
    is_author: bool


class ScreenReader:
    def __init__(self, adb_controller, temp_dir: str = "./logs"):
        self.adb = adb_controller
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        self._screenshot_count = 0

    def capture_screenshot(self) -> str:
        """截图保存到本地（供视觉分析用）"""
        self._screenshot_count += 1
        path = os.path.join(self.temp_dir, f"screen_{self._screenshot_count}.png")
        if self.adb.screenshot(path):
            return path
        return ""

    def _dump_ui(self) -> str:
        """通过 uiautomator dump 提取界面 XML"""
        device_path = "/sdcard/douyin_bot_ui.xml"
        local_path = os.path.join(self.temp_dir, "ui_dump.xml")

        self.adb._run(f"shell uiautomator dump {device_path}", timeout=10)
        self.adb._run(f"pull {device_path} {local_path}", timeout=15)
        self.adb._run(f"shell rm {device_path}")

        if not os.path.exists(local_path):
            return ""

        try:
            with open(local_path, "rb") as f:
                return f.read().decode("utf-8")
        except Exception as e:
            logger.error(f"读取 UI dump 失败: {e}")
            return ""

    def extract_text_from_xml(self, xml_str: str) -> list[str]:
        """从 UI XML 中提取所有文字"""
        texts = []
        try:
            root = ET.fromstring(xml_str)
            for node in root.iter():
                text = node.get("text", "").strip()
                desc = node.get("content-desc", "").strip()
                if text:
                    texts.append(text)
                if desc and desc != text:
                    texts.append(desc)
        except ET.ParseError as e:
            logger.error(f"XML 解析失败: {e}")
        return texts

    def capture_and_analyze(self) -> ScreenContent:
        """提取当前屏幕的文字内容"""
        xml_str = self._dump_ui()
        lines = self.extract_text_from_xml(xml_str) if xml_str else []
        raw_text = "\n".join(lines)
        screenshot_path = self.capture_screenshot()

        return ScreenContent(
            raw_text=raw_text,
            lines=lines,
            screenshot_path=screenshot_path,
        )

    def extract_comments(self) -> list[CommentItem]:
        """从评论区 UI dump 中提取结构化评论列表"""
        xml_str = self._dump_ui()
        if not xml_str:
            return []

        comments = []
        try:
            root = ET.fromstring(xml_str)
            # 每条评论容器 resource-id 包含 "e60"
            for node in root.iter():
                rid = node.get("resource-id", "")
                if "e60" not in rid:
                    continue
                desc = node.get("content-desc", "")
                if not desc:
                    continue
                # 格式: "用户名,评论文本,时间, · 地区,回复 按钮,作者赞过"
                is_author = "作者赞过" in desc or "作者" in desc.split(",")[-1] if "," in desc else False
                # 解析用户名和内容：取第一个逗号前为用户名，之后到第一个时间标记前为内容
                parts = desc.split(",")
                username = parts[0].strip() if parts else ""
                # 找到回复按钮的坐标（在当前节点的子树中找 resource-id 包含 wo5 的）
                reply_x, reply_y = 0, 0
                for child in node.iter():
                    child_rid = child.get("resource-id", "")
                    child_text = child.get("text", "").strip()
                    if child_text == "回复" and "wo5" in child_rid:
                        bounds = child.get("bounds", "")
                        nums = re.findall(r'\d+', bounds)
                        if len(nums) == 4:
                            reply_x = (int(nums[0]) + int(nums[2])) // 2
                            reply_y = (int(nums[1]) + int(nums[3])) // 2
                        break
                if reply_x == 0:
                    continue
                # 提取评论文本（去掉用户名、时间、地区等）
                # content-desc 格式: "用户名,评论文本,时间, · 地区,回复 按钮,作者赞过"
                content = ",".join(parts[1:]) if len(parts) > 1 else ""
                # 去掉尾部 "回复 按钮,作者赞过" 等元信息
                content = re.split(r',\s*\d+天前|\d+小时前|\d+分钟前|\d+周前|昨天|今天|\d{2}-\d{2}', content)[0].strip()
                if content.endswith(","):
                    content = content[:-1].strip()

                comments.append(CommentItem(
                    username=username,
                    content=content,
                    reply_btn_x=reply_x,
                    reply_btn_y=reply_y,
                    is_author=is_author,
                ))
        except ET.ParseError as e:
            logger.error(f"评论 XML 解析失败: {e}")
        return comments
