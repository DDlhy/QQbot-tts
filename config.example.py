# ============================================
# QQ-Voice-Bot 配置文件
# 复制此文件为 config.py 并填入你的配置
# ============================================

# ---------- QQ Bot ----------
APP_ID = "你的AppID"                  # 在QQ开放平台 https://q.qq.com 获取
CLIENT_SECRET = "你的ClientSecret"

# ---------- CosyVoice2 ----------
COSYVOICE_DIR = r"D:\CosyVoice2"    # CosyVoice2安装根目录
# 模型路径（相对于COSYVOICE_DIR）
COSYVOICE_MODEL_REL = "pretrained_models/CosyVoice2-0.5B"

# ---------- 参考音频 ----------
REF_AUDIO = r"D:\ref_audio\my_voice.wav"     # 参考音频路径（wav, ≤30秒, 24000Hz单声道）
REF_TEXT = "参考音频里说的话，写在这里"         # 参考音频对应的文字

# ---------- Ollama ----------
OLLAMA_MODEL = "qwen3:14b"          # Ollama模型名（ollama list查看已安装模型）
# OLLAMA_MODEL = "qwen2.5:0.5b"     # 轻量替代方案

# ---------- 角色设定文件（可选） ----------
# 放在脚本同级目录，用于Ollama对话时的system prompt
PERSONA_FILE = "天依.md"
