import tempfile
import unittest
from pathlib import Path
from unicodedata import normalize

from backend.base.definitions import FileConstants
from backend.base.files import folder_is_inside_folder, list_files


class HiddenSidecarFiltering(unittest.TestCase):
    def test_list_files_does_not_descend_hidden_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            visible = root / 'Comic.cbz'
            visible.write_bytes(b'comic')

            panels = root / '.Panels' / 'thumbnails'
            panels.mkdir(parents=True)
            (panels / 'Comic.cbz.jpg').write_bytes(b'thumbnail')

            archive_temp = root / '.archive_extract' / 'nested'
            archive_temp.mkdir(parents=True)
            (archive_temp / 'Temp.cbz').write_bytes(b'temp')

            files = list_files(
                str(root), FileConstants.SCANNABLE_EXTENSIONS
            )
            self.assertEqual(files, [str(visible)])

    def test_folder_comparison_normalises_macos_unicode(self):
        base = (
            '/comics/DC Comics/Wonder Woman By George Pérez/'
            'Volume 01 (2016)'
        )
        child = normalize('NFD', base) + '/Wonder Woman 001.cbz'
        self.assertTrue(folder_is_inside_folder(base, child))


if __name__ == '__main__':
    unittest.main()
