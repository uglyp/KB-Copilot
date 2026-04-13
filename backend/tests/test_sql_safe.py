"""SQL 仅 SELECT 校验单元测试。"""

import unittest

from app.services.llama_analytics.sql_safe import assert_select_only


class TestAssertSelectOnly(unittest.TestCase):
    def test_accepts_simple_select(self) -> None:
        assert_select_only("SELECT 1")
        assert_select_only("  select * from v_users_public  ")

    def test_rejects_delete(self) -> None:
        with self.assertRaises(ValueError):
            assert_select_only("DELETE FROM v_users_public")

    def test_rejects_multiple_statements(self) -> None:
        with self.assertRaises(ValueError):
            assert_select_only("SELECT 1; SELECT 2")


class TestLlamaIntent(unittest.TestCase):
    def test_keyword_hit(self) -> None:
        from app.core.config import Settings
        from app.services.llama_analytics.intent import should_run_llama_analytics

        s = Settings(
            database_url="mysql+aiomysql://u:p@localhost/db",
            relational_db="mysql",
            llamaindex_enabled=True,
            llamaindex_intent_keywords="用户,统计",
        )
        self.assertTrue(should_run_llama_analytics("当前用户数", s))

    def test_disabled(self) -> None:
        from app.core.config import Settings
        from app.services.llama_analytics.intent import should_run_llama_analytics

        s = Settings(
            database_url="mysql+aiomysql://u:p@localhost/db",
            relational_db="mysql",
            llamaindex_enabled=False,
        )
        self.assertFalse(should_run_llama_analytics("用户数", s))


if __name__ == "__main__":
    unittest.main()
