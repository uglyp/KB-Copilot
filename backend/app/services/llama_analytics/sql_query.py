"""管理员 NL2SQL（仅视图）与普通用户参数化统计。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

# 与迁移中视图名一致；勿包含基表
ADMIN_ANALYTICS_TABLES: list[str] = [
    "v_users_public",
    "v_knowledge_bases_catalog",
    "v_conversations_summary",
    "v_documents_catalog",
    "v_messages_for_analytics",
    "v_llm_usage_records_public",
]


def run_admin_nl2sql(engine: Engine, llm: LLM, question: str) -> str:
    """仅暴露脱敏视图；连接须为只读账号。"""
    from llama_index.core import SQLDatabase
    from llama_index.core.query_engine import NLSQLTableQueryEngine

    sql_database = SQLDatabase(engine, include_tables=ADMIN_ANALYTICS_TABLES)
    qe = NLSQLTableQueryEngine(
        sql_database=sql_database,
        tables=ADMIN_ANALYTICS_TABLES,
        llm=llm,
        synthesize_response=True,
    )
    try:
        resp = qe.query(question)
        return str(resp)
    except Exception:
        logger.exception("管理员 NL2SQL 失败")
        raise


def run_user_safe_stats(engine: Engine, user_id: int) -> str:
    """参数化查询，仅返回当前用户维度统计（含用量表 token 与按模型拆分）。"""
    overview = text(
        """
        SELECT
          (SELECT COUNT(*) FROM v_knowledge_bases_catalog WHERE user_id = :uid) AS kb_count,
          (SELECT COUNT(*) FROM v_conversations_summary WHERE user_id = :uid) AS conv_count,
          (SELECT COUNT(*) FROM v_messages_for_analytics WHERE user_id = :uid) AS msg_count
        """
    )
    usage_totals = text(
        """
        SELECT
          COUNT(*) AS usage_rounds,
          COALESCE(SUM(embed_prompt_tokens), 0) AS sum_embed_prompt,
          COALESCE(SUM(embed_total_tokens), 0) AS sum_embed_total,
          COALESCE(SUM(chat_prompt_tokens), 0) AS sum_chat_prompt,
          COALESCE(SUM(chat_completion_tokens), 0) AS sum_chat_completion,
          COALESCE(SUM(chat_total_tokens), 0) AS sum_chat_total
        FROM llm_usage_records
        WHERE user_id = :uid
        """
    )
    dialect = engine.dialect.name
    if dialect == "postgresql":
        usage_by_model = text(
            """
            SELECT
              r.chat_model_id,
              COALESCE(
                MAX(CASE WHEN p.user_id = :uid THEN m.display_name END),
                CASE
                  WHEN r.chat_model_id IS NULL THEN '未记录模型'
                  ELSE '模型ID ' || r.chat_model_id::text
                END
              ) AS model_label,
              COUNT(*)::bigint AS rounds,
              COALESCE(SUM(r.chat_total_tokens), 0)::bigint AS chat_tokens,
              COALESCE(SUM(r.chat_prompt_tokens), 0)::bigint AS chat_prompt_tokens,
              COALESCE(SUM(r.chat_completion_tokens), 0)::bigint AS chat_completion_tokens,
              COALESCE(SUM(r.embed_total_tokens), 0)::bigint AS embed_tokens,
              COALESCE(SUM(r.embed_prompt_tokens), 0)::bigint AS embed_prompt_tokens
            FROM llm_usage_records r
            LEFT JOIN llm_models m ON m.id = r.chat_model_id
            LEFT JOIN llm_providers p ON p.id = m.provider_id
            WHERE r.user_id = :uid
            GROUP BY r.chat_model_id
            ORDER BY rounds DESC
            """
        )
    else:
        # MySQL
        usage_by_model = text(
            """
            SELECT
              r.chat_model_id,
              COALESCE(
                MAX(CASE WHEN p.user_id = :uid THEN m.display_name END),
                CASE
                  WHEN r.chat_model_id IS NULL THEN '未记录模型'
                  ELSE CONCAT('模型ID ', CAST(r.chat_model_id AS CHAR))
                END
              ) AS model_label,
              COUNT(*) AS rounds,
              COALESCE(SUM(r.chat_total_tokens), 0) AS chat_tokens,
              COALESCE(SUM(r.chat_prompt_tokens), 0) AS chat_prompt_tokens,
              COALESCE(SUM(r.chat_completion_tokens), 0) AS chat_completion_tokens,
              COALESCE(SUM(r.embed_total_tokens), 0) AS embed_tokens,
              COALESCE(SUM(r.embed_prompt_tokens), 0) AS embed_prompt_tokens
            FROM llm_usage_records r
            LEFT JOIN llm_models m ON m.id = r.chat_model_id
            LEFT JOIN llm_providers p ON p.id = m.provider_id
            WHERE r.user_id = :uid
            GROUP BY r.chat_model_id
            ORDER BY rounds DESC
            """
        )

    lines: list[str] = [
        "与当前账号相关的统计（参数化 SQL，仅含本用户数据）：",
        "",
        "【资源概览】",
    ]
    with engine.connect() as conn:
        row = conn.execute(overview, {"uid": user_id}).mappings().first()
        if not row:
            return ""
        lines.append(f"- 知识库数量: {row['kb_count']}")
        lines.append(f"- 会话数量: {row['conv_count']}")
        lines.append(f"- 消息条数（messages 表）: {row['msg_count']}")
        lines.append("")

        urow = conn.execute(usage_totals, {"uid": user_id}).mappings().first()
        if urow and (urow["usage_rounds"] or 0) > 0:
            lines.append("【对话用量汇总】（来自 llm_usage_records，一条记录一轮问答）")
            lines.append(f"- 有用量记录的问答轮次: {urow['usage_rounds']}")
            lines.append(
                f"- 对话 token 合计（prompt+completion，若未分项则可能只在 chat_total）: "
                f"chat_total={urow['sum_chat_total']}, "
                f"chat_prompt={urow['sum_chat_prompt']}, "
                f"chat_completion={urow['sum_chat_completion']}"
            )
            lines.append(
                f"- 检索 embedding token 合计: embed_total={urow['sum_embed_total']}, "
                f"embed_prompt={urow['sum_embed_prompt']}"
            )
            lines.append("")

            model_rows = conn.execute(usage_by_model, {"uid": user_id}).mappings().all()
            lines.append("【按对话模型维度】（轮次与 token；模型名仅当提供商属当前用户时显示）")
            for mr in model_rows:
                lines.append(
                    f"  - {mr['model_label']}: "
                    f"轮次={mr['rounds']}, "
                    f"chat_total={mr['chat_tokens']}, "
                    f"chat_prompt={mr['chat_prompt_tokens']}, "
                    f"chat_completion={mr['chat_completion_tokens']}, "
                    f"embed_total={mr['embed_tokens']}, "
                    f"embed_prompt={mr['embed_prompt_tokens']}"
                )
        else:
            lines.append("【对话用量汇总】暂无 llm_usage_records 记录（新用户或未产生用量统计的会话）。")

    lines.append("")
    lines.append(
        "请用以上数字直接回答用户关于明细、轮次、模型、token 的问题；"
        "若某项为 0 或为空，再说明原因，勿笼统说「系统无法提供」。"
    )
    return "\n".join(lines)
