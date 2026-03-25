"""
与「后台任务」同名的轻量入口：当前在请求内直接 `await`，但使用 **独立 session**，
避免与上传接口的 session 事务纠缠；成功则 `commit`，失败 `rollback` 后抛出。
"""

from app.db.session import async_session_factory
from app.services.ingestion import process_document_ingestion


async def ingest_document_task(doc_id: int) -> None:
    async with async_session_factory() as session:
        try:
            await process_document_ingestion(session, doc_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
