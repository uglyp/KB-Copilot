"""
应用入口（ASGI）。

Python Web 常见结构：
- `FastAPI()` 创建应用实例；`uvicorn app.main:app` 中的 `app` 即此变量。
- 中间件按「后添加先执行」的顺序包裹请求；CORS 需放前面以便浏览器预检（OPTIONS）能通过。
- `include_router` 把各模块路由挂到统一前缀下（如 `/api/v1`），避免单文件里写几千行路由。

与前端的关系：Vite 开发服（如 :5173）与后端（:8000）不同源，故需 CORS 放行前端 Origin。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.hf_env import configure_hf_hub_env

# 在任意可能 import huggingface / fastembed 之前设置镜像与超时（见 hf_env 模块说明）
configure_hf_hub_env()

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health() -> dict[str, str]:
    """负载均衡 / K8s 探针常用；不查数据库，仅确认进程存活。"""
    return {"status": "ok"}
