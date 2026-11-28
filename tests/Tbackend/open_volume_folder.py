import unittest
from os import makedirs
from os.path import join
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from flask import Flask

from backend.base.custom_exceptions import FolderNotFound, FolderNotOpenable
from backend.base.definitions import OSType
from backend.base.files import open_folder_in_file_manager
from frontend.api import api


class OpenFolderInFileManager(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.folder = join(self.tmp.name, 'Dynamite', 'Evil Ernie', 'Volume 01 (2014)')
        makedirs(self.folder)

    def tearDown(self):
        self.tmp.cleanup()

    def _open(self, os_type, process=None, popen_error=None):
        popen = Mock(return_value=process, side_effect=popen_error)
        with patch('backend.base.files.get_os_type', return_value=os_type), \
                patch('backend.base.files.Popen', popen):
            open_folder_in_file_manager(self.folder)
        return popen

    def test_macos_uses_open(self):
        process = Mock()
        process.wait.return_value = 0
        popen = self._open(OSType.MACOS, process)
        self.assertEqual(popen.call_args.args[0], ['open', self.folder])

    def test_linux_uses_xdg_open(self):
        process = Mock()
        process.wait.return_value = 0
        popen = self._open(OSType.LINUX, process)
        self.assertEqual(popen.call_args.args[0], ['xdg-open', self.folder])

    def test_missing_folder(self):
        with patch('backend.base.files.Popen') as popen:
            with self.assertRaises(FolderNotFound):
                open_folder_in_file_manager(join(self.tmp.name, 'gone'))
        popen.assert_not_called()

    def test_no_opener_installed(self):
        with self.assertRaises(FolderNotOpenable):
            self._open(OSType.LINUX, popen_error=FileNotFoundError('xdg-open'))

    def test_opener_fails(self):
        process = Mock()
        process.wait.return_value = 3
        with self.assertRaises(FolderNotOpenable):
            self._open(OSType.LINUX, process)

    def test_opener_that_keeps_running_counts_as_success(self):
        process = Mock()
        process.wait.side_effect = [TimeoutExpired('xdg-open', 5), 0]
        self._open(OSType.LINUX, process)


class OpenFolderRoute(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(api, url_prefix='/api')
        self.client = app.test_client()

    def test_opens_the_stored_folder_of_the_volume(self):
        volume = Mock()
        volume.get_data.return_value.folder = '/Comics/Dynamite/Evil Ernie/Volume 01 (2014)'
        with patch('frontend.api.extract_key'), \
                patch('frontend.api.Library.get_volume', return_value=volume) as get_volume, \
                patch('frontend.api.open_folder_in_file_manager') as opener:
            response = self.client.post('/api/volumes/7/openfolder', json={'folder': '/etc'})
        self.assertEqual(response.status_code, 200)
        get_volume.assert_called_once_with(7)
        opener.assert_called_once_with('/Comics/Dynamite/Evil Ernie/Volume 01 (2014)')

    def test_missing_folder_is_404(self):
        volume = Mock()
        volume.get_data.return_value.folder = '/Comics/gone'
        with patch('frontend.api.extract_key'), \
                patch('frontend.api.Library.get_volume', return_value=volume), \
                patch('frontend.api.open_folder_in_file_manager',
                      side_effect=FolderNotFound('/Comics/gone')):
            response = self.client.post('/api/volumes/7/openfolder')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error'], 'FolderNotFound')


if __name__ == '__main__':
    unittest.main()
