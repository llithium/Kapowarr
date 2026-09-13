import unittest

from backend.implementations.comicvine import _get_comicvine_volume_number


class ComicVineVolumeNumber(unittest.TestCase):
    def test_known_volumes_without_decks_use_overrides(self):
        expected_volume_numbers = {
            4363: 3,   # Green Lantern (1990)
            18216: 4,  # Green Lantern (2005)
            26374: 3,  # Gen 13 (2002)
            18560: 4,  # Gen 13 (2006)
            60768: 2,  # Aphrodite IX (2013)
        }

        for comicvine_id, expected in expected_volume_numbers.items():
            with self.subTest(comicvine_id=comicvine_id):
                self.assertEqual(
                    _get_comicvine_volume_number(comicvine_id, None),
                    expected
                )

    def test_unknown_volume_without_deck_defaults_to_one(self):
        self.assertEqual(_get_comicvine_volume_number(999999999, None), 1)

    def test_deck_volume_is_used_without_an_override(self):
        self.assertEqual(
            _get_comicvine_volume_number(
                999999999,
                'Volume 6 of the ongoing series'
            ),
            6
        )


if __name__ == '__main__':
    unittest.main()
