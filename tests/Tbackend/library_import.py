import unittest
from os import makedirs, remove
from os.path import exists, isfile, join
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from backend.base.custom_exceptions import InvalidKeyValue, VolumeAlreadyAdded
from backend.base.definitions import MonitorScheme
from backend.features.library_import import (_find_existing_volume_match,
                                             _source_folder_is_shared,
                                             create_groups, import_library,
                                             propose_library_import)


class ExistingLibraryImportMatch(unittest.TestCase):
    @staticmethod
    def _volume(
        comicvine_id,
        title,
        year,
        volume_number,
        issue_year,
        publisher='DC Comics',
        issue_comicvine_id=9001
    ):
        volume_data = SimpleNamespace(
            comicvine_id=comicvine_id,
            title=title,
            alt_title=None,
            year=year,
            volume_number=volume_number,
            publisher=publisher,
            site_url=f'https://comicvine.example/volume/{comicvine_id}'
        )
        issue = SimpleNamespace(
            comicvine_id=issue_comicvine_id,
            calculated_issue_number=85.0,
            date=f'{issue_year}-01-01'
        )
        return SimpleNamespace(
            vd=volume_data,
            get_issues=lambda _skip_files=False: [issue]
        )

    def test_direct_volume_id_overrides_fuzzy_title(self):
        filepath = '/imports/Wrong Series Issue 085.cbz'
        files = {
            filepath: {
                'series': 'Wrong Series',
                'year': None,
                'volume_number': None,
                'special_version': None,
                'issue_number': 85.0,
                'annual': False
            }
        }
        metadata = {
            filepath: {
                'series': 'Wrong Series',
                'issue_number': '85',
                'comicvine_volume_id': 1002
            }
        }
        volumes = {
            1: self._volume(1001, 'Wrong Series', 2016, 1, 2020),
            2: self._volume(1002, 'Batman', 2016, 3, 2020)
        }

        with patch(
            'backend.features.library_import.Library.get_volume',
            side_effect=lambda volume_id: volumes[volume_id]
        ):
            result = _find_existing_volume_match(files, metadata, [1, 2])

        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 1002)
        self.assertEqual(result['already_added'], 2)
        self.assertEqual(result['match_source'], 'comicinfo-id')
        self.assertEqual(result['confidence'], 100)
        self.assertTrue(result['direct_id'])

    def test_direct_issue_id_finds_existing_parent_volume(self):
        filepath = '/imports/Wrong Series Issue 085.cbz'
        files = {
            filepath: {
                'series': 'Wrong Series',
                'year': None,
                'volume_number': None,
                'special_version': None,
                'issue_number': 85.0,
                'annual': False
            }
        }
        metadata = {
            filepath: {
                'series': 'Wrong Series',
                'issue_number': '85',
                'comicvine_issue_id': 934000
            }
        }
        volumes = {
            1: self._volume(
                1001, 'Wrong Series', 2016, 1, 2020,
                issue_comicvine_id=100000
            ),
            2: self._volume(
                1002, 'Batman', 2016, 3, 2020,
                issue_comicvine_id=934000
            )
        }

        with patch(
            'backend.features.library_import.Library.get_volume',
            side_effect=lambda volume_id: volumes[volume_id]
        ):
            result = _find_existing_volume_match(files, metadata, [1, 2])

        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 1002)
        self.assertEqual(result['already_added'], 2)
        self.assertEqual(result['match_source'], 'comicinfo-id')
        self.assertEqual(result['confidence'], 100)

    def test_issue_year_disambiguates_existing_runs(self):
        files = {
            '/imports/Batman (2020) Issue 085.cbz': {
                'series': 'Batman',
                'year': None,
                'volume_number': None,
                'special_version': None,
                'issue_number': 85.0,
                'annual': False
            }
        }
        metadata = {
            '/imports/Batman (2020) Issue 085.cbz': {
                'series': 'Batman',
                'issue_number': '85',
                'year': 2020,
                'publisher': 'DC Comics'
            }
        }
        volumes = {
            1: self._volume(1001, 'Batman', 2016, 3, 2020),
            2: self._volume(1002, 'Batman', 1940, 1, 1948)
        }

        with patch(
            'backend.features.library_import.Library.get_volume',
            side_effect=lambda volume_id: volumes[volume_id]
        ):
            result = _find_existing_volume_match(files, metadata, [1, 2])

        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 1001)
        self.assertEqual(result['already_added'], 1)
        self.assertEqual(result['match_source'], 'existing-library')

    def test_ambiguous_existing_runs_are_not_auto_selected(self):
        files = {
            '/imports/Batman (2020) Issue 085.cbz': {
                'series': 'Batman',
                'year': None,
                'volume_number': None,
                'special_version': None,
                'issue_number': 85.0,
                'annual': False
            }
        }
        metadata = {
            '/imports/Batman (2020) Issue 085.cbz': {
                'series': 'Batman',
                'issue_number': '85',
                'year': 2020,
                'publisher': 'DC Comics'
            }
        }
        volumes = {
            1: self._volume(1001, 'Batman', 2016, 3, 2020),
            2: self._volume(1002, 'Batman', 2020, 4, 2020)
        }

        with patch(
            'backend.features.library_import.Library.get_volume',
            side_effect=lambda volume_id: volumes[volume_id]
        ):
            result = _find_existing_volume_match(files, metadata, [1, 2])

        self.assertIsNone(result)

    def test_missing_issue_is_not_auto_matched(self):
        files = {
            '/imports/Example Issue 099.cbz': {
                'series': 'Example',
                'year': None,
                'volume_number': None,
                'special_version': None,
                'issue_number': 99.0,
                'annual': False
            }
        }
        metadata = {}
        volume = self._volume(2001, 'Example', 2020, 1, 2020)

        with patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume
        ):
            result = _find_existing_volume_match(files, metadata, [1])

        self.assertIsNone(result)


class LibraryImportGrouping(unittest.TestCase):
    def test_equivalent_data_with_different_mapping_order_shares_group(self):
        first = {
            'series': 'Batman', 'year': None, 'volume_number': 1,
            'special_version': None, 'issue_number': 1.0, 'annual': False
        }
        second = {
            'annual': False, 'issue_number': 2.0, 'special_version': None,
            'volume_number': 1, 'year': None, 'series': 'Batman'
        }

        groups = create_groups({'first.cbz': first, 'second.cbz': second})

        self.assertEqual(list(groups), [1])
        self.assertEqual(list(groups[1]), ['first.cbz', 'second.cbz'])


class LibraryImportScanErrors(unittest.TestCase):
    def test_lazy_not_a_directory_error_becomes_invalid_filter(self):
        with patch(
            'backend.features.library_import.RootFolders.get_folder_list',
            return_value=['/library']
        ), patch(
            'backend.features.library_import.FilesDB.fetch',
            return_value=[]
        ), patch(
            'backend.features.library_import.list_files',
            side_effect=NotADirectoryError('/library/file.cbz')
        ):
            with self.assertRaises(InvalidKeyValue):
                propose_library_import()


class ImportSourceFolderHandling(unittest.TestCase):
    def test_flat_staging_folder_with_multiple_volumes_is_shared(self):
        imports = {
            1001: [
                "/comics/New folder/Brian Pulido's Lady Death_ Blacklands (2006) Issue 001.cbr",
                "/comics/New folder/Brian Pulido's Lady Death_ Blacklands (2006) Issue 002.cbr"
            ],
            2002: [
                '/comics/New folder/Lady Death (2012) Issue 021.cbr'
            ]
        }

        self.assertTrue(_source_folder_is_shared(1001, imports[1001], imports))
        self.assertTrue(_source_folder_is_shared(2002, imports[2002], imports))

    def test_dedicated_series_folders_are_not_shared(self):
        imports = {
            1001: [
                '/comics/Blacklands/Issue 001.cbr',
                '/comics/Blacklands/Issue 002.cbr'
            ],
            2002: [
                '/comics/Lady Death/Issue 021.cbr'
            ]
        }

        self.assertFalse(_source_folder_is_shared(1001, imports[1001], imports))
        self.assertFalse(_source_folder_is_shared(2002, imports[2002], imports))


class PublicLibraryImportFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = self.temp_dir.name
        self.source = join(self.root, 'inbox')
        self.destination = join(self.root, 'Batman')
        makedirs(self.source)
        self.filepath = join(self.source, 'Batman Issue 001.cbz')
        with open(self.filepath, 'wb') as comic:
            comic.write(b'comic')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_import_moves_files_for_existing_volume_and_runs_rename(self):
        root_folder = SimpleNamespace(folder=self.root, id=7)
        volume = SimpleNamespace(vd=SimpleNamespace(folder=self.destination))
        match = {'id': 796, 'filepath': self.filepath}

        with patch(
            'backend.features.library_import.RootFolders.get_all',
            return_value=[root_folder]
        ), patch(
            'backend.features.library_import.Library.add',
            side_effect=VolumeAlreadyAdded(796, 11)
        ), patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume
        ), patch(
            'backend.features.library_import.scan_files'
        ) as scan, patch(
            'backend.features.library_import._match_unmatched_comicinfo_files'
        ), patch(
            'backend.features.library_import.mass_rename'
        ) as rename:
            import_library([match], rename_files=True)

        moved = join(self.destination, 'Batman Issue 001.cbz')
        self.assertTrue(isfile(moved))
        self.assertFalse(exists(self.filepath))
        scan.assert_called_once_with(11, filepath_filter=[moved])
        rename.assert_called_once_with(11, filepath_filter=[moved])

    def test_import_keeps_existing_file_and_reports_conflict(self):
        root_folder = SimpleNamespace(folder=self.root, id=7)
        volume = SimpleNamespace(vd=SimpleNamespace(folder=self.destination))
        match = {'id': 796, 'filepath': self.filepath}
        makedirs(self.destination)
        destination = join(self.destination, 'Batman Issue 001.cbz')
        with open(destination, 'wb') as comic:
            comic.write(b'existing comic')

        with patch(
            'backend.features.library_import.RootFolders.get_all',
            return_value=[root_folder]
        ), patch(
            'backend.features.library_import.Library.add',
            side_effect=VolumeAlreadyAdded(796, 11)
        ), patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume
        ), patch(
            'backend.features.library_import.scan_files'
        ) as scan:
            conflicts = import_library([match])

        self.assertTrue(isfile(self.filepath))
        with open(destination, 'rb') as comic:
            self.assertEqual(comic.read(), b'existing comic')
        self.assertEqual(conflicts, [{
            'filepath': self.filepath,
            'destination': destination,
            'message': (
                'A file with this name is already in the Kapowarr volume '
                'folder.'
            )
        }])
        scan.assert_not_called()

    def test_propose_scans_file_directly_in_root_and_returns_match(self):
        remove(self.filepath)
        root_filepath = join(self.root, 'Batman Issue 002.cbz')
        with open(root_filepath, 'wb') as comic:
            comic.write(b'comic')
        file_data = {
            'series': 'Batman', 'year': None, 'volume_number': None,
            'special_version': None, 'issue_number': 1.0, 'annual': False
        }
        cv_match = {
            'id': 796, 'title': 'Batman (1940)', 'issue_count': 1,
            'link': 'https://comicvine.example/4050-796',
            'already_added': None
        }
        comicvine = Mock()
        comicvine.filenames_to_cvs = AsyncMock(return_value={1: cv_match})
        comicvine_ids = AsyncMock(return_value={})

        with patch(
            'backend.features.library_import.RootFolders.get_folder_list',
            return_value=[self.root]
        ), patch(
            'backend.features.library_import.FilesDB.fetch',
            return_value=[]
        ), patch(
            'backend.features.library_import.extract_filename_data',
            return_value=file_data
        ), patch(
            'backend.features.library_import.read_comicinfo',
            return_value=None
        ), patch(
            'backend.features.library_import.Library.get_volumes',
            return_value=[]
        ), patch(
            'backend.features.library_import.ComicVine', return_value=comicvine
        ), patch(
            'backend.features.library_import.match_comicinfo_ids',
            new=comicvine_ids
        ):
            result = propose_library_import()

        self.assertEqual(result[0]['filepath'], root_filepath)
        self.assertEqual(result[0]['cv']['id'], 796)

    def test_import_moves_root_file_to_dedicated_volume_folder(self):
        root_filepath = join(self.root, 'Batman Issue 002.cbz')
        with open(root_filepath, 'wb') as comic:
            comic.write(b'comic')

        root_folder = SimpleNamespace(folder=self.root, id=7)
        volume = SimpleNamespace(vd=SimpleNamespace(folder=self.destination))
        match = {'id': 796, 'filepath': root_filepath}

        with patch(
            'backend.features.library_import.RootFolders.get_all',
            return_value=[root_folder]
        ), patch(
            'backend.features.library_import.Library.add',
            return_value=11
        ) as add, patch(
            'backend.features.library_import.commit'
        ), patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume
        ), patch(
            'backend.features.library_import.scan_files'
        ) as scan, patch(
            'backend.features.library_import._match_unmatched_comicinfo_files'
        ):
            conflicts = import_library([match])

        moved = join(self.destination, 'Batman Issue 002.cbz')
        self.assertEqual(conflicts, [])
        self.assertTrue(isfile(moved))
        self.assertFalse(isfile(root_filepath))
        add.assert_called_once_with(
            comicvine_id=796,
            root_folder_id=7,
            monitored=False,
            monitor_scheme=MonitorScheme.NONE,
            monitor_new_issues=False,
            volume_folder=None
        )
        scan.assert_called_once_with(11, filepath_filter=[moved])
