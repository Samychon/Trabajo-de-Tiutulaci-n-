import unittest

from sqlalchemy import DateTime
from sqlalchemy.sql.elements import TextClause

from app.db.base import Base


class TimestampDefaultTests(unittest.TestCase):
    def test_timestamp_defaults_are_sql_functions_not_literal_text(self):
        checked = 0
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                default = column.server_default
                if not isinstance(column.type, DateTime) or default is None:
                    continue
                checked += 1
                self.assertNotIsInstance(default.arg, str, f"{table.name}.{column.name}")
                self.assertNotIsInstance(default.arg, TextClause, f"{table.name}.{column.name}")
        self.assertGreaterEqual(checked, 13)


if __name__ == "__main__":
    unittest.main()
