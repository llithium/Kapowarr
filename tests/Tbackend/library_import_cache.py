import unittest
from asyncio import run
from unittest.mock import AsyncMock, Mock, patch

from backend.implementations.comicinfo import read_comicinfo
from backend.implementations.comicinfo_cv import (_fetch_issue_volume_ids,
                                                   match_comicinfo_ids)


class LibraryImportCheckpointing(unittest.TestCase):
    @staticmethod
    def _file_data():
        return {
            'series': 'Batman',
            'year': None,
            'volume_number': None,
            'special_version': None,
            'issue_number': 1.0,
            'annual': False
        }

    @staticmethod
    def _cached_volume():
        return {
            'comicvine_id': 796,
            'title': 'Batman',
            'year': 1940,
            'issue_count': 715,
            'site_url': 'https://comicvine.example/4050-796',
            'already_added': None
        }

    def test_comicinfo_cache_hit_does_not_open_archive(self):
        metadata = {
            'series': 'Batman',
            'issue_number': '1',
            'comicvine_issue_id': 684877
        }

        with (
            patch(
                'backend.implementations.comicinfo.get_cached_comicinfo',
                return_value=metadata
            ),
            patch(
                'backend.implementations.comicinfo._read_zip_comicinfo'
            ) as archive_reader
        ):
            result = read_comicinfo('/library/Batman Issue 001.cbz')

        self.assertEqual(result, metadata)
        archive_reader.assert_not_called()

    def test_successful_comicinfo_parse_is_checkpointed(self):
        xml = b'''<ComicInfo>
    <Series>Batman: Knightfall: 25th Anniversary Edition</Series>
    <Number>1</Number>
    <Web>https://comicvine.gamespot.com/example/4000-684877/</Web>
</ComicInfo>'''

        with (
            patch(
                'backend.implementations.comicinfo.get_cached_comicinfo',
                return_value=None
            ),
            patch(
                'backend.implementations.comicinfo._read_zip_comicinfo',
                return_value=xml
            ),
            patch(
                'backend.implementations.comicinfo.store_cached_comicinfo'
            ) as store
        ):
            result = read_comicinfo('/library/Batman Issue 001.cbz')

        self.assertEqual(result['comicvine_issue_id'], 684877)
        store.assert_called_once_with(
            '/library/Batman Issue 001.cbz',
            result
        )

    def test_cached_issue_parent_mapping_skips_comicvine_request(self):
        comicvine = Mock()

        with patch(
            'backend.implementations.comicinfo_cv.get_cached_issue_volume_ids',
            return_value={684877: 112233, 684878: 112233}
        ):
            result = run(_fetch_issue_volume_ids(
                comicvine,
                {684877, 684878}
            ))

        self.assertEqual(
            result,
            {684877: 112233, 684878: 112233}
        )

    def test_cached_exact_volume_skips_repeat_volume_lookup(self):
        filepath = '/library/Batman Issue 001.cbz'
        groups = {1: {filepath: self._file_data()}}
        metadata = {
            filepath: {
                'series': 'Batman',
                'comicvine_volume_id': 796
            }
        }
        comicvine = Mock()
        comicvine.search_volumes = AsyncMock()

        with patch(
            'backend.implementations.comicinfo_cv.get_cached_cv_volumes',
            return_value={796: self._cached_volume()}
        ):
            result = run(match_comicinfo_ids(comicvine, groups, metadata))

        self.assertEqual(result[1]['id'], 796)
        self.assertEqual(result[1]['match_source'], 'comicinfo-id')
        comicvine.search_volumes.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
