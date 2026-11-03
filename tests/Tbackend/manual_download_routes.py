import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from flask import Flask

from backend.base.custom_exceptions import IndexerNotFound, InvalidKeyValue
from backend.base.definitions import EnqueuingDownloadFailureReason
from backend.features.download_queue import DownloadHandler
from frontend.api import api


class ManualDownloadRoutes(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(api, url_prefix='/api')
        self.client = app.test_client()

    def test_download_routes_await_handler_and_report_failure(self):
        handler = Mock()
        handler.add = AsyncMock(return_value=([{'id': 8}], None))
        issue = Mock()
        issue.get_data.return_value.volume_id = 7
        body = {'link': 'https://example.test/comic', 'indexer_id': 3, 'force_match': True}
        with patch('frontend.api.extract_key'), patch('frontend.api.StartTypeHandlers.diffuse_timer'), \
            patch('frontend.api.Library.get_volume'), patch('frontend.api.Library.get_issue', return_value=issue), \
            patch('frontend.api.DownloadHandler', return_value=handler):
            for path, issue_id in [('/api/volumes/7/download', None), ('/api/issues/9/download', 9)]:
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json['result'], [{'id': 8}])
                handler.add.assert_awaited_with(body['link'], indexer_id=3, volume_id=7,
                                                issue_id=issue_id, force_match=True)
            handler.add.return_value = ([], EnqueuingDownloadFailureReason.LINK_BROKEN)
            response = self.client.post('/api/volumes/7/download', json=body)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json['error'], 'EnqueuingDownloadFailure')
            self.assertEqual(response.json['result']['reason'], 'link_broken')

    def test_issue_search_uses_volume_and_issue_ids(self):
        issue = Mock()
        issue.get_data.return_value.volume_id = 7
        with patch('frontend.api.extract_key'), patch('frontend.api.StartTypeHandlers.diffuse_timer'), \
            patch('frontend.api.Library.get_issue', return_value=issue), \
            patch('frontend.api.manual_search', return_value=[]) as search:
            response = self.client.get('/api/issues/9/manualsearch')
            self.assertEqual(response.status_code, 200)
            search.assert_called_once_with(7, 9)

    def test_selected_indexer_must_exist_be_enabled_and_match_link(self):
        handler = DownloadHandler.__new__(DownloadHandler)
        handler.queue = []
        handler.settings = SimpleNamespace(sv=SimpleNamespace(downloads_enabled=True))
        indexers = [{'id': 3, 'enabled': True, 'client_type': 'GetComics', 'url': 'https://example.test/base'}]
        with patch('backend.features.download_queue.IndexerClients.get_all_data', return_value=indexers):
            detect = handler._DownloadHandler__determine_link_type
            self.assertEqual(detect('https://example.test/base/comic', 3), 'gc')
            with self.assertRaises(IndexerNotFound):
                detect('https://example.test/base/comic', 4)
            with self.assertRaises(InvalidKeyValue):
                detect('https://example.test/baseless', 3)
            indexers[0]['enabled'] = False
            with self.assertRaises(InvalidKeyValue):
                detect('https://example.test/base/comic', 3)
