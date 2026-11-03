import asyncio
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from requests import RequestException

from backend.base.definitions import (DownloadClientIdentifier,
                                      DownloadService, DownloadState,
                                      GCDownloadService, SearchAction)
from backend.features.download_queue import (DownloadHandler,
                                             download_type_to_class)
from backend.features.post_processing import add_to_history
from backend.features.search_full import SearchCoordinator
from backend.implementations import getcomics
from backend.implementations.download_clients.base import BaseDirectDownload


class DownloadWorkflowTest(unittest.TestCase):
    def test_producer_persist_restore_and_history(self):
        class Download:
            identifier = DownloadClientIdentifier.DDL

            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.id = None
                self.issue_id = None
                self.title = 'Comic'
                self.state = DownloadState.DOWNLOADING_STATE

            def as_dict(self):
                return {'id': self.id}

        group = {'links': {GCDownloadService.GETCOMICS: ['link']},
                 'info': {'issue_number': 1.0}, 'web_sub_title': 'subtitle'}
        with patch.object(getcomics, '__purify_link', AsyncMock(return_value=('link', Download))), \
            patch.object(getcomics, 'iter_commit', lambda rows: rows):
            download, _ = asyncio.run(getattr(getcomics, '__purify_download_group')(
                group, 1, None, 'page', 'title'))
        self.assertIs(download.download_service, DownloadService.GETCOMICS)

        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE download_queue (id INTEGER PRIMARY KEY, volume_id, client_type, external_client_id, download_link, covered_issues, force_original_name, source_type, source_name, web_link, web_title, web_sub_title)')
        db.execute('CREATE TABLE download_history (web_link, web_title, web_sub_title, file_title, volume_id, issue_id, source, downloaded_at, success)')
        handler = DownloadHandler.__new__(DownloadHandler)
        handler.queue = []
        handler.settings = SimpleNamespace(sv=SimpleNamespace(downloads_enabled=True))
        with patch('backend.features.download_queue.get_db', return_value=db.cursor()), \
            patch('backend.features.download_queue.Server', return_value=Mock()), \
            patch('backend.features.download_queue.WebSocket', return_value=Mock()), \
            patch('backend.features.download_queue.AddedToQueueEvent'), \
            patch('backend.features.download_queue.iter_commit', lambda rows: rows), \
            patch.object(handler, '_process_queue'), \
            patch.dict(download_type_to_class, {DownloadClientIdentifier.DDL: Download}), \
            patch('backend.features.post_processing.get_db', return_value=db.cursor()), \
            patch('backend.features.download_queue.IndexerClients.get_all_data', return_value=[
                 {'id': 1, 'enabled': True, 'client_type': 'GetComics', 'url': 'https://example.test/catalog'}
            ]), \
            patch('backend.features.download_queue.GetComicsPage') as page:
            page.return_value.load_data = AsyncMock()
            page.return_value.create_downloads = AsyncMock(return_value=[download])
            self.assertIsNone(handler._DownloadHandler__determine_link_type('https://example.test.evil/catalog/page'))
            self.assertIsNone(handler._DownloadHandler__determine_link_type('https://example.test/catalogue/page'))
            entries, error = asyncio.run(handler.add('https://example.test/catalog/page', 1, indexer_id=1))
            self.assertIsNone(error)
            self.assertEqual(entries, [{'id': download.id}])
            page.return_value.create_downloads.assert_awaited_once_with(1, None, False)
            handler.queue = []
            self.assertEqual(tuple(db.execute('SELECT client_type, source_type FROM download_queue').fetchone()), ('direct', 'GetComics'))
            handler._DownloadHandler__load_downloads()
            restored = handler.queue[0]
            self.assertEqual(restored.id, download.id)
            self.assertIs(restored.download_service, DownloadService.GETCOMICS)
            add_to_history(restored)
            self.assertEqual(db.execute('SELECT source FROM download_history').fetchone()[0], 'GetComics')
        db.close()

    def test_retry_resets_non_range_and_resumes_range(self):
        class Response:
            def __init__(self, fail): self.fail = fail
            def __enter__(self): return self
            def __exit__(self, *args): pass

            def iter_content(self, **kwargs):
                yield b'old' if self.fail else b'complete'
                if self.fail:
                    raise RequestException('interrupted')
        for supports_range, expected, starts in [(False, b'complete', [0, 0]), (True, b'oldcomplete', [0, 3])]:
            with self.subTest(supports_range=supports_range), TemporaryDirectory() as folder:
                download = BaseDirectDownload.__new__(BaseDirectDownload)
                download._files = [str(Path(folder) / 'file')]
                download._size = len(expected)
                download._supports_range_header = supports_range
                download._fetch_pure_link = Mock(side_effect=[Response(True), Response(False)])
                with patch('backend.implementations.download_clients.base.WebSocket', return_value=Mock()), \
                    patch('backend.implementations.download_clients.base.QueueStatusEvent'):
                    download.run()
                self.assertEqual(Path(download.files[0]).read_bytes(), expected)
                self.assertEqual([call.kwargs['start_byte'] for call in download._fetch_pure_link.call_args_list], starts)
                self.assertEqual(download.state, DownloadState.DOWNLOADING_STATE)

    def test_search_removes_stopped_indexers_without_losing_pairing(self):
        async def run_case(actions):
            stopped = []

            class Indexer:
                def __init__(self, name): self.name = name
                async def shutdown(self): stopped.append(self.name)
                async def search(self, query): return self.name
            teams = []
            for name, action in actions:
                teams.append({'indexer': Indexer(name),
                    'search_action_planner': SimpleNamespace(next_action=lambda a=action: (a, {})),
                    'query_builder': SimpleNamespace(next_query=lambda *args, n=name: n)})
            coordinator = SearchCoordinator.__new__(SearchCoordinator)
            coordinator.indexers = teams
            return await coordinator._run_iteration(), stopped
        stop = SearchAction.STOP
        self.assertEqual(asyncio.run(run_case([('a', stop), ('b', stop)])), ([], ['a', 'b']))
        action = next(a for a in SearchAction if a != stop)
        self.assertEqual(asyncio.run(run_case([('a', stop), ('b', stop), ('c', action)])), ([('c', 'c')], ['a', 'b']))
