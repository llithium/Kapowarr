import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.library_import import (_find_existing_volume_match,
                                             _source_folder_is_shared)


class ExistingLibraryImportMatch(unittest.TestCase):
    @staticmethod
    def _volume(
        comicvine_id,
        title,
        year,
        volume_number,
        issue_year,
        publisher='DC Comics'
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
            calculated_issue_number=85.0,
            date=f'{issue_year}-01-01'
        )
        return SimpleNamespace(
            vd=volume_data,
            get_issues=lambda _skip_files=False: [issue]
        )

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
