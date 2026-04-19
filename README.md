# Auto Douyin Bot

抖音 AI 自动浏览评论工具。在 PC 模拟器上运行抖音，AI 自动刷视频、识别内容中的逻辑谬误和错误观点，并生成犀利评论或回复。

## 功能

- **AI 驱动浏览** — 自动识别视频内容，判断是否值得评论
- **谬误检测** — 只回复存在逻辑谬误、事实错误或价值观问题的视频/评论
- **楼中楼回复** — 检测评论区中的错误言论，自动点击回复按钮进行针对性反驳
- **人格系统** — 可自定义 AI 人设和评论风格（暴躁老哥、温和理性等）
- **反检测** — 随机延迟、频率限制、模拟人类行为
- **多模型支持** — 支持 GLM、MiniMax 等 OpenAI 兼容 API

## 工作流程

```
1. 截取屏幕 → uiautomator 提取文字
2. AI 分析视频内容是否有谬误
3. 若值得评论 → 打开评论区
4. 读取评论列表 → AI 判断评论区是否有人说错话
5. 生成评论/回复 → 自动输入并发送
6. 随机等待 → 切换下一个视频
```

## 环境要求

- Python 3.10+
- MuMu 模拟器 12（或其他支持 ADB 的安卓模拟器）
- 大模型 API Key（MiniMax / 智谱 GLM）

## 安装

```bash
git clone https://github.com/cipher-wb/auto-douyin-bot-.git
cd auto-douyin-bot-
pip install -r requirements.txt
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入 ADB 路径和 API Key
```

## 配置

编辑 `config.yaml`：

```yaml
emulator:
  adb_path: "D:/Program Files/Netease/MuMu/nx_device/12.0/shell/adb.exe"
  port: 16384

llm:
  provider: "minimax"
  minimax:
    api_key: "your-api-key"

personality:
  description: "你是一个暴躁老哥，嘴毒心热，对逻辑错误零容忍"
  comment_style: "犀利毒舌"
  comment_probability: 0.25
```

## 使用

1. 启动 MuMu 模拟器，打开抖音，进入推荐页视频播放界面
2. 运行：

```bash
python main.py
```

3. 按 `Ctrl+C` 停止

## 项目结构

```
├── main.py              # 主入口 + 主循环
├── adb_controller.py    # ADB 操作（截图、点击、输入、滑动）
├── screen_reader.py     # 屏幕文字提取 + 结构化评论解析
├── ai_engine.py         # LLM 统一接口（支持多模型切换）
├── personality.py       # 人格系统 + 谬误检测 + 评论生成
├── comment_action.py    # 评论/回复动作执行（含楼中楼）
├── anti_detect.py       # 反检测策略
├── config.yaml          # 配置文件（需自行创建）
└── config.yaml.example  # 配置模板
```

## 技术要点

- 使用 `uiautomator dump` 提取屏幕文字，无需 OCR 库
- 通过 MuMuManager.exe 实现中文输入（ADB 原生不支持中文）
- 动态解析 UI XML 定位按钮坐标，适配不同分辨率
- MiniMax 模型输出含 `<think...>` 思考过程，已做自动剥离处理
- 评论区每条评论的 `resource-id` 包含 `e60`，回复按钮包含 `wo5`，用于精确定位

## 免责声明

本项目仅供学习和研究用途。使用本工具产生的任何后果由使用者自行承担。
