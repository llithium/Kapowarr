import sqlite3
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from flask import Flask

from backend.base.custom_exceptions import FolderNotFound, InvalidKeyValue
from backend.internals.db import (DBConnection, DBConnectionManager, get_db,
                                  set_db_location,
                                  setup_db_adapters_and_converters)
from backend.internals.db_backup_import import backup_database, get_backups
from backend.internals.settings import Settings


class DatabaseBackups(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.folder = Path(stack.enter_context(TemporaryDirectory()))
        stack.enter_context(patch.object(DBConnection, 'file', ''))
        stack.enter_context(patch.object(DBConnection, 'default_file', ''))
        stack.enter_context(patch.object(DBConnectionManager, 'instances', {}))
        stack.enter_context(patch.object(Settings, '_instances', {}))
        stack.enter_context(Flask(__name__).app_context())
        self.addCleanup(DBConnectionManager.close_connection_of_thread)
        self.addCleanup(Settings.get_settings.cache_clear)
        self.addCleanup(Settings.get_public_settings.cache_clear)
        set_db_location(str(self.folder))
        setup_db_adapters_and_converters()
        get_db().execute('CREATE TABLE config(key PRIMARY KEY, value BLOB);')
        get_db().execute('CREATE TABLE example(value TEXT);')
        get_db().execute("INSERT INTO example VALUES ('preserved');")
        get_db().connection.commit()
        self.settings = Settings()

    def test_scheduled_backup_creates_readable_copy_in_data_folder(self):
        backup_database()

        backups = get_backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(Path(backups[0]['filepath']).parent, self.folder)
        with sqlite3.connect(backups[0]['filepath']) as backup:
            self.assertEqual(
                backup.execute('SELECT value FROM example;').fetchone(),
                ('preserved',)
            )
        public = self.settings.get_public_settings()
        self.assertEqual(public.db_backup_amount, 3)
        self.assertEqual(Path(public.db_backup_folder), self.folder)

    def test_configured_folder_and_retention_remove_only_oldest_backup(self):
        destination = self.folder / 'backups'
        destination.mkdir()
        self.settings.update({
            'db_backup_folder': str(destination), 'db_backup_amount': 2
        }, from_public=True)
        get_db().connection.commit()
        oldest = destination / 'Kapowarr_2020_01_01_00_00.db'
        newer = destination / 'Kapowarr_2020_01_02_00_00.db'
        unrelated = destination / 'manual.db'
        for file in (oldest, newer, unrelated):
            file.touch()

        backup_database()

        self.assertFalse(oldest.exists())
        self.assertTrue(newer.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(len(get_backups()), 2)

    def test_zero_count_skips_backup_without_deleting_existing_copies(self):
        existing = self.folder / 'Kapowarr_2020_01_01_00_00.db'
        existing.touch()
        self.settings.update({'db_backup_amount': 0}, from_public=True)

        backup_database()

        self.assertTrue(existing.exists())
        self.assertEqual(len(get_backups()), 1)

    def test_invalid_backup_settings_are_rejected(self):
        with self.assertRaises(InvalidKeyValue):
            self.settings.update({'db_backup_amount': -1}, from_public=True)
        with self.assertRaises(FolderNotFound):
            self.settings.update({
                'db_backup_folder': str(self.folder / 'missing')
            }, from_public=True)


if __name__ == '__main__':
    unittest.main()
