import unittest
from datetime import datetime, timedelta
from time import time

from backend.base.definitions import DownloadService, StatusType
from backend.internals.status import StatusHandlers


class status_handler_registration(unittest.TestCase):
    def test_all_status_types_have_handlers(self):
        """Every StatusType enum value must have a registered handler."""
        for status_type in StatusType:
            self.assertIn(
                status_type,
                StatusHandlers.handlers,
                f"StatusType.{status_type.name} has no registered handler"
            )

    def test_download_service_rate_limit_expires_at_next_midnight(self):
        """Download-service rate-limit status should expire at the next midnight."""
        handler = StatusHandlers.handlers[StatusType.DOWNLOAD_SERVICE_RATE_LIMIT]
        timestamp = int(time())
        expected = int(
            (
                datetime.fromtimestamp(timestamp)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                + timedelta(days=1)
            ).timestamp()
        )

        self.assertEqual(
            handler.get_expiry(
                DownloadService.MEGA.value,
                timestamp),
            expected)


class StatusRestoration(unittest.TestCase):
    def test_restore_expiry_and_clear_cancel_timer(self):
        import sqlite3
        from tempfile import TemporaryDirectory
        from unittest.mock import Mock, patch

        from backend.internals.status import (CVRateLimitStatus,
                                              DownloadServiceRateLimitStatus,
                                              RootFolderFullStatus)

        cv = CVRateLimitStatus(StatusType.CV_RATE_LIMIT)
        service = DownloadServiceRateLimitStatus(StatusType.DOWNLOAD_SERVICE_RATE_LIMIT)
        root = RootFolderFullStatus(StatusType.ROOT_FOLDER_FULL)
        handlers = {h.status_type: h for h in (cv, service, root)}
        timers = []

        def create_timer(**kwargs):
            timer = Mock()
            timer.interval = kwargs['interval']
            timer.subtype = kwargs['args'][0]
            timer.start.side_effect = lambda: self.assertIs(
                handlers[StatusType.CV_RATE_LIMIT]._timers.get(timer.subtype)
                or handlers[StatusType.DOWNLOAD_SERVICE_RATE_LIMIT]._timers.get(timer.subtype),
                timer
            )
            timers.append(timer)
            return timer

        with TemporaryDirectory() as folder, sqlite3.connect(folder + '/status.db') as db:
            db.execute('CREATE TABLE status (status_type TEXT, subtype TEXT, timestamp INTEGER, expires_at INTEGER)')
            db.executemany('INSERT INTO status VALUES (?, ?, ?, ?)', [
                (StatusType.CV_RATE_LIMIT.value, 'active', 900, 1100),
                (StatusType.CV_RATE_LIMIT.value, 'expired', 800, 1000),
                (StatusType.DOWNLOAD_SERVICE_RATE_LIMIT.value, 'Mega', 950, 1200),
                (StatusType.ROOT_FOLDER_FULL.value, '/comics', 900, None),
            ])
            manager = StatusHandlers()
            with patch.object(StatusHandlers, 'handlers', handlers), \
                patch('backend.internals.status.get_db', side_effect=db.cursor), \
                patch('backend.internals.status.time', return_value=1000), \
                patch('backend.internals.status.Server') as server, \
                patch.object(manager, '_emit_count'):
                server.return_value.get_db_timer_thread.side_effect = create_timer
                manager.load_from_db()
                self.assertTrue(cv.problem_reported('active'))
                self.assertFalse(cv.problem_reported('expired'))
                self.assertTrue(service.problem_reported('Mega'))
                self.assertTrue(root.problem_reported('/comics'))
                self.assertEqual([(t.subtype, t.interval) for t in timers], [('active', 100), ('Mega', 200)])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM status').fetchone()[0], 3)
                manager.report(StatusType.CV_RATE_LIMIT, 'active')
                self.assertEqual(len(timers), 2)
                self.assertEqual(db.execute(
                    "SELECT timestamp, expires_at FROM status WHERE subtype = 'active'"
                ).fetchone(), (1000, 1100))
                manager.clear(StatusType.CV_RATE_LIMIT, 'active')
                timers[0].cancel.assert_called_once()
                self.assertFalse(cv.problem_reported('active'))
                self.assertEqual(db.execute('SELECT COUNT(*) FROM status').fetchone()[0], 2)
