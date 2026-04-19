"""反检测策略 — 随机延迟、人类行为模拟、频率限制"""

import time
import random
import logging
from collections import deque

logger = logging.getLogger(__name__)


class AntiDetect:
    def __init__(self, behavior_config: dict):
        self.swipe_min = behavior_config.get("swipe_interval_min", 3)
        self.swipe_max = behavior_config.get("swipe_interval_max", 10)
        self.max_comments_per_hour = behavior_config.get("max_comments_per_hour", 8)
        self.like_probability = behavior_config.get("like_probability", 0.15)
        self.comment_delay_min = behavior_config.get("comment_delay_min", 3)
        self.comment_delay_max = behavior_config.get("comment_delay_max", 8)

        # 评论时间记录（用于频率限制）
        self._comment_timestamps: deque = deque()
        # 统计
        self.stats = {
            "videos_watched": 0,
            "comments_posted": 0,
            "likes_given": 0,
            "start_time": time.time(),
        }

    def swipe_delay(self) -> float:
        """返回观看视频的等待时间（秒）"""
        delay = random.uniform(self.swipe_min, self.swipe_max)
        logger.debug(f"观看等待: {delay:.1f}s")
        return delay

    def comment_delay(self) -> float:
        """返回评论前的等待时间"""
        delay = random.uniform(self.comment_delay_min, self.comment_delay_max)
        logger.debug(f"评论前等待: {delay:.1f}s")
        return delay

    def can_comment(self) -> bool:
        """检查是否可以评论（频率限制）"""
        now = time.time()
        # 清理一小时前的记录
        while self._comment_timestamps and now - self._comment_timestamps[0] > 3600:
            self._comment_timestamps.popleft()

        if len(self._comment_timestamps) >= self.max_comments_per_hour:
            logger.info("已达到每小时评论上限，跳过评论")
            return False
        return True

    def record_comment(self):
        """记录一次评论"""
        self._comment_timestamps.append(time.time())
        self.stats["comments_posted"] += 1

    def should_like(self) -> bool:
        """是否应该点赞"""
        return random.random() < self.like_probability

    def record_like(self):
        self.stats["likes_given"] += 1

    def record_video(self):
        self.stats["videos_watched"] += 1

    def random_pause(self):
        """随机短暂停顿，模拟人类阅读/思考"""
        pause = random.uniform(0.5, 2.0)
        time.sleep(pause)

    def get_stats(self) -> dict:
        """获取运行统计"""
        elapsed = time.time() - self.stats["start_time"]
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        return {
            "运行时间": f"{mins}分{secs}秒",
            "浏览视频": self.stats["videos_watched"],
            "发布评论": self.stats["comments_posted"],
            "点赞数": self.stats["likes_given"],
            "本小时已评论": len(self._comment_timestamps),
        }
