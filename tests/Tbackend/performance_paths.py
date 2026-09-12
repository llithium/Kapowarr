import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.base.definitions import (LibraryFilter, LibrarySorting,
                                      SpecialVersion)
from backend.base.files import filter_scannable_paths
from backend.implementations.file_matching import scan_files
from backend.implementations.matching import match_title
from backend.implementations.volumes import Library
from backend.internals.db import DB_SCHEMA, KapowarrCursor


class PerformancePaths(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(DB_SCHEMA)
        self.cursor = self.db.cursor(factory=KapowarrCursor)
        self.db.executemany(
            'INSERT INTO volumes(id, comicvine_id, title, root_folder, monitored) VALUES (?, ?, ?, 1, ?)',
            [(1, 101, 'The Batman & Robin', 1), (2, 102, 'Saga', 1), (3, 103, 'Batman', 0)]
        )
        self.db.executemany(
            'INSERT INTO issues(id, volume_id, comicvine_id, issue_number, calculated_issue_number) VALUES (?, 1, ?, ?, ?)',
            [(i, i, str(n), n) for i, n in enumerate([1, 1.5, 1.5, 2, 3], 1)]
        )
        self.db.execute("INSERT INTO files VALUES (1, '/comic.cbz', 100)")
        self.db.executemany('INSERT INTO issues_files(file_id, issue_id) VALUES (1, ?)', [(1,), (2,)])

    def tearDown(self):
        self.db.close()

    def test_search_preserves_matching_sorting_filters_and_shared_file_totals(self):
        with patch('backend.implementations.volumes.get_db', return_value=self.cursor):
            for sort in LibrarySorting:
                for filter in (None, LibraryFilter.MONITORED, LibraryFilter.WANTED):
                    for query in ('batman', 'batman robin', 'the', 'absent'):
                        expected = [v for v in Library.get_public_volumes(sort, filter)
                                    if match_title(v['title'], query, allow_contains=True)]
                        self.assertEqual(Library.search(query, sort, filter), expected)
            self.assertEqual(Library.search('cv:101')[0]['total_size'], 100)
            statements = []
            self.db.set_trace_callback(statements.append)
            self.assertEqual(Library.search('absent'), [])
            self.assertEqual(len(statements), 1)

    def test_targeted_paths_ignore_hidden_missing_outside_and_duplicate_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'volume'
            folder.mkdir()
            paths = [folder / 'Comic.CBZ', folder / '.Comic.cbz', folder / 'notes.txt', root / 'outside.cbz']
            (folder / '.hidden').mkdir()
            paths.append(folder / '.hidden' / 'Comic.cbz')
            for path in paths:
                path.touch()
            paths.append(folder / 'missing.cbz')
            with patch('backend.base.files.scandir', side_effect=AssertionError('unexpected traversal')):
                self.assertEqual(filter_scannable_paths(str(folder), map(str, paths + paths)), [str(paths[0])])

    def test_targeted_scan_preserves_fractional_duplicate_and_existing_bindings(self):
        with tempfile.TemporaryDirectory() as folder:
            file = str(Path(folder) / 'Batman 1.5-2.cbz')
            Path(file).touch()
            self.db.execute('INSERT INTO files VALUES (2, ?, 100)', (file,))
            issues = [SimpleNamespace(id=i, calculated_issue_number=n, date=None)
                      for i, n in enumerate([1, 1.5, 1.5, 2, 3], 1)]
            volume = SimpleNamespace(
                get_data=lambda: SimpleNamespace(folder=folder, special_version=SpecialVersion.NORMAL),
                get_issues=lambda **kwargs: issues,
                get_all_files=lambda: [{'filepath': file, 'id': 2}]
            )
            settings = SimpleNamespace(delete_empty_folders=False, unmonitor_deleted_issues=False)
            metadata = {'issue_number': (1.5, 2), 'special_version': None}
            with patch('backend.implementations.volumes.Volume', return_value=volume), \
                    patch('backend.implementations.file_matching.get_db', return_value=self.cursor), \
                    patch('backend.implementations.file_matching.Settings') as config, \
                    patch('backend.implementations.file_matching.extract_filename_data', return_value=metadata), \
                    patch('backend.implementations.file_matching.file_importing_filter', return_value=True), \
                    patch('backend.implementations.file_matching.refine_special_version', return_value=metadata), \
                    patch('backend.implementations.file_matching.commit'), \
                    patch('backend.implementations.file_matching.list_files', side_effect=AssertionError('unexpected traversal')):
                config.return_value.get_settings.return_value = settings
                scan_files(1, [file], del_unmatched_files=False)
            self.assertEqual([tuple(r) for r in self.db.execute('SELECT file_id, issue_id FROM issues_files ORDER BY file_id, issue_id')],
                             [(1, 1), (1, 2), (2, 2), (2, 3), (2, 4)])
