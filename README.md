# QQbot-tts
用于串联本地tts模型与大语言模型到qqbot
# QQ群语音机器人 

一个纯Python实现的QQ群语音机器人，@它就能用洛天依（或其他音色）的语音回复你。

## 功能

- 监听QQ群@消息和私聊
- **默认模式**：@机器人 → Ollama(AI对话) → CosyVoice2语音克隆 → 语音回复
- **/生成 模式**：@机器人 `/生成 文字内容` → 跳过AI，直接语音克隆发送
- 自动重连、心跳保活
- 支持自定义音色（替换参考音频即可）

## 架构

```
QQ群消息 → WebSocket监听 → strip @mention
  ├─ /生成 开头 → 直接TTS
  └─ 普通消息 → Ollama(qwen3:14b + persona) → TTS
                 └─ Ollama超时/空回复 → 兜底文案

TTS: CosyVoice2 (subprocess, PYTHONPATH="" 隔离)
语音上传: QQ Bot 小文件直传 API
```

## 依赖

### 必须
- **Python 3.10+**（推荐3.11）
- **CosyVoice2** — 语音克隆引擎
- **Ollama** — 本地大模型推理
- **ffmpeg** — 音频格式转换（mp3→wav等）

### Python包
```bash
pip install httpx aiohttp
```

### QQ Bot
- 需要到 [QQ开放平台](https://q.qq.com) 注册Bot，获取 AppID + ClientSecret
- Bot需要公网IP或内网穿透（WebSocket需要持续连接）

## 快速开始

### 1. 配置

复制 `config.example.py` 为 `config.py`，填入你的配置：

```python
# config.py
APP_ID = "你的AppID"
CLIENT_SECRET = "你的ClientSecret"

COSYVOICE_DIR = r"D:\CosyVoice2"          # CosyVoice2安装目录
COSYVOICE_MODEL_REL = "pretrained_models/CosyVoice2-0.5B"  # 模型相对路径
REF_AUDIO = r"D:\ref_audio\my_voice.wav"   # 参考音频（≤30秒，24000Hz单声道wav）
REF_TEXT = "参考音频对应的文字内容"

OLLAMA_MODEL = "qwen3:14b"                 # Ollama模型名
```

### 2. 准备参考音频

准备一段**30秒以内**的wav音频（你的目标音色说话样本）和对应的文字内容，填入config.py的`REF_AUDIO`和`REF_TEXT`。

如果是mp3格式，用ffmpeg转换：
```bash
ffmpeg -i input.mp3 -ac 1 -ar 24000 -t 29 output.wav
```

### 3. 准备角色设定（可选）

在bot脚本同级目录放一个 `天依.md`（或其他名字），作为AI对话的system prompt。格式示例：

```markdown
你是天依，用第一人称「我」自称。你是温柔治愈的少女...
```

### 4. 启动

```bash
python qq-voice-bot.py
```

日志输出到 `qq-voice-bot.log`。

## 启动脚本 (Windows)

双击 `启动QQ语音机器人.bat`：
```bat
@echo off
cd /d %~dp0
python qq-voice-bot.py
pause
```

## 注意事项

### CosyVoice2 依赖
- 必须用**CosyVoice2自带的venv**，不要用系统Python
- 启动时需设置 `PYTHONPATH=""` 避免与其他Python环境冲突
- 参考音频必须 ≤ 30秒（CosyVoice2限制）

### Ollama (qwen3:14b)
- qwen3:14b 默认开启thinking模式，thinking输出不进入最终回复
- 需要足够大的 `num_predict`（推荐800+）确保response有输出空间
- 如果GPU内存不够或回复质量差，可换轻量模型如 `qwen2.5:0.5b`

### QQ Bot
- API域名 `api.sgroup.qq.com` 和 `bots.qq.com` 可能需要国内网络
- WebSocket连接需要稳定网络，断开会自动重连
- 群消息intent需在QQ开放平台后台开启

## 文件结构

```
qq-voice-bot/
├── qq-voice-bot.py          # 主程序
├── config.example.py        # 配置模板（复制为config.py使用）
├── 启动QQ语音机器人.bat      # Windows启动脚本
├── README.md                # 本文件
└── qq-voice-bot.log         # 运行日志（自动生成）
```

## License

Creative Commons Zero v1.0 Universal
