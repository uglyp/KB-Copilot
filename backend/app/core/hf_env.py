"""
Hugging Face Hub / 镜像与超时。

许多 Python 库在 **import 时或首次调用时** 读取 `os.environ`。
因此本模块应在 `import fastembed` 之前执行（见 `main.py` 与 `local_embed.py`）。
`HF_ENDPOINT` 可指向国内镜像，减轻 `huggingface.co` 直连超时。
"""

import os

_configured = False


def configure_hf_hub_env() -> None:
    """幂等：多次调用只生效一次；避免重复改环境变量。"""
    global _configured
    if _configured:
        return
    _configured = True

    from app.core.config import get_settings

    s = get_settings()

    # 国内等网络环境下直连 huggingface.co 易超时，可设镜像（例：https://hf-mirror.com）
    if s.hf_endpoint:
        os.environ["HF_ENDPOINT"] = s.hf_endpoint.rstrip("/")

    # 默认 10s 对大模型文件过短，大文件需长时间持续传输
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", str(s.hf_hub_download_timeout))
    # 拉取仓库元数据（ETag）也可能慢
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", str(s.hf_hub_etag_timeout))
