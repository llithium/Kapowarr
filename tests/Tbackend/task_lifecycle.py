import unittest
from threading import Thread
from unittest.mock import patch

from backend.base.custom_exceptions import TaskNotDeletable, TaskNotFound
from backend.features.tasks import SearchAll, TaskHandler


class TaskCancellation(unittest.TestCase):
    def test_cancel_queued_task_without_starting_its_thread(self):
        handler = TaskHandler()
        running = SearchAll()
        queued = SearchAll()
        thread = Thread(target=lambda: self.fail('Canceled task ran'))
        entries = [
            {'id': 1, 'task': running, 'status': 'running', 'thread': Thread()},
            {'id': 2, 'task': queued, 'status': 'queued', 'thread': thread}
        ]
        with patch.object(TaskHandler, 'queue', entries), patch(
            'backend.features.tasks.WebSocket'
        ) as websocket:
            handler.remove(2)
            self.assertEqual([entry['id'] for entry in handler.queue], [1])
            self.assertTrue(queued.stop)
            self.assertIsNone(thread.ident)
            websocket.return_value.emit.assert_called_once()
            with self.assertRaises(TaskNotDeletable):
                handler.remove(1)
            with self.assertRaises(TaskNotFound):
                handler.remove(2)


if __name__ == '__main__':
    unittest.main()
