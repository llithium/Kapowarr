import unittest
from os import makedirs, remove
from os.path import isdir, join
from shutil import rmtree
from tempfile import TemporaryDirectory
from unittest.mock import patch

from flask import Flask

from backend.base.helpers import Singleton
from backend.implementations.file_matching import scan_files
from backend.internals.db import (DBConnection, DBConnectionManager,
                                  close_db, commit, get_db, set_db_location,
                                  setup_db)
from backend.internals.settings import Settings


class ScanRemovesFilesMissingFromDisk(unittest.TestCase):
    """Refresh & scan must drop file records whose files are gone, also when
    the whole volume folder is gone."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = join(self.tmp.name, 'Comics')
        self.volume_folder = join(
            self.root, 'Splitter', 'Vampirella', 'Volume 01 (1998)'
        )
        self.comic = join(
            self.volume_folder, 'Vampirella (1998) Volume 01 Issue 017.cbz'
        )
        makedirs(self.volume_folder)
        with open(self.comic, 'wb') as f:
            f.write(b'comic')

        self._clear_singletons()
        self.app = Flask('scan-missing-files')
        self.app.teardown_appcontext(close_db)
        self.previous_db = DBConnection.default_file
        db_folder = join(self.tmp.name, 'db')
        makedirs(db_folder)
        set_db_location(db_folder)
        self.ctx = self.app.app_context()
        self.ctx.push()
        setup_db()

        cursor = get_db()
        cursor.execute(
            "INSERT INTO root_folders(id, folder) VALUES (1, ?);",
            (self.root + '/',)
        )
        cursor.execute(
            """
            INSERT INTO volumes(
                id, comicvine_id, title, year, publisher, volume_number,
                root_folder, folder, special_version
            ) VALUES (1, 1, 'Vampirella', 1998, 'Splitter', 1, 1, ?, NULL);
            """,
            (self.volume_folder,)
        )
        cursor.execute(
            """
            INSERT INTO issues(
                id, volume_id, comicvine_id, issue_number,
                calculated_issue_number
            ) VALUES (1, 1, 1, '17', 17.0);
            """
        )
        commit()


    def tearDown(self):
        self.ctx.pop()
        DBConnectionManager.close_connection_of_thread()
        DBConnection.default_file = self.previous_db
        self.tmp.cleanup()
        self._clear_singletons()

    @staticmethod
    def _clear_singletons():
        # Root folders and settings are cached per process
        for key in list(Singleton._instances):
            if key.endswith(('.RootFolders', '.Settings')):
                del Singleton._instances[key]

    def _set(self, **values):
        Settings().update(values)

    def _file_count(self):
        return get_db().execute(
            "SELECT COUNT(*) FROM issues_files;"
        ).fetchone()[0], get_db().execute(
            "SELECT COUNT(*) FROM files;"
        ).fetchone()[0]

    def test_file_found_then_removed(self):
        self._set(create_empty_volume_folders=False)
        scan_files(1)
        self.assertEqual(self._file_count(), (1, 1))

        remove(self.comic)
        scan_files(1)
        self.assertEqual(self._file_count(), (0, 0))

    def test_whole_volume_folder_removed(self):
        self._set(create_empty_volume_folders=False)
        scan_files(1)
        self.assertEqual(self._file_count(), (1, 1))

        rmtree(join(self.root, 'Splitter'))
        scan_files(1)
        self.assertEqual(self._file_count(), (0, 0))
        # The setting is off, so the folder isn't recreated
        self.assertFalse(isdir(self.volume_folder))

    def test_manually_matched_file_in_removed_folder(self):
        self._set(create_empty_volume_folders=False)
        scan_files(1)
        get_db().execute("UPDATE issues_files SET forced = 1;")
        commit()

        rmtree(join(self.root, 'Splitter'))
        scan_files(1)
        self.assertEqual(self._file_count(), (0, 0))

    def test_unreachable_root_folder_keeps_records(self):
        self._set(create_empty_volume_folders=False)
        scan_files(1)
        self.assertEqual(self._file_count(), (1, 1))

        # E.g. an unmounted drive or a cloud folder that isn't available
        rmtree(self.root)
        scan_files(1)
        self.assertEqual(self._file_count(), (1, 1))

    def test_refresh_failure_still_scans(self):
        from backend.base.custom_exceptions import InvalidComicVineApiKey
        from backend.implementations import volumes

        self._set(create_empty_volume_folders=False)
        scan_files(1)
        rmtree(join(self.root, 'Splitter'))

        with patch.object(
            volumes, '_refresh_metadata',
            side_effect=InvalidComicVineApiKey
        ):
            with self.assertRaises(InvalidComicVineApiKey):
                volumes.refresh_and_scan(1)

        self.assertEqual(self._file_count(), (0, 0))


if __name__ == '__main__':
    unittest.main()
