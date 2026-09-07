import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.library_import import (
    _find_existing_volume_match,
    _group_is_already_tracked,
)
from backend.implementations.comicinfo import comicinfo_to_filename_data


def file_data(series='Example', year=2020, issue_number=1.0):
    return {
        'series': series,
        'year': year,
        'volume_number': 1,
        'special_version': None,
        'issue_number': issue_number,
        'annual': False,
    }


class ExistingImportFiltering(unittest.TestCase):
    def test_library_import_keeps_filename_series_year(self):
        fallback = file_data(series='Worlds Finest', year=2013)
        result = comicinfo_to_filename_data(
            {'series': "Worlds' Finest", 'year': 2014},
            fallback,
            for_library_import=True,
        )
        self.assertEqual(result['year'], 2013)

    def test_direct_issue_already_with_file_is_skipped(self):
        filepath = '/comics/Example/Example 001.cbz'
        files = {filepath: file_data()}
        metadata = {
            filepath: {
                'comicvine_issue_id': 9001,
                'comicvine_volume_id': 1001,
            }
        }
        issue = SimpleNamespace(
            comicvine_id=9001,
            calculated_issue_number=1.0,
            files=[{'filepath': '/old/path/Example 001.cbz'}],
        )
        volume = SimpleNamespace(get_issues=lambda: [issue])

        with patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume,
        ):
            self.assertTrue(
                _group_is_already_tracked(files, metadata, 12)
            )

    def test_direct_new_issue_in_existing_volume_is_not_skipped(self):
        filepath = '/imports/Example 002.cbz'
        files = {filepath: file_data(issue_number=2.0)}
        metadata = {
            filepath: {
                'comicvine_issue_id': 9002,
                'comicvine_volume_id': 1001,
            }
        }
        issue = SimpleNamespace(
            comicvine_id=9002,
            calculated_issue_number=2.0,
            files=[],
        )
        volume = SimpleNamespace(get_issues=lambda: [issue])

        with patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume,
        ):
            self.assertFalse(
                _group_is_already_tracked(files, metadata, 12)
            )

    def test_far_apart_series_year_is_not_fuzzy_matched(self):
        filepath = "/imports/Worlds' Finest (2013) Volume 001.cbz"
        files = {
            filepath: file_data(
                series="Worlds' Finest",
                year=2013,
                issue_number=1.0,
            )
        }
        volume_data = SimpleNamespace(
            comicvine_id=1990,
            title="Worlds' Finest",
            alt_title=None,
            year=1990,
            volume_number=1,
            publisher='DC Comics',
            site_url='https://example.invalid/1990',
        )
        issue = SimpleNamespace(
            comicvine_id=5001,
            calculated_issue_number=1.0,
            date='1990-01-01',
        )
        volume = SimpleNamespace(
            vd=volume_data,
            get_issues=lambda _skip_files=False: [issue],
        )

        with patch(
            'backend.features.library_import.Library.get_volume',
            return_value=volume,
        ):
            result = _find_existing_volume_match(files, {}, [1])

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
