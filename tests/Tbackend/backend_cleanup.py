import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import backend.base.files as files_module
from backend.base.custom_exceptions import ExternalClientNotFound
from backend.base.definitions import DownloadType, FileDate, OSType
from backend.base.files import set_file_date
from backend.implementations.external_clients import ExternalClients
from backend.implementations.file_processing import mass_set_file_date


class BackendCleanup(unittest.TestCase):
    def test_file_date_sets_access_and_modification_times_on_unix(self):
        for os_type in (OSType.LINUX, OSType.MACOS):
            with self.subTest(os_type=os_type), patch(
                'backend.base.files.get_os_type', return_value=os_type
            ), patch('backend.base.files.utime') as set_times, patch(
                'backend.base.files.__set_macos_times'
            ) as set_creation:
                set_file_date('/tmp/example.cbz', '2024-01-02')

                set_times.assert_called_once()
                self.assertEqual(
                    set_times.call_args.args[0],
                    '/tmp/example.cbz')
                accessed, modified = set_times.call_args.kwargs['times']
                self.assertEqual(accessed, modified)
                if os_type == OSType.MACOS:
                    set_creation.assert_called_once_with(
                        '/tmp/example.cbz', modified)
                else:
                    set_creation.assert_not_called()

    def test_windows_timestamp_closes_handle_on_set_failure(self):
        create_file = Mock(return_value=123)
        set_file_time = Mock(return_value=0)
        close_handle = Mock(return_value=1)
        kernel32 = SimpleNamespace(
            CreateFileW=create_file,
            SetFileTime=set_file_time,
            CloseHandle=close_handle
        )

        with patch(
            'backend.base.files.ctypes.WinDLL',
            return_value=kernel32,
            create=True
        ):
            getattr(files_module, '__set_windows_times')('/tmp/example.cbz', 0)

        set_file_time.assert_called_once()
        close_handle.assert_called_once_with(123)

    def test_file_date_filter_binds_paths(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.executescript('''
            CREATE TABLE files (id INTEGER PRIMARY KEY, filepath TEXT, size INT);
            CREATE TABLE issues (id INTEGER PRIMARY KEY, volume_id INT, date TEXT);
            CREATE TABLE issues_files (issue_id INT, file_id INT);
            INSERT INTO files VALUES
                (1, "safe.cbz", 1),
                (2, "other.cbz", 1),
                (3, "odd' name.cbz", 1);
            INSERT INTO issues VALUES (1, 7, "2024-01-01");
            INSERT INTO issues_files VALUES (1, 1), (1, 2), (1, 3);
        ''')
        selected = []
        settings = SimpleNamespace(
            sv=SimpleNamespace(change_file_date=FileDate.ISSUE_RELEASE_DATE)
        )
        cursor_connection = connection.cursor()

        with patch(
            'backend.implementations.file_processing.get_db',
            return_value=cursor_connection
        ), patch(
            'backend.implementations.file_processing.Settings',
            return_value=settings
        ), patch(
            'backend.implementations.file_processing.set_file_date',
            side_effect=lambda filepath, _date: selected.append(filepath)
        ):
            mass_set_file_date(7, filepath_filter=["odd' name.cbz"])

        self.assertEqual(selected, ["odd' name.cbz"])

    def test_least_used_client_includes_clients_with_empty_queue(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.executescript('''
            CREATE TABLE external_download_clients (
                id INTEGER PRIMARY KEY, download_type INT
            );
            CREATE TABLE download_queue (id INTEGER PRIMARY KEY,
                external_client_id INT);
            INSERT INTO external_download_clients VALUES (1, 2), (2, 2);
            INSERT INTO download_queue VALUES (10, 1);
        ''')

        with patch(
            'backend.implementations.external_clients.get_db',
            return_value=connection
        ), patch.object(
            ExternalClients, 'get_client', side_effect=lambda client_id: client_id
        ):
            result = ExternalClients.get_least_used_client(DownloadType.TORRENT)
            self.assertEqual(result, 2)
            connection.execute('DELETE FROM external_download_clients')
            with self.assertRaises(ExternalClientNotFound):
                ExternalClients.get_least_used_client(DownloadType.TORRENT)


if __name__ == '__main__':
    unittest.main()
