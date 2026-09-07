import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.post_processing import (copy_file_torrent,
                                              move_torrent_to_dest,
                                              reset_file_link)


class TorrentProcessing(unittest.TestCase):
    def test_transfers_scan_and_rename_but_copy_retains_seeding_source(self):
        for transfer in (copy_file_torrent, move_torrent_to_dest):
            with self.subTest(transfer=transfer.__name__):
                download = SimpleNamespace(
                    files=['/downloads/archive'], volume_id=1,
                    filename_body='archive'
                )
                with patch('backend.features.post_processing.exists',
                           side_effect=lambda path: path == '/downloads/archive'), patch(
                    'backend.features.post_processing.Volume',
                    return_value=SimpleNamespace(vd=SimpleNamespace(folder='/library'))
                ), patch('backend.features.post_processing.commit'), patch(
                    'backend.features.post_processing.copy_directory'
                ) as copy, patch(
                    'backend.features.post_processing.rename_file'
                ) as move, patch(
                    'backend.features.post_processing.extract_files_from_folder',
                    return_value=['/library/issue.cbz']
                ), patch('backend.features.post_processing.scan_files') as scan, patch(
                    'backend.features.post_processing.Settings',
                    return_value=SimpleNamespace(sv=SimpleNamespace(rename_downloaded_files=True))
                ), patch('backend.features.post_processing.mass_rename',
                         return_value=['/library/renamed.cbz']):
                    transfer(download)
                    scan.assert_called_once_with(
                        1, filepath_filter=['/library/issue.cbz'],
                        update_websocket=True)
                    self.assertEqual(download.files, ['/library/renamed.cbz'])
                    if transfer is copy_file_torrent:
                        copy.assert_called_once_with(
                            '/downloads/archive', '/library/archive')
                        move.assert_not_called()
                        reset_file_link(download)
                        self.assertEqual(download.files, ['/downloads/archive'])
                    else:
                        move.assert_called_once_with(
                            '/downloads/archive', '/library/archive')
                        copy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
