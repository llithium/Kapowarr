import unittest

from backend.features.library_import import (_is_managed_volume_file,
                                             _is_panels_path)


class LibraryImportPathFiltering(unittest.TestCase):
    def test_file_inside_managed_volume_folder_is_skipped(self):
        managed = {
            '/comics/DC Comics/The Question/Volume 01 (1986)'
        }
        filepath = (
            '/comics/DC Comics/The Question/Volume 01 (1986)/'
            'The Question (1986) Volume 01 Issue 001.cbz'
        )

        self.assertTrue(_is_managed_volume_file(filepath, managed))

    def test_sibling_folder_is_not_treated_as_managed(self):
        managed = {
            '/comics/DC Comics/The Question/Volume 01 (1986)'
        }
        filepath = (
            '/comics/DC Comics/The Question Annual/Volume 01 (1987)/'
            'The Question Annual (1987) Volume 01 Issue 001.cbz'
        )

        self.assertFalse(_is_managed_volume_file(filepath, managed))

    def test_panels_bundle_contents_are_ignored(self):
        filepath = (
            '/comics/Coffin Comics/Lady Death Malevolent Decimation/'
            'Lady Death Malevolent Decimation (2024) Volume 01 HC.panels/'
            'cover.jpg'
        )

        self.assertTrue(_is_panels_path(filepath))

    def test_panels_check_is_case_insensitive(self):
        filepath = '/comics/Example/Example.PANELS/page-001.webp'

        self.assertTrue(_is_panels_path(filepath))

    def test_normal_comic_archive_is_not_a_panels_path(self):
        filepath = '/comics/Example/Example (2024) Volume 01 HC.cbz'

        self.assertFalse(_is_panels_path(filepath))


if __name__ == '__main__':
    unittest.main()
