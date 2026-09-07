import inspect
import unittest
from asyncio import run
from types import SimpleNamespace

from backend.base.definitions import (EnqueuingDownloadFailureReason,
                                      MonitorScheme)
from backend.features.download_queue import DownloadHandler
from backend.implementations.volumes import Library
from backend.internals.settings import SettingsValues


class DownloadPreferences(unittest.TestCase):
    def test_download_feature_is_enabled_by_default_for_compatibility(self):
        self.assertTrue(SettingsValues().downloads_enabled)

    def test_new_volumes_are_unmonitored_by_default(self):
        parameters = inspect.signature(Library.add).parameters
        self.assertFalse(parameters['monitored'].default)
        self.assertEqual(
            parameters['monitor_scheme'].default,
            MonitorScheme.NONE,
        )
        self.assertFalse(parameters['monitor_new_issues'].default)
        self.assertFalse(parameters['auto_search'].default)

    def test_disabled_downloads_are_not_enqueued(self):
        handler = object.__new__(DownloadHandler)
        handler.settings = SimpleNamespace(
            sv=SimpleNamespace(downloads_enabled=False)
        )

        downloads, reason = run(handler.add(
            'https://getcomics.org/example',
            1,
        ))

        self.assertEqual(downloads, [])
        self.assertEqual(
            reason,
            EnqueuingDownloadFailureReason.DOWNLOADS_DISABLED,
        )


if __name__ == '__main__':
    unittest.main()
