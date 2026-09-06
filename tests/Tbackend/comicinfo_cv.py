import unittest
from asyncio import run
from unittest.mock import AsyncMock, Mock, patch

from backend.implementations.comicinfo_cv import match_comicinfo_ids


class ComicInfoComicVineMatching(unittest.TestCase):
    @staticmethod
    def _file_data(series='Batman'):
        return {
            'series': series,
            'year': None,
            'volume_number': None,
            'special_version': None,
            'issue_number': 1.0,
            'annual': False
        }

    @staticmethod
    def _volume_result(comicvine_id=796):
        return {
            'comicvine_id': comicvine_id,
            'title': 'Batman',
            'year': 1940,
            'volume_number': 1,
            'cover_link': '',
            'cover': None,
            'description': '',
            'site_url': f'https://comicvine.example/4050-{comicvine_id}',
            'aliases': [],
            'publisher': 'DC Comics',
            'issue_count': 715,
            'translated': False,
            'already_added': None,
            'issues': None
        }

    def test_direct_volume_id_fetches_exact_volume(self):
        filepath = '/imports/Batman Issue 001.cbz'
        groups = {1: {filepath: self._file_data()}}
        metadata = {
            filepath: {
                'series': 'Batman',
                'comicvine_volume_id': 796
            }
        }
        comicvine = Mock()
        comicvine.search_volumes = AsyncMock(
            return_value=[self._volume_result()]
        )

        result = run(match_comicinfo_ids(comicvine, groups, metadata))

        self.assertEqual(result[1]['id'], 796)
        self.assertEqual(result[1]['match_source'], 'comicinfo-id')
        self.assertEqual(result[1]['confidence'], 100)
        self.assertTrue(result[1]['direct_id'])
        comicvine.search_volumes.assert_awaited_once_with(
            '4050-796',
            allow_rate_limit_reached=True
        )

    def test_issue_ids_resolve_to_one_parent_volume(self):
        first = '/imports/Batman Issue 001.cbz'
        second = '/imports/Batman Issue 002.cbz'
        groups = {
            1: {
                first: self._file_data(),
                second: self._file_data()
            }
        }
        metadata = {
            first: {'series': 'Batman', 'comicvine_issue_id': 934000},
            second: {'series': 'Batman', 'comicvine_issue_id': 934001}
        }
        comicvine = Mock()
        comicvine.search_volumes = AsyncMock(
            return_value=[self._volume_result()]
        )

        with patch(
            'backend.implementations.comicinfo_cv._fetch_issue_volume_ids',
            new=AsyncMock(return_value={934000: 796, 934001: 796})
        ):
            result = run(match_comicinfo_ids(comicvine, groups, metadata))

        self.assertEqual(result[1]['id'], 796)
        self.assertEqual(
            result[1]['match_reason'],
            'ComicVine issue ID from ComicInfo.xml'
        )

    def test_issue_ids_from_multiple_volumes_fall_back(self):
        first = '/imports/Batman Issue 001.cbz'
        second = '/imports/Batman Issue 002.cbz'
        groups = {
            1: {
                first: self._file_data(),
                second: self._file_data()
            }
        }
        metadata = {
            first: {'series': 'Batman', 'comicvine_issue_id': 934000},
            second: {'series': 'Batman', 'comicvine_issue_id': 934001}
        }
        comicvine = Mock()
        comicvine.search_volumes = AsyncMock()

        with patch(
            'backend.implementations.comicinfo_cv._fetch_issue_volume_ids',
            new=AsyncMock(return_value={934000: 796, 934001: 999})
        ):
            result = run(match_comicinfo_ids(comicvine, groups, metadata))

        self.assertEqual(result, {})
        comicvine.search_volumes.assert_not_awaited()

    def test_unresolved_issue_id_falls_back(self):
        filepath = '/imports/Batman Issue 001.cbz'
        groups = {1: {filepath: self._file_data()}}
        metadata = {
            filepath: {'series': 'Batman', 'comicvine_issue_id': 934000}
        }
        comicvine = Mock()
        comicvine.search_volumes = AsyncMock()

        with patch(
            'backend.implementations.comicinfo_cv._fetch_issue_volume_ids',
            new=AsyncMock(return_value={})
        ):
            result = run(match_comicinfo_ids(comicvine, groups, metadata))

        self.assertEqual(result, {})
        comicvine.search_volumes.assert_not_awaited()
