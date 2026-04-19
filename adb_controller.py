"""ADB 控制器 — 连接 MuMu 模拟器，控制抖音操作"""

import subprocess
import time
import random
import os
import logging

logger = logging.getLogger(__name__)


class ADBController:
    def __init__(self, adb_path: str = "adb", host: str = "127.0.0.1", port: int = 7555):
        self.adb_path = adb_path
        self.host = host
        self.port = port
        self.device = f"{host}:{port}"
        self.screen_width = 1080
        self.screen_height = 1920

    def _run(self, cmd: str, timeout: int = 30) -> str:
        full_cmd = f'"{self.adb_path}" -s {self.device} {cmd}'
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
                env={**os.environ, "MSYS_NO_PATHCONV": "1"},
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB 命令超时: {cmd}")
            return ""

    def connect(self) -> bool:
        logger.info(f"连接模拟器 {self.device}...")
        result = subprocess.run(
            f'"{self.adb_path}" connect {self.device}',
            shell=True, capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        logger.info(f"连接结果: {output}")

        if "connected" in output.lower() or "already connected" in output.lower():
            self._get_screen_size()
            return True
        return False

    def _get_screen_size(self):
        output = self._run("shell wm size")
        if "Override size" in output or "Physical size" in output:
            for line in output.split("\n"):
                if "size" in line.lower():
                    size_str = line.split(":")[-1].strip()
                    w, h = size_str.split("x")
                    w, h = int(w), int(h)
                    self.screen_width = min(w, h)
                    self.screen_height = max(w, h)
                    logger.info(f"屏幕分辨率: {self.screen_width}x{self.screen_height}")

    def screenshot(self, save_path: str) -> bool:
        device_path = "/sdcard/douyin_bot_screenshot.png"
        self._run(f"shell screencap -p {device_path}", timeout=10)
        self._run(f"pull {device_path} {save_path}", timeout=15)
        self._run(f"shell rm {device_path}")
        return os.path.exists(save_path)

    def next_video(self):
        """切换到下一个视频（使用 DPAD_DOWN，在 MuMu + 抖音中最可靠）"""
        self._run("shell input keyevent 20")
        logger.debug("切换下一个视频 (DPAD_DOWN)")

    def swipe_up(self, duration: int | None = None):
        """备用滑动方式"""
        w, h = self.screen_width, self.screen_height
        duration = duration or random.randint(300, 600)
        x = w // 2 + random.randint(-50, 50)
        y_start = h * 3 // 4 + random.randint(-30, 30)
        y_end = h // 4 + random.randint(-30, 30)
        self._run(f"shell input swipe {x} {y_start} {x} {y_end} {duration}")

    def tap(self, x: int, y: int, random_offset: int = 5):
        x += random.randint(-random_offset, random_offset)
        y += random.randint(-random_offset, random_offset)
        self._run(f"shell input tap {x} {y}")

    def input_text(self, text: str):
        """通过 MuMu 管理器输入中文文本"""
        import subprocess
        muMu = os.path.join(
            os.path.dirname(self.adb_path), "..", "..", "nx_main", "MuMuManager.exe"
        )
        muMu = os.path.normpath(muMu)
        if not os.path.exists(muMu):
            # fallback: 尝试常见路径
            muMu = r"D:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe"

        try:
            subprocess.run(
                f'"{muMu}" control --vmindex 0 tool cmd --cmd input_text --text "{text}"',
                shell=True, capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"MuMu input_text 失败: {e}")

    def press_back(self):
        self._run("shell input keyevent 4")

    def press_enter(self):
        self._run("shell input keyevent 66")

    def get_current_activity(self) -> str:
        return self._run("shell dumpsys window | grep mCurrentFocus")

    def is_connected(self) -> bool:
        result = subprocess.run(
            f'"{self.adb_path}" devices',
            shell=True, capture_output=True, text=True, timeout=5
        )
        return self.device in result.stdout

    def _scale(self, x: int, y: int) -> tuple[int, int]:
        sx = int(x * self.screen_width / 1080)
        sy = int(y * self.screen_height / 1920)
        return sx, sy

    # 抖音 UI 坐标（基于 1440x2560 实测分辨率）
    def _get_comment_button_pos(self) -> tuple[int, int]:
        """获取评论按钮坐标（通过 UI dump 动态查找）"""
        import xml.etree.ElementTree as ET
        try:
            self._run("shell uiautomator dump /sdcard/ui_btn.xml")
            self._run("pull /sdcard/ui_btn.xml logs/ui_btn.xml")
            with open("logs/ui_btn.xml", "rb") as f:
                root = ET.fromstring(f.read().decode("utf-8"))
            for node in root.iter():
                desc = node.get("content-desc", "")
                if "评论" in desc and "按钮" in desc:
                    bounds = node.get("bounds", "")
                    # Parse bounds=[x1,y1][x2,y2]
                    import re
                    nums = re.findall(r'\d+', bounds)
                    if len(nums) == 4:
                        x = (int(nums[0]) + int(nums[2])) // 2
                        y = (int(nums[1]) + int(nums[3])) // 2
                        return x, y
        except Exception:
            pass
        # Fallback: 默认位置
        return self._scale(990, 1250)

    def tap_comment_button(self):
        """点击右侧评论按钮"""
        x, y = self._get_comment_button_pos()
        self.tap(x, y, random_offset=5)
        time.sleep(2.0)

    def tap_comment_input(self):
        """点击评论输入框（通过 UI dump 动态查找）"""
        import xml.etree.ElementTree as ET
        try:
            self._run("shell uiautomator dump /sdcard/ui_input.xml")
            self._run("pull /sdcard/ui_input.xml logs/ui_input.xml")
            with open("logs/ui_input.xml", "rb") as f:
                root = ET.fromstring(f.read().decode("utf-8"))
            for node in root.iter():
                cls = node.get("class", "")
                text = node.get("text", "")
                desc = node.get("content-desc", "")
                if "EditText" in cls:
                    bounds = node.get("bounds", "")
                    import re
                    nums = re.findall(r'\d+', bounds)
                    if len(nums) == 4:
                        x = (int(nums[0]) + int(nums[2])) // 2
                        y = (int(nums[1]) + int(nums[3])) // 2
                        self.tap(x, y, random_offset=5)
                        time.sleep(1.5)
                        return
        except Exception:
            pass
        # Fallback
        x, y = self._scale(360, 1850)
        self.tap(x, y, random_offset=15)
        time.sleep(1.0)

    def tap_comment_send(self):
        """点击发送按钮"""
        # UI dump 坐标系为 2560x1440（横屏），发送按钮在右下区域
        x = 2474 + random.randint(-8, 8)
        y = 1305 + random.randint(-5, 5)
        self._run(f"shell input tap {x} {y}")
        time.sleep(1.0)

    def tap_reply_button(self, x: int, y: int):
        """点击某条评论的回复按钮"""
        x += random.randint(-3, 3)
        y += random.randint(-3, 3)
        self._run(f"shell input tap {x} {y}")
        time.sleep(1.5)

    def tap_like_button(self):
        """点击点赞按钮"""
        import xml.etree.ElementTree as ET
        try:
            self._run("shell uiautomator dump /sdcard/ui_like.xml")
            self._run("pull /sdcard/ui_like.xml logs/ui_like.xml")
            with open("logs/ui_like.xml", "rb") as f:
                root = ET.fromstring(f.read().decode("utf-8"))
            for node in root.iter():
                desc = node.get("content-desc", "")
                if "未点赞" in desc and "喜欢" in desc:
                    bounds = node.get("bounds", "")
                    import re
                    nums = re.findall(r'\d+', bounds)
                    if len(nums) == 4:
                        x = (int(nums[0]) + int(nums[2])) // 2
                        y = (int(nums[1]) + int(nums[3])) // 2
                        self.tap(x, y, random_offset=3)
                        return
        except Exception:
            pass
        x, y = self._scale(990, 1050)
        self.tap(x, y, random_offset=3)

    def close_keyboard(self):
        self._run("shell input keyevent 111")

    def launch_douyin(self):
        """启动抖音"""
        self._run("shell am start -n com.ss.android.ugc.aweme/.main.MainActivity")
        time.sleep(5)
