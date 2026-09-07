import sqlite3
import unittest
from unittest.mock import patch

from backend.internals.db_models import FilesDB


class FilepathUpdateCollisionHandling(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.execute('PRAGMA foreign_keys = ON;')
        self.connection.executescript("""
            CREATE TABLE files(
                id INTEGER PRIMARY KEY,
                filepath TEXT UNIQUE NOT NULL,
                size INTEGER
            );
            CREATE TABLE volumes(
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE issues(
                id INTEGER PRIMARY KEY
            );
            CREATE TABLE issues_files(
                file_id INTEGER NOT NULL,
                issue_id INTEGER NOT NULL,
                forced BOOL NOT NULL DEFAULT 0,
                FOREIGN KEY (file_id) REFERENCES files(id),
                FOREIGN KEY (issue_id) REFERENCES issues(id),
                PRIMARY KEY (file_id, issue_id)
            );
            CREATE TABLE volume_files(
                file_id INTEGER PRIMARY KEY,
                volume_id INTEGER NOT NULL,
                file_type VARCHAR(15) NOT NULL,
                forced BOOL NOT NULL DEFAULT 0,
                FOREIGN KEY (volume_id) REFERENCES volumes(id),
                FOREIGN KEY (file_id) REFERENCES files(id)
            );
        """)
        self.cursor = self.connection.cursor()

    def tearDown(self):
        self.connection.close()

    def _update(self, mapping):
        with patch(
            'backend.internals.db_models.get_db',
            return_value=self.cursor
        ):
            FilesDB.update_filepaths(mapping)

    def test_existing_destination_row_is_merged(self):
        self.cursor.executemany(
            'INSERT INTO files(id, filepath, size) VALUES (?, ?, ?);',
            (
                (1, '/comics/old.cbz', 100),
                (2, '/comics/new.cbz', 100)
            )
        )
        self.cursor.executemany(
            'INSERT INTO issues(id) VALUES (?);',
            ((10,), (11,))
        )
        self.cursor.execute(
            'INSERT INTO volumes(id) VALUES (?);',
            (99,)
        )
        self.cursor.executemany(
            """
            INSERT INTO issues_files(file_id, issue_id, forced)
            VALUES (?, ?, ?);
            """,
            (
                (1, 10, 0),
                (2, 10, 1),
                (2, 11, 0)
            )
        )
        self.cursor.execute(
            """
            INSERT INTO volume_files(
                file_id, volume_id, file_type, forced
            ) VALUES (?, ?, ?, ?);
            """,
            (2, 99, 'metadata', 1)
        )

        self._update({
            '/comics/old.cbz': '/comics/new.cbz'
        })

        self.assertEqual(
            self.cursor.execute(
                'SELECT id, filepath, size FROM files;'
            ).fetchall(),
            [(1, '/comics/new.cbz', 100)]
        )
        self.assertEqual(
            self.cursor.execute(
                """
                SELECT file_id, issue_id, forced
                FROM issues_files
                ORDER BY issue_id;
                """
            ).fetchall(),
            [(1, 10, 1), (1, 11, 0)]
        )
        self.assertEqual(
            self.cursor.execute(
                """
                SELECT file_id, volume_id, file_type, forced
                FROM volume_files;
                """
            ).fetchall(),
            [(1, 99, 'metadata', 1)]
        )

    def test_chained_renames_do_not_collide(self):
        self.cursor.executemany(
            'INSERT INTO files(id, filepath, size) VALUES (?, ?, ?);',
            (
                (1, '/comics/a.cbz', 10),
                (2, '/comics/b.cbz', 20)
            )
        )

        self._update({
            '/comics/a.cbz': '/comics/b.cbz',
            '/comics/b.cbz': '/comics/c.cbz'
        })

        self.assertEqual(
            self.cursor.execute(
                """
                SELECT id, filepath, size
                FROM files
                ORDER BY id;
                """
            ).fetchall(),
            [
                (1, '/comics/b.cbz', 10),
                (2, '/comics/c.cbz', 20)
            ]
        )


if __name__ == '__main__':
    unittest.main()
