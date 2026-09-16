import sqlite3
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from backend.features.tasks import TaskHandler


class TaskScheduling(unittest.TestCase):
    def setUp(self) -> None:
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """
            CREATE TABLE task_intervals(
                task_name PRIMARY KEY,
                schedule TEXT NOT NULL,
                next_run INTEGER NOT NULL
            );
            """
        )
        self.db.execute(
            "INSERT INTO task_intervals VALUES (?, ?, ?);",
            ('update_all', '0 * * * *', 0)
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_interval_check_reads_cron_schedule_schema(self) -> None:
        handler = TaskHandler()
        handler.context = nullcontext

        with patch('backend.features.tasks.get_db', return_value=self.db), \
                patch('backend.features.tasks.get_schedules_next_run',
                      return_value=123) as next_run, \
                patch.object(handler, 'add') as add, \
                patch.object(handler, 'handle_intervals') as reschedule:
            handler._TaskHandler__check_intervals()

        add.assert_called_once()
        next_run.assert_called_once_with('0 * * * *')
        self.assertEqual(
            self.db.execute(
                "SELECT next_run FROM task_intervals WHERE task_name = ?;",
                ('update_all',)
            ).fetchone()[0],
            123
        )
        reschedule.assert_called_once_with()

    def test_update_schedule_recalculates_next_run(self) -> None:
        handler = TaskHandler()
        handler.task_interval_waiter = None

        with patch('backend.features.tasks.get_db', return_value=self.db), \
                patch('backend.features.tasks.get_schedules_next_run',
                      return_value=456), \
                patch.object(handler, 'handle_intervals') as reschedule:
            handler.update_task_schedule('update_all', '15 * * * *')

        self.assertEqual(
            tuple(self.db.execute(
                """
                SELECT schedule, next_run
                FROM task_intervals
                WHERE task_name = ?;
                """,
                ('update_all',)
            ).fetchone()),
            ('15 * * * *', 456)
        )
        reschedule.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
