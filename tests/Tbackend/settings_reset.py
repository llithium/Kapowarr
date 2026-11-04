import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

from backend.internals.server import StartType
from frontend.api import api


class SettingsResetTests(unittest.TestCase):
    def test_reset_restarts_only_for_changed_hosting_or_proxy_values(self):
        app = Flask(__name__)
        app.register_blueprint(api, url_prefix='/api')
        settings = Mock()
        settings.sv = SimpleNamespace(host='127.0.0.1', proxy_host='proxy')
        settings.get_default_value.side_effect = {'host': '0.0.0.0', 'proxy_host': ''}.get
        settings.get_public_settings.return_value.todict.return_value = {}
        server = Mock()
        with patch('frontend.api.Settings', return_value=settings), \
            patch('frontend.api.Server', return_value=server), \
            patch('frontend.api.extract_key'), \
            patch('frontend.api.StartTypeHandlers.diffuse_timer'):
            client = app.test_client()
            response = client.delete('/api/settings?api_key=test', json={'reset_keys': ['host']})
            self.assertEqual(response.status_code, 200)
            settings.backup_hosting_settings.assert_called_once()
            server.restart.assert_called_once_with(StartType.RESTART_HOSTING_CHANGES)
            settings.reset.assert_called_once_with('host', from_public=True)

            settings.reset_mock()
            server.reset_mock()
            response = client.delete('/api/settings?api_key=test', json={'reset_keys': ['proxy_host']})
            self.assertEqual(response.status_code, 200)
            settings.backup_hosting_settings.assert_not_called()
            server.restart.assert_called_once_with()
            settings.reset.assert_called_once_with('proxy_host', from_public=True)

            settings.reset_mock()
            server.reset_mock()
            settings.sv.host = '0.0.0.0'
            response = client.delete('/api/settings?api_key=test', json={'reset_keys': ['host']})
            self.assertEqual(response.status_code, 200)
            server.restart.assert_not_called()


class DatabaseUploadTests(unittest.TestCase):
    def test_multipart_upload_reaches_import_with_file_and_hosting_choice(self):
        from io import BytesIO
        from pathlib import Path
        from tempfile import TemporaryDirectory

        app = Flask(__name__)
        app.register_blueprint(api, url_prefix='/api')
        with TemporaryDirectory() as directory:
            destination = Path(directory) / 'Kapowarr_upload.db'
            with patch('frontend.api.DBConnection.default_file', str(Path(directory) / 'Kapowarr.db')), \
                patch('frontend.api.import_db') as import_db, \
                patch('frontend.api.extract_key'), \
                patch('frontend.api.StartTypeHandlers.diffuse_timer'):
                response = app.test_client().post(
                    '/api/system/database?api_key=test',
                    data={'file': (BytesIO(b'database'), 'backup.db'),
                          'copy_hosting_settings': 'true'},
                    content_type='multipart/form-data'
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(destination.read_bytes(), b'database')
                import_db.assert_called_once_with(str(destination), True)


class TaskRouteTests(unittest.TestCase):
    def test_backup_task_and_invalid_command(self):
        from backend.features.tasks import BackupDatabase

        app = Flask(__name__)
        app.register_blueprint(api, url_prefix='/api')
        handler = Mock()
        handler.add.return_value = 17
        with patch('frontend.api.TaskHandler', return_value=handler), \
            patch('frontend.api.extract_key'), \
            patch('frontend.api.StartTypeHandlers.diffuse_timer'):
            client = app.test_client()
            response = client.post('/api/system/tasks?api_key=test', json={'cmd': 'backup_db'})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json['result']['id'], 17)
            self.assertIsInstance(handler.add.call_args.args[0], BackupDatabase)
            for command in ('unknown', ['backup_db']):
                response = client.post('/api/system/tasks?api_key=test', json={'cmd': command})
                self.assertEqual(response.status_code, 400)
            self.assertEqual(handler.add.call_count, 1)


if __name__ == '__main__':
    unittest.main()
