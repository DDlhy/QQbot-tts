"""
QQ群语音机器人 — QQ-Voice-Bot
监听群@消息 → Ollama AI对话 → CosyVoice2语音克隆 → 发送语音
纯asyncio+httpx+aiohttp，不依赖其他框架

使用前：复制 config.example.py 为 config.py 并填入你的配置
"""
import asyncio
import json
import logging
import os
import re
import sys
import time
import base64
import subprocess
import tempfile

import httpx
import aiohttp

# ============ 日志 ============
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qq-voice-bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("qq-voice-bot")

# ============ 配置加载 ============
# 优先从 config.py 加载，没有则使用默认占位
try:
    from config import (
        APP_ID, CLIENT_SECRET,
        COSYVOICE_DIR, COSYVOICE_MODEL_REL,
        REF_AUDIO, REF_TEXT,
        OLLAMA_MODEL,
        PERSONA_FILE,
    )
    log.info(f"配置已从 config.py 加载")
except ImportError:
    log.warning("config.py 未找到！请在脚本同级目录复制 config.example.py 为 config.py 并填入配置")
    APP_ID = "请填入你的AppID"
    CLIENT_SECRET = "请填入你的ClientSecret"
    COSYVOICE_DIR = r"C:\CosyVoice2"
    COSYVOICE_MODEL_REL = "pretrained_models/CosyVoice2-0.5B"
    REF_AUDIO = "ref_audio.wav"
    REF_TEXT = "请填入参考音频的文字内容"
    OLLAMA_MODEL = "qwen3:14b"
    PERSONA_FILE = "洛天依.md"

# 派生路径
COSYVOICE_PYTHON = os.path.join(COSYVOICE_DIR, "venv", "Scripts", "python.exe")
COSYVOICE_MODEL = os.path.join(COSYVOICE_DIR, COSYVOICE_MODEL_REL)
PERSONA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), PERSONA_FILE)

# ============ QQ Bot API 常量 ============
API_BASE = "https://api.sgroup.qq.com"
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
GATEWAY_URL_PATH = "/gateway"
MSG_TYPE_MEDIA = 7
MEDIA_TYPE_VOICE = 3

# ============ Ollama 配置 ============
OLLAMA_URL = "http://localhost:11434/api/generate"

# ============ 工具函数 ============

def build_user_agent() -> str:
    return f"qq-voice-bot/{APP_ID}"

async def get_access_token(client: httpx.AsyncClient) -> str:
    """获取QQ Bot access token"""
    log.info("正在获取 access token...")
    resp = await client.post(
        TOKEN_URL,
        json={"appId": APP_ID, "clientSecret": CLIENT_SECRET},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Token response missing access_token: {data}")
    log.info(f"Token获取成功，有效期 {data.get('expires_in', '?')}s")
    return token

async def get_gateway_url(client: httpx.AsyncClient, token: str) -> str:
    """获取WebSocket网关地址"""
    log.info("正在获取网关地址...")
    resp = await client.get(
        f"{API_BASE}{GATEWAY_URL_PATH}",
        headers={"Authorization": f"QQBot {token}", "User-Agent": build_user_agent()},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    url = data.get("url")
    if not url:
        raise RuntimeError(f"Gateway response missing url: {data}")
    log.info(f"网关地址: {url}")
    return url

# ============ 角色设定 ============

def load_persona() -> str:
    """读取角色设定文件"""
    if os.path.exists(PERSONA_PATH):
        raw = open(PERSONA_PATH, encoding="utf-8").read().strip()
        log.info(f"角色设定已加载 ({len(raw)}字符)")
        return raw
    else:
        log.warning(f"角色文件未找到: {PERSONA_PATH}，Ollama将无角色设定运行")
        return ""

# ============ Ollama 对话 ============

async def ask_ollama(prompt: str) -> str:
    """调用Ollama，返回文字回复"""
    log.info(f'Ollama请求: "{prompt[:50]}..."')
    sys_prompt = load_persona()
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "system": sys_prompt,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 800},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        reply = (data.get("response") or data.get("thinking") or "").strip()
        log.info(f'Ollama回复: "{reply[:50]}..."')
        return reply

# ============ CosyVoice2 TTS ============

def generate_tts(text: str) -> str:
    """调用CosyVoice2生成语音，返回wav文件路径"""
    output_path = os.path.join(tempfile.gettempdir(), f"qq_voice_{int(time.time())}.wav")
    log.info(f'TTS开始生成: "{text[:30]}..."')

    model_path = COSYVOICE_MODEL.replace("\\", "/")
    ref_path = REF_AUDIO.replace("\\", "/")
    out_path = output_path.replace("\\", "/")
    text_escaped = json.dumps(text)
    ref_text_escaped = json.dumps(REF_TEXT)
    out_path_escaped = json.dumps(out_path)

    script = f"""
import sys
sys.path.insert(0, 'third_party/Matcha-TTS')
from cosyvoice.cli.cosyvoice import CosyVoice2

model = CosyVoice2('{model_path}', load_jit=False, load_trt=False, fp16=False)
out = model.inference_zero_shot({text_escaped}, {ref_text_escaped}, '{ref_path}', stream=False)
result = next(out)

import torchaudio
wav = result['tts_speech']
if wav.shape[1] > 24000:
    wav = wav[:, 24000:]
torchaudio.save({out_path_escaped}, wav, 24000)
print('TTS_DONE')
"""

    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    proc = subprocess.run(
        [COSYVOICE_PYTHON, "-c", script],
        cwd=COSYVOICE_DIR,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if "TTS_DONE" not in proc.stdout:
        stderr_tail = proc.stderr[-500:]
        log.error(f"TTS失败! stderr: {stderr_tail}")
        raise RuntimeError("TTS生成失败")

    file_size = os.path.getsize(output_path)
    log.info(f"TTS生成完成: {output_path} ({file_size} bytes, {file_size/24000/2:.1f}s)")
    return output_path

# ============ 语音上传与发送 ============

async def upload_small_voice(client: httpx.AsyncClient, token: str, chat_type: str, chat_id: str, file_path: str) -> dict:
    """小文件直传: POST /v2/{users|groups}/{id}/files"""
    file_size = os.path.getsize(file_path)
    log.info(f"上传语音: {file_size} bytes -> {chat_type}:{chat_id}")
    with open(file_path, "rb") as f:
        file_data_b64 = base64.b64encode(f.read()).decode()

    path = f"/v2/users/{chat_id}/files" if chat_type == "c2c" else f"/v2/groups/{chat_id}/files"

    resp = await client.request(
        "POST",
        f"{API_BASE}{path}",
        headers={
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
            "User-Agent": build_user_agent(),
        },
        json={
            "file_type": MEDIA_TYPE_VOICE,
            "file_data": file_data_b64,
            "srv_send_msg": False,
        },
        timeout=120.0,
    )
    data = resp.json()
    if resp.status_code >= 400:
        raise RuntimeError(f"上传失败 [{resp.status_code}]: {data.get('message', data)}")
    file_info = data.get("file_info") or (data.get("data", {}) or {}).get("file_info")
    if not file_info:
        raise RuntimeError(f"上传返回无file_info: {json.dumps(data, ensure_ascii=False)[:200]}")
    log.info(f"上传成功")
    return file_info

async def send_voice_message(client: httpx.AsyncClient, token: str, chat_type: str, chat_id: str, file_info: dict):
    """发送语音消息"""
    path = f"/v2/users/{chat_id}/messages" if chat_type == "c2c" else f"/v2/groups/{chat_id}/messages"

    resp = await client.request(
        "POST",
        f"{API_BASE}{path}",
        headers={
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
            "User-Agent": build_user_agent(),
        },
        json={
            "msg_type": MSG_TYPE_MEDIA,
            "media": {"file_info": file_info},
        },
        timeout=30.0,
    )
    data = resp.json()
    if resp.status_code >= 400:
        raise RuntimeError(f"发送失败 [{resp.status_code}]: {data.get('message', data)}")
    log.info(f"语音已发送 {chat_type}:{chat_id}")

def strip_at_mention(content: str) -> str:
    """去掉@bot前缀"""
    return re.sub(r"^@\S+\s*", "", content.strip()).strip()

# ============ 消息处理 ============

FALLBACK_TEXT = "嗯...刚才走神了一下下~ 再说一次好吗？"

async def handle_group_at(text: str, group_openid: str, client: httpx.AsyncClient, token: str):
    """处理群@消息"""
    text = strip_at_mention(text)
    log.info(f"━━━ 群@消息 ━━━")
    log.info(f"  群ID: {group_openid}")
    log.info(f"  内容: {text[:100]}")

    if not text:
        log.info("  无文字内容，跳过")
        return

    try:
        if text.strip().startswith("/生成"):
            tts_text = text.strip()[3:].strip()
            if not tts_text:
                log.info("  /生成 无内容，跳过")
                return
            log.info(f"  模式: /生成 → 直接TTS")
        else:
            reply = await ask_ollama(text)
            if not reply:
                reply = FALLBACK_TEXT
            tts_text = reply
            log.info(f"  模式: Ollama对话 → TTS")

        wav_path = await asyncio.get_running_loop().run_in_executor(None, generate_tts, tts_text)
        file_info = await upload_small_voice(client, token, "group", group_openid, wav_path)
        await send_voice_message(client, token, "group", group_openid, file_info)
        os.unlink(wav_path)
        log.info("━━━ 处理完成 ━━━")
    except Exception as e:
        log.error(f"处理失败: {e}", exc_info=True)

async def handle_dm(text: str, user_openid: str, client: httpx.AsyncClient, token: str):
    """处理私聊消息"""
    log.info(f"━━━ 私聊消息 ━━━")
    log.info(f"  用户: {user_openid}")
    log.info(f"  内容: {text[:100]}")

    try:
        wav_path = await asyncio.get_running_loop().run_in_executor(None, generate_tts, text)
        file_info = await upload_small_voice(client, token, "c2c", user_openid, wav_path)
        await send_voice_message(client, token, "c2c", user_openid, file_info)
        os.unlink(wav_path)
        log.info("━━━ 处理完成 ━━━")
    except Exception as e:
        log.error(f"失败: {e}", exc_info=True)

# ============ WebSocket 监听 ============

async def listen_ws(client: httpx.AsyncClient, token: str):
    """连接WebSocket并循环处理事件"""
    gateway_url = await get_gateway_url(client, token)

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(gateway_url) as ws:
            log.info("WebSocket已连接，开始监听...")

            last_seq = None
            heartbeat_interval = 30.0

            async def heartbeat():
                while True:
                    await asyncio.sleep(heartbeat_interval * 0.8)
                    try:
                        await ws.send_json({"op": 1, "d": last_seq})
                    except Exception:
                        break

            identify_payload = {
                "op": 2,
                "d": {
                    "token": f"QQBot {token}",
                    "intents": (1 << 25) | (1 << 30),
                    "shard": [0, 1],
                    "properties": {
                        "$os": "windows", "$browser": "qq-voice-bot", "$device": "qq-voice-bot"
                    },
                },
            }
            await ws.send_json(identify_payload)
            log.info("Identify已发送，等待事件...")

            hb_task = asyncio.create_task(heartbeat())

            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        op = payload.get("op", 0)
                        d = payload.get("d", {})
                        seq = payload.get("s")
                        if seq is not None:
                            last_seq = seq

                        if op == 10:
                            heartbeat_interval = d.get("heartbeat_interval", 30) / 1000.0
                            log.info(f"Hello接收, heartbeat={heartbeat_interval:.1f}s")
                        elif op == 11:
                            pass
                        elif op == 0:
                            event_type = payload.get("t", "")
                            log.info(f"WS事件: t={event_type} s={seq}")
                            if event_type in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
                                group_openid = str(d.get("group_openid", ""))
                                content = str(d.get("content", ""))
                                log.info(f"收到群@事件 group={group_openid}")
                                asyncio.create_task(handle_group_at(content, group_openid, client, token))
                            elif event_type == "C2C_MESSAGE_CREATE":
                                author = d.get("author", {})
                                user_openid = str(author.get("user_openid", "")) if isinstance(author, dict) else ""
                                content = str(d.get("content", ""))
                                log.info(f"收到私聊 user={user_openid}")
                                if content.strip():
                                    asyncio.create_task(handle_dm(content, user_openid, client, token))

                    elif msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                        log.warning(f"WS连接关闭: {msg.type}")
                        break
            except Exception as e:
                log.error(f"WS异常: {e}", exc_info=True)
            finally:
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass

# ============ 主入口 ============

async def main():
    log.info("=" * 50)
    log.info("QQ群语音机器人 v1.1")
    log.info(f"App ID: {APP_ID[:8]}***")
    log.info(f"TTS引擎: CosyVoice2")
    log.info(f"AI模型: Ollama/{OLLAMA_MODEL}")
    log.info(f"角色设定: {PERSONA_FILE}")
    log.info("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        reconnect_count = 0
        while True:
            try:
                token = await get_access_token(client)
                await listen_ws(client, token)
            except Exception as e:
                reconnect_count += 1
                delay = min(30, 5 * reconnect_count)
                log.error(f"连接断开 (第{reconnect_count}次): {e}")
                log.info(f"{delay}秒后重连...")
                await asyncio.sleep(delay)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("用户中断，退出")
    except Exception as e:
        log.critical(f"致命错误: {e}", exc_info=True)
        input("按回车退出...")