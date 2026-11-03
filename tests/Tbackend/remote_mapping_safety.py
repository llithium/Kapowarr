import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from flask import Flask

from backend.base.custom_exceptions import RemoteMappingInvalid
from backend.implementations.remote_mapping import RemoteMappings
from backend.internals.db import DBConnection


class RemoteMappingSafety(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.context = Flask(__name__).app_context()
        self.context.push()
        self.connection = DBConnection(db_file=os.path.join(self.temp.name, 'test.sqlite'))
        self.cursor = self.connection.cursor()
        self.cursor.executescript('''
            CREATE TABLE external_download_clients (id INTEGER PRIMARY KEY);
            INSERT INTO external_download_clients VALUES (1), (2);
            CREATE TABLE remote_mappings (
                id INTEGER PRIMARY KEY, external_download_client_id INTEGER NOT NULL,
                remote_path TEXT NOT NULL, local_path TEXT NOT NULL,
                FOREIGN KEY (external_download_client_id) REFERENCES external_download_clients(id)
            );
        ''')
        self.db_patch = patch('backend.implementations.remote_mapping.get_db', return_value=self.cursor)
        self.db_patch.start()
        self.first = Path(self.temp.name, 'first_%')
        self.second = Path(self.temp.name, 'second')
        self.first.mkdir()
        self.second.mkdir()

    def tearDown(self):
        self.db_patch.stop()
        self.connection.close()
        self.context.pop()
        self.temp.cleanup()

    def test_literal_paths_and_boundaries(self):
        RemoteMappings.add(1, '/remote_%', str(self.first))
        self.assertEqual(RemoteMappings.remote_to_local(1, '/remote_%/a.cbz'), str(self.first / 'a.cbz'))
        self.assertEqual(RemoteMappings.remote_to_local(1, '/remote_X/a.cbz'), '/remote_X/a.cbz')
        self.assertEqual(RemoteMappings.local_to_remote(1, str(self.first) + 'x/a'), str(self.first) + 'x/a')
        self.assertEqual(RemoteMappings.local_to_remote(1, str(self.first / 'a.cbz')), '/remote_%/a.cbz')
        self.assertEqual(RemoteMappings.remote_to_local(1, '/REMOTE_%/a.cbz'), '/REMOTE_%/a.cbz')

    def test_posix_remote_backslash_is_literal(self):
        RemoteMappings.add(1, r'/remote\name', str(self.first))
        self.assertEqual(RemoteMappings.remote_to_local(1, r'/remote\name/a.cbz'), str(self.first / 'a.cbz'))
        self.assertEqual(RemoteMappings.local_to_remote(1, str(self.first / 'a.cbz')), r'/remote\name/a.cbz')

    def test_windows_remote_uses_windows_case_and_separators(self):
        RemoteMappings.add(1, r'C:\Comics', str(self.first))
        self.assertEqual(RemoteMappings.remote_to_local(1, r'c:\comics\Sub\a.cbz'), str(self.first / 'Sub' / 'a.cbz'))
        self.assertEqual(RemoteMappings.local_to_remote(1, str(self.first / 'a.cbz')), r'C:\Comics\a.cbz')
        with self.assertRaises(RemoteMappingInvalid):
            RemoteMappings.add(1, r'c:\COMICS\child', str(self.second))

    def test_duplicates_and_client_only_update_are_rejected(self):
        RemoteMappings.add(1, '/remote', str(self.first))
        with self.assertRaises(RemoteMappingInvalid):
            RemoteMappings.add(1, '/different', str(self.first))
        with self.assertRaises(RemoteMappingInvalid):
            RemoteMappings.add(1, '/remote', str(self.second))
        other = RemoteMappings.add(2, '/remote/child', str(self.second))
        with self.assertRaises(RemoteMappingInvalid):
            other.update(external_download_client_id=1)
        self.assertEqual(other.get()['external_download_client_id'], 2)
