# Auto Douyin Bot

抖音 AI 自动浏览评论工具。在 PC 模拟器上运行抖音，AI 模拟不同人设自动刷视频、识别内容、生成评论或回复。

## 功能

- **多人设系统** — 配置多套 AI 人设（身份、语气、话题），按权重随机切换，模拟不同用户
- **话题过滤** — 每个人设可设置关键词，只对感兴趣的话题评论；留空则不限话题
- **智能评论** — AI 自动分析视频内容，找出值得评论的角度，生成犀利但有理有据的评论
- **楼中楼回复** — 读取评论区，找到值得回复的评论，自动点击回复按钮进行针对性回复
- **强制评论** — 连续 3 个视频未评论时自动强制评论，保持活跃度
- **反检测** — 随机延迟、评论频率限制、模拟真人行为

## 快速开始

### 环境要求

- Python 3.10+
- MuMu 模拟器 12（或其他支持 ADB 的安卓模拟器）
- 大模型 API Key（推荐 MiniMax，便宜好用）

### 安装

```bash
git clone https://github.com/cipher-wb/auto-douyin-bot-.git
cd auto-douyin-bot-
pip install -r requirements.txt
cp config.yaml.example config.yaml
```

### 配置

编辑 `config.yaml`，主要需要改两处：

**1. 填入 ADB 路径和模拟器端口**

```yaml
emulator:
  adb_path: "D:/Program Files/Netease/MuMu/nx_device/12.0/shell/adb.exe"
  port: 16384   # MuMu 12 默认端口
```

**2. 填入 AI 模型 API Key**（选一个就行）

```yaml
llm:
  provider: "minimax"   # 或 "glm"
  minimax:
    api_key: "your-api-key"
```

**3. 自定义人设**（可选，已有 2 套预制模板）

```yaml
personas:
  - name: "温暖知性"
    identity: "你是一个温暖知性的朋友..."
    style: "温和理性"
    weight: 2
    topics:
      keywords: ["科学", "物理", "医学"]  # 触发关键词，留空 [] 则不限话题
    strategy:
      comment_probability: 0.4             # 评论概率
```

每个人设可独立配置：
| 字段 | 说明 |
|------|------|
| `identity` | 身份描述，告诉 AI 它是谁 |
| `style` | 评论风格（温和理性/温柔真诚等） |
| `weight` | 权重，数字越大越常被选中 |
| `keywords` | 话题关键词，视频内容包含这些词才触发；留空 `[]` 不限话题 |
| `ai_trigger` | AI 评论角度提示 |
| `target_video` | 是否评论视频（true/false） |
| `target_comments` | 是否回复别人的评论（true/false） |
| `comment_probability` | 评论概率（0.4 = 每个视频 40% 概率尝试评论） |

### 运行

1. 启动 MuMu 模拟器，打开抖音，进入推荐页的视频播放界面
2. 运行：

```bash
python main.py
```

3. 按 `Ctrl+C` 停止

## 工作流程

```
每个视频：
  1. 按权重随机选取一个人设
  2. 提取屏幕文字（uiautomator dump）
  3. AI 分析：找出视频中最值得评论的角度（伪科学/逻辑谬误/虚假内容等）
  4. 打开评论区
     → 读取评论列表，AI 判断是否有人说了值得回复的话
     → 生成犀利评论或楼中楼回复 → 自动输入发送
  5. 连续 3 个视频未评论 → 强制评论（保持活跃度）
  6. 随机等待 → 切换下一个视频
```

## 项目结构

```
├── main.py              # 主入口 + 主循环
├── adb_controller.py    # ADB 操作（截图、点击、输入、滑动）
├── screen_reader.py     # 屏幕文字提取 + 结构化评论解析
├── ai_engine.py         # LLM 统一接口（支持 GLM/MiniMax 切换）
├── personality.py       # 多人设系统 + 评论决策 + 评论生成
├── comment_action.py    # 评论/回复动作执行（含楼中楼）
├── anti_detect.py       # 反检测策略
├── config.yaml          # 配置文件（需自行创建）
└── config.yaml.example  # 配置模板（带详细注释）
```

## 技术要点

- 使用 `uiautomator dump` 提取屏幕文字，无需安装 OCR 库
- 通过 MuMuManager.exe 实现中文输入（ADB 原生不支持中文）
- 动态解析 UI XML 定位按钮坐标，适配不同分辨率
- MiniMax 模型输出含 `<think...>` 思考过程，已做自动剥离
- 评论区每条评论的 `resource-id` 包含 `e60`，回复按钮包含 `wo5`，用于精确定位

## 免责声明

本项目仅供学习和研究用途。使用本工具产生的任何后果由使用者自行承担。
