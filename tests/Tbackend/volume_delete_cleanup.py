import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.base.files import (delete_empty_parent_folders,
                                delete_leftover_clutter, is_leftover_clutter)
from backend.implementations import volumes


class LeftoverClutter(unittest.TestCase):
    def test_clutter_names(self):
        self.assertTrue(is_leftover_clutter('.Panels', True))
        self.assertTrue(is_leftover_clutter('.panels', True))
        self.assertTrue(is_leftover_clutter('Comic 001.panels', True))
        self.assertTrue(is_leftover_clutter('.DS_Store', False))
        self.assertTrue(is_leftover_clutter('._Comic 001.cbz', False))
        self.assertTrue(is_leftover_clutter('Thumbs.db', False))
        self.assertFalse(is_leftover_clutter('Comic 001.cbz', False))
        self.assertFalse(is_leftover_clutter('Extras', True))
        self.assertFalse(is_leftover_clutter('.DS_Store', True))

    def test_panels_folder_is_removed_once_comics_are_gone(self):
        with TemporaryDirectory() as temp:
            volume = Path(temp, 'Volume 01 (1990)')
            thumbs = volume / '.Panels' / 'thumbnails'
            thumbs.mkdir(parents=True)
            (thumbs / 'Comic 001.cbz.jpg').write_bytes(b'thumb')
            (volume / '.DS_Store').write_bytes(b'')

            delete_leftover_clutter(str(volume))

            self.assertEqual(list(volume.iterdir()), [])

    def test_sidecars_of_remaining_comics_are_kept(self):
        with TemporaryDirectory() as temp:
            volume = Path(temp, 'Volume 01 (1990)')
            (volume / '.Panels').mkdir(parents=True)
            (volume / '.Panels' / 'metadata').write_bytes(b'data')
            (volume / 'Unrelated.cbz').write_bytes(b'comic')

            delete_leftover_clutter(str(volume))

            self.assertTrue((volume / '.Panels' / 'metadata').exists())

    def test_parent_folders_holding_only_clutter_are_removed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp, 'comics')
            series = root / 'DC Comics' / 'The Question'
            volume = series / 'Volume 01 (1986)'
            volume.mkdir(parents=True)
            (series / '.DS_Store').write_bytes(b'')
            (series / '.Panels').mkdir()
            (root / 'DC Comics' / 'Other.cbz').write_bytes(b'comic')

            delete_empty_parent_folders(
                str(volume), str(root), ignore_clutter=True
            )

            self.assertFalse(series.exists())
            self.assertTrue((root / 'DC Comics' / 'Other.cbz').exists())

    def test_clutter_still_counts_as_content_by_default(self):
        with TemporaryDirectory() as temp:
            root = Path(temp, 'comics')
            series = root / 'Series'
            volume = series / 'Volume 01 (1986)'
            volume.mkdir(parents=True)
            (series / '.DS_Store').write_bytes(b'')

            delete_empty_parent_folders(str(volume), str(root))

            self.assertFalse(volume.exists())
            self.assertTrue((series / '.DS_Store').exists())


class VolumeDeleteWithFolder(unittest.TestCase):
    def test_deleting_volume_removes_panels_folder_and_volume_folder(self):
        with TemporaryDirectory() as temp:
            root = Path(temp, 'comics')
            series = root / 'Coffin Comics' / 'Lady Death'
            volume_folder = series / 'Volume 01 (2024)'
            thumbs = volume_folder / '.Panels' / 'thumbnails'
            thumbs.mkdir(parents=True)
            comic = volume_folder / 'Lady Death (2024) Volume 01 HC.cbz'
            comic.write_bytes(b'comic')
            (thumbs / 'cover.jpg').write_bytes(b'thumb')
            (root / 'Other.cbz').write_bytes(b'comic')

            volume = volumes.Volume.__new__(volumes.Volume)
            volume.id = 1
            volume.get_data = lambda: SimpleNamespace(
                folder=str(volume_folder), root_folder=1
            )
            volume.get_all_files = lambda: [{"filepath": str(comic)}]

            with patch(
                'backend.features.tasks.TaskHandler.task_for_volume_running',
                return_value=False
            ), patch(
                'backend.features.download_queue.DownloadHandler'
            ) as handler, patch.object(
                volumes, 'RootFolders',
                return_value={1: str(root)}
            ), patch.object(volumes, 'FilesDB'), patch.object(
                volumes, 'get_db', return_value=MagicMock()
            ):
                handler.return_value.download_for_volume_queued.return_value = False
                volume.delete(delete_folder=True)

            self.assertFalse(volume_folder.exists())
            self.assertFalse((root / 'Coffin Comics').exists())
            self.assertTrue((root / 'Other.cbz').exists())


if __name__ == '__main__':
    unittest.main()
