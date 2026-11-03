import os
import sqlite3
import unittest
from contextlib import closing
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from flask import Flask
from requests import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.helpers import CommaList, test_proxy_url
from backend.internals.db import (DBConnection, DBConnectionManager, close_db,
                                  get_db, set_db_location, setup_db)
from backend.internals.settings import Settings


class DatabaseTransactions(unittest.TestCase):
    def test_teardown_commits_success_and_rolls_back_failure(self):
        previous_file = DBConnection.default_file
        DBConnectionManager.close_connection_of_thread()
        app = Flask(__name__)
        app.teardown_appcontext(close_db)
        try:
            with TemporaryDirectory() as folder:
                set_db_location(folder)
                with app.app_context():
                    get_db().execute('CREATE TABLE changes (value TEXT)')
                with app.app_context():
                    get_db().execute("INSERT INTO changes VALUES ('complete')")
                with self.assertRaises(RuntimeError):
                    with app.app_context():
                        get_db().execute("INSERT INTO changes VALUES ('partial')")
                        raise RuntimeError('operation failed')
                with closing(sqlite3.connect(DBConnection.default_file)) as connection:
                    self.assertEqual(
                        connection.execute('SELECT value FROM changes').fetchall(),
                        [('complete',)]
                    )
        finally:
            DBConnectionManager.close_connection_of_thread()
            DBConnection.default_file = previous_file


class ProxyValidation(unittest.TestCase):
    def test_probe_preserves_each_environment_value_on_success_and_failure(self):
        for status in (200, 407, None):
            for previous in (
                {},
                {'HTTP_PROXY': 'http://old', 'HTTPS_PROXY': 'https://different',
                 'NO_PROXY': 'localhost'}
            ):
                with self.subTest(status=status, previous=previous):
                    session = Mock()
                    session.__enter__ = Mock(return_value=session)
                    session.__exit__ = Mock(return_value=False)
                    session.get.return_value.status_code = status
                    if status is None:
                        session.get.side_effect = RequestException('unreachable')
                    with patch.dict(os.environ, previous, clear=True), patch(
                        'backend.base.helpers.Session', return_value=session
                    ):
                        if status == 200:
                            test_proxy_url('http://candidate', CommaList('ignore'))
                        else:
                            with self.assertRaises((ClientNotWorking, CredentialInvalid)):
                                test_proxy_url('http://candidate', CommaList('ignore'))
                        self.assertEqual(dict(os.environ), previous)


class SettingsLogging(unittest.TestCase):
    def test_settings_and_generated_keys_do_not_log_secrets(self):
        previous_file = DBConnection.default_file
        DBConnectionManager.close_connection_of_thread()
        app = Flask(__name__)
        app.teardown_appcontext(close_db)
        settings = Settings.__new__(Settings)
        settings.clear_cache()
        try:
            with TemporaryDirectory() as folder, app.app_context():
                set_db_location(folder)
                with patch('backend.internals.settings.LOGGER.info') as info:
                    setup_db()
                    settings.update({'api_key': 'private-key-value'})
                    settings.generate_api_key()
                    generated = settings.sv.api_key
                logged = str(info.call_args_list)
                self.assertNotIn('private-key-value', logged)
                self.assertNotIn(generated, logged)
        finally:
            settings.clear_cache()
            DBConnectionManager.close_connection_of_thread()
            DBConnection.default_file = previous_file
