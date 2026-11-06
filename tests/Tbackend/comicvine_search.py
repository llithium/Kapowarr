import asyncio
import sqlite3
import unittest
from unittest.mock import patch

from backend.implementations.comicvine import ComicVine


class ComicVineSearch(unittest.TestCase):
    def test_search_includes_newer_years_beyond_first_fifty_results(self):
        volumes = [{
            'id': index + 1,
            'name': 'Lady Death',
            'start_year': '2025' if index < 50 else '2026',
            'deck': '',
            'description': '',
            'image': {'small_url': 'https://example.test/cover.jpg'},
            'site_detail_url': 'https://example.test/volume',
            'count_of_issues': 1
        } for index in range(100)]

        async def search_page(session, path, params, default):
            self.assertEqual(path, '/search')
            self.assertEqual(params['query'], 'lady death')
            return {'results': volumes[:params['limit']]}

        comicvine = ComicVine.__new__(ComicVine)
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE volumes (comicvine_id INTEGER, id INTEGER)')
            db.executemany(
                'INSERT INTO volumes VALUES (?, ?)',
                ((index, index + 1000) for index in range(1, 101))
            )
            with patch.object(
                comicvine, '_ComicVine__call_api', side_effect=search_page
            ), patch(
                'backend.implementations.comicvine.get_db',
                return_value=db.cursor()
            ), patch(
                'backend.implementations.comicvine.AsyncSession'
            ):
                results = asyncio.run(comicvine.search_volumes('lady death'))

        self.assertIn(2026, {result['year'] for result in results})
        self.assertEqual(len(results), 100)
        self.assertTrue(all(
            result['already_added'] == result['comicvine_id'] + 1000
            for result in results
        ))


if __name__ == '__main__':
    unittest.main()
