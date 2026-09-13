import tempfile
import unittest
from pathlib import Path
from unicodedata import normalize

from backend.base.definitions import FileConstants
from backend.base.files import (folder_is_inside_folder,
                                list_files, move_folder_contents)


class HiddenSidecarFiltering(unittest.TestCase):
    def test_volume_folder_move_includes_hidden_sidecars(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'Volume 01 (1990)'
            sidecar = source / '.Panels' / 'thumbnails' / 'Comic.cbz.jpg'
            sidecar.parent.mkdir(parents=True)
            sidecar.write_bytes(b'thumbnail')
            destination = root / 'Volume 03 (1990)'
            destination.mkdir()

            move_folder_contents(str(source), str(destination))

            self.assertFalse(source.exists())
            self.assertEqual(
                (destination / '.Panels' / 'thumbnails' / 'Comic.cbz.jpg')
                .read_bytes(),
                b'thumbnail'
            )

    def test_volume_folder_move_does_not_overwrite_sidecars(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'old' / '.Panels'
            destination = root / 'new' / '.Panels'
            source.mkdir(parents=True)
            destination.mkdir(parents=True)
            (source / 'metadata').write_bytes(b'old')
            (destination / 'metadata').write_bytes(b'new')

            move_folder_contents(str(root / 'old'), str(root / 'new'))

            self.assertEqual((source / 'metadata').read_bytes(), b'old')
            self.assertEqual((destination / 'metadata').read_bytes(), b'new')

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
