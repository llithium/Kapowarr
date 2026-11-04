import multiprocessing
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from zipfile import ZipFile

from flask import Flask, has_app_context

from backend.base import helpers
from backend.implementations import conversion
from backend.implementations.converters import ProposedConversion, zip_to_cbz


def _initialize_worker_context(*args):
    """Provide a Flask context without starting application services."""
    helpers.context = Flask('conversion-worker').app_context


def _convert_archive_in_context(filepath):
    if not has_app_context():
        raise RuntimeError('Conversion worker has no application context')
    return zip_to_cbz(filepath)


class MassConversion(unittest.TestCase):
    def test_conversion_runs_in_worker_with_and_without_progress(self):
        for report_progress in (False, True):
            with self.subTest(report_progress=report_progress), TemporaryDirectory() as folder:
                source = Path(folder, 'Comic.zip')
                with ZipFile(source, 'w') as archive:
                    archive.writestr('page.jpg', b'comic page')
                target = source.with_suffix('.cbz')
                proposal = ProposedConversion(str(source), _convert_archive_in_context, 'cbz')
                websocket = Mock()
                websocket.client_manager.queue = None

                with patch.object(conversion, '_get_convertable_files', return_value=iter([proposal])), \
                        patch.object(conversion, 'commit'), \
                        patch.object(conversion.FilesDB, 'delete_filepaths'), \
                        patch.object(conversion, 'scan_files'), \
                        patch.object(conversion, 'mass_process_files'), \
                        patch.object(conversion, 'WebSocket', return_value=websocket), \
                        patch('backend.internals.server.WebSocket', return_value=websocket), \
                        patch.object(helpers, 'get_log_filepath', return_value=str(Path(folder, 'test.log'))), \
                        patch.object(helpers, '_create_context', _initialize_worker_context), \
                        patch.object(helpers, 'Pool', multiprocessing.get_context('spawn').Pool):
                    result = conversion.mass_convert(1, update_websocket_progress=report_progress)

                self.assertEqual(result, [str(target)])
                self.assertFalse(source.exists())
                with ZipFile(target) as archive:
                    self.assertEqual(archive.read('page.jpg'), b'comic page')
