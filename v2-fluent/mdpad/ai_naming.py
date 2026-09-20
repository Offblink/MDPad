"""AI 智能文件名生成（智谱 GLM）。

API key 不进仓库：从本机配置文件读（`%APPDATA%\\MDPad\\ai_key.txt`，每行一个 key，
`#` 开头的行忽略）。没配 key 时不会发网络请求，直接把"没配 key"当成一次失败返回，
界面沿用原来的失败提示与默认文件名兜底。
"""
import os

import requests

KEY_FILE_NAME = "ai_key.txt"
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def key_file_path():
    """本机 key 文件位置（打包版与源码版共用同一份）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "MDPad", KEY_FILE_NAME)


def load_api_key():
    """读本机 key 文件：返回第一个有效行；文件不存在/没填内容返回 None。"""
    try:
        with open(key_file_path(), "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        return None
    return None


def generate_filename_with_ai(content, timeout=10):
    """调用 AI API，根据文档内容生成 10 字以内的默认文件名。

    返回:
        (name, error)：成功时 name 为清理后的短标题（不含扩展名）、error 为 None；
        失败时 name 为 None、error 为可展示的错误描述。
    """
    if not content or not content.strip():
        return None, None

    api_key = load_api_key()
    if not api_key:
        return None, f"未配置 AI key：请在 {key_file_path()} 里填一行智谱 API key"

    prompt = f"""
    请将以下文本内容总结成一个10个中文字以内的短标题，用于作为文件名。不要包含任何标点符号、引号或文件扩展名。\n
    文本内容：\n{content[:2000]}  # 限制输入长度
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": "你是一个文件命名助手，请根据内容生成简洁的标题，不超过10个字。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 20,
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        ai_response = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        cleaned = ai_response.replace('"', '').replace("'", "").replace("。", "").replace(".", "")
        if len(cleaned) > 10:
            cleaned = cleaned[:10]
        if cleaned:
            return cleaned, None
        return None, "AI 未返回有效的文件名"
    except requests.exceptions.Timeout:
        return None, "请求 AI 服务超时"
    except requests.exceptions.RequestException as e:
        return None, f"无法连接到 AI 服务: {e}"
    except Exception as e:
        return None, f"处理 AI 响应时出错: {e}"
