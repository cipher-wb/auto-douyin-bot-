"""抖音 AI 自动浏览评论工具 — 主程序"""

import sys
import os
import re
import time
import signal
import logging
import yaml

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.logging import RichHandler
from rich import print as rprint

from adb_controller import ADBController
from screen_reader import ScreenReader
from ai_engine import AIEngine
from personality import PersonalityEngine
from comment_action import CommentAction
from anti_detect import AntiDetect

# Windows GBK 编码兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(force_terminal=True)
running = True


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/douyin_bot.log", encoding="utf-8"),
        ],
    )


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if not os.path.exists(config_path):
        console.print("[red]未找到 config.yaml[/red]")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def signal_handler(sig, frame):
    global running
    console.print("\n[yellow]收到退出信号，正在停止...[/yellow]")
    running = False


def print_banner():
    console.print(Panel("抖音 AI 自动浏览评论工具 v1.0", style="bold cyan"))


def print_stats(anti: AntiDetect):
    stats = anti.get_stats()
    table = Table(title="运行统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")
    for k, v in stats.items():
        table.add_row(k, str(v))
    console.print(table)


def clean_video_text(raw_text: str) -> str:
    """清理 UI 元数据，只保留视频内容文字供 AI 分析"""
    UI_NOISE = ["未点赞", "喜欢", "评论", "收藏", "分享", "按钮", "拍同款",
                "音乐", "发弹幕", "未选中", "听抖音", "听合集", "创建的原声"]
    parts = raw_text.replace("\n", " | ").split("|")
    meaningful = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p in ("视频", "关注"):
            continue
        if any(kw in p for kw in UI_NOISE):
            continue
        if re.match(r'^[\d.]+万?$', p):
            continue
        meaningful.append(p)
    return " ".join(meaningful)


def is_on_video_page(content_text: str) -> bool:
    """判断当前是否在视频播放页面"""
    video_keywords = ["未点赞", "喜欢", "评论", "分享", "音乐", "推荐"]
    matches = sum(1 for kw in video_keywords if kw in content_text)
    return matches >= 3


def is_live_stream(content_text: str) -> bool:
    """判断当前是否进入了直播间"""
    live_keywords = ["直播间", "直播中", "关注主播", "主播", "礼物"]
    matches = sum(1 for kw in live_keywords if kw in content_text)
    return matches >= 2


def recover_to_video_page(adb, reader, console):
    """尝试恢复到视频播放页面"""
    for attempt in range(5):
        content = reader.capture_and_analyze()
        if is_on_video_page(content.raw_text):
            console.print("[green]已回到视频页面[/green]")
            return True
        if is_live_stream(content.raw_text):
            console.print("[yellow]进入了直播间，按返回退出[/yellow]")
        else:
            console.print(f"[yellow]不在视频页面 (尝试 {attempt+1}/5)，按返回...[/yellow]")
        adb.press_back()
        time.sleep(2)
    # 恢复失败，重启抖音
    console.print("[red]恢复失败，重启抖音...[/red]")
    adb.press_back()
    time.sleep(1)
    adb.press_back()
    time.sleep(1)
    adb.launch_douyin()
    time.sleep(5)
    return False


def main():
    print_banner()
    setup_logging()
    logger = logging.getLogger("main")
    signal.signal(signal.SIGINT, signal_handler)

    config = load_config()
    logger.info("配置加载完成")

    emu_cfg = config.get("emulator", {})
    adb = ADBController(
        adb_path=emu_cfg.get("adb_path", "adb"),
        host=emu_cfg.get("host", "127.0.0.1"),
        port=emu_cfg.get("port", 7555),
    )

    ai = AIEngine(config.get("llm", {}))
    personality = PersonalityEngine(ai, config)
    reader = ScreenReader(adb, temp_dir="./logs")
    commenter = CommentAction(adb, reader)
    anti = AntiDetect(config.get("behavior", {}))

    # 连接模拟器
    console.print("[cyan]正在连接 MuMu 模拟器...[/cyan]")
    if not adb.connect():
        console.print("[red]连接失败！[/red]")
        sys.exit(1)
    console.print(f"[green]连接成功[/green] 分辨率: {adb.screen_width}x{adb.screen_height}")

    # 显示配置
    persona_names = ", ".join(f"{p.name}(w{p.weight})" for p in personality.personas)
    console.print(f"[bold]人设:[/bold] {persona_names}")
    console.print(f"[bold]模型:[/bold] {ai._model}")
    console.print("[dim]按 Ctrl+C 停止\n[/dim]")

    time.sleep(2)

    last_content_hash = ""
    videos_since_last_comment = 0  # 距上次评论刷了几个视频

    while running:
        try:
            anti.record_video()

            # 1. 提取屏幕内容
            content = reader.capture_and_analyze()

            if not content.raw_text:
                console.print("[yellow]未识别到内容，尝试恢复...[/yellow]")
                recover_to_video_page(adb, reader, console)
                continue

            # 检查是否进入直播间，自动退出
            if is_live_stream(content.raw_text) and not is_on_video_page(content.raw_text):
                console.print("[yellow]进入了直播间，退出...[/yellow]")
                adb.press_back()
                time.sleep(2)
                continue

            # 检查是否在视频页面
            if not is_on_video_page(content.raw_text):
                console.print("[yellow]不在视频页面，尝试恢复...[/yellow]")
                recover_to_video_page(adb, reader, console)
                continue

            # 检查视频是否切换了（避免重复分析同一视频）
            content_hash = hash(content.raw_text[:200])
            if content_hash == last_content_hash:
                console.print("[dim]同一视频，强制切换[/dim]")
                adb.next_video()
                time.sleep(2)
                adb.next_video()
                time.sleep(3)
                continue
            last_content_hash = content_hash

            # 显示识别到的内容
            display_text = content.raw_text[:120].replace("\n", " | ")
            console.print(f"[cyan]内容:[/cyan] {display_text}")

            # 2. 清理 UI 噪音，提取纯内容（供 AI 使用）
            clean_text = clean_video_text(content.raw_text)
            if clean_text:
                console.print(f"[dim]AI内容: {clean_text[:80]}[/dim]")

            # 3. 内容分类 + 自动选择人设
            content_type = personality.classify_content(clean_text or content.raw_text)
            persona = personality.select_persona_by_type(content_type)
            console.print(f"[bold blue]── 视频 #{anti.stats['videos_watched']} [{persona.name}] ({content_type}) ──[/bold blue]")

            # 3. 美女擦边视频自动点赞
            if content_type == "beauty" and "未点赞" in content.raw_text:
                adb.tap_like_button()
                anti.record_like()
                console.print("[magenta]♥ 美女视频自动点赞[/magenta]")

            # 4. 评论流程
            videos_since_last_comment += 1
            force_comment = videos_since_last_comment >= 3
            ai_text = clean_text or content.raw_text  # AI 用清理后的文本

            if not anti.can_comment():
                console.print("[dim]评论频率限制，跳过评论[/dim]")
            elif force_comment:
                # 强制评论：跳过 AI 判断，直接生成并发布
                console.print("[yellow]已刷3条未评论，强制评论[/yellow]")
                time.sleep(anti.comment_delay())
                comment = personality.generate_comment(ai_text, persona=persona)
                if comment and len(comment) >= 3:
                    console.print(f"[bold green]评论: {comment}[/bold green]")
                    success = commenter.execute_comment_flow(comment)
                    if success:
                        anti.record_comment()
                        videos_since_last_comment = 0
                        console.print("[green]+ 评论成功[/green]")
                    recover_to_video_page(adb, reader, console)
                else:
                    console.print("[dim]生成的评论太短，跳过[/dim]")
            else:
                # 智能评论：AI 决定评论角度并执行
                time.sleep(anti.comment_delay())
                result = commenter.execute_smart_comment_flow(ai_text, personality, persona)
                if result["success"]:
                    anti.record_comment()
                    videos_since_last_comment = 0
                    ctype = "回复评论" if result["type"] == "comment" else "评论视频"
                    console.print(f"[green]+ {ctype}成功: {result['comment']}[/green]")
                    recover_to_video_page(adb, reader, console)
                elif result["type"] == "skip":
                    console.print("[dim]人设策略限制，跳过[/dim]")
                else:
                    console.print("[red]x 评论失败[/red]")
                    recover_to_video_page(adb, reader, console)

            # 5. 随机点赞
            if anti.should_like():
                adb.tap_like_button()
                anti.record_like()
                console.print("[dim]+ 点赞[/dim]")

            # 6. 等待 + 切换视频
            delay = anti.swipe_delay()
            console.print(f"[dim]等待 {delay:.1f}s 后切换...[/dim]\n")
            time.sleep(delay)
            adb.next_video()
            time.sleep(2)  # 等待新视频加载

        except Exception as e:
            logger.error(f"主循环异常: {e}", exc_info=True)
            console.print(f"[red]异常: {e}[/red]")
            time.sleep(5)

    console.print("\n[bold]程序已停止[/bold]")
    print_stats(anti)


if __name__ == "__main__":
    main()
