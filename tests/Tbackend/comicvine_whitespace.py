import unittest

from backend.implementations.comicvine import ComicVine, _normalise_metadata_text


class ComicVineMetadataWhitespace(unittest.TestCase):
    def test_collapses_repeated_whitespace(self):
        self.assertEqual(
            _normalise_metadata_text('  Lady Death:  Extinction\tExpress  '),
            'Lady Death: Extinction Express'
        )

    def test_volume_metadata_collapses_whitespace(self):
        comicvine = ComicVine.__new__(ComicVine)
        result = comicvine._ComicVine__format_volume_output({
            'id': 123,
            'name': 'Lady Death:  Extinction Express',
            'start_year': '2015',
            'deck': '',
            'description': '',
            'image': {'small_url': 'https://example.test/cover.jpg'},
            'site_detail_url': 'https://example.test/volume/123',
            'aliases': 'Lady Death:  Extinction Express\r\nLD:\tExtinction Express',
            'publisher': {'name': 'Coffin  Comics'},
            'count_of_issues': 1
        })

        self.assertEqual(result['title'], 'Lady Death: Extinction Express')
        self.assertEqual(result['publisher'], 'Coffin Comics')
        self.assertEqual(
            result['aliases'],
            ['Lady Death: Extinction Express', 'LD: Extinction Express']
        )

    def test_issue_title_collapses_whitespace(self):
        comicvine = ComicVine.__new__(ComicVine)
        comicvine.date_type = 'cover_date'
        result = comicvine._ComicVine__format_issue_output({
            'id': 456,
            'volume': {'id': 123},
            'issue_number': '1',
            'name': 'Chapter  One:\tExtinction',
            'cover_date': '2016-10-01',
            'store_date': None,
            'description': ''
        })

        self.assertEqual(result['title'], 'Chapter One: Extinction')


if __name__ == '__main__':
    unittest.main()
