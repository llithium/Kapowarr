import errno
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from backend.base import files
from backend.implementations import converters, naming


class FilePreservation(unittest.TestCase):
    def test_cross_device_copy_failure_preserves_source(self):
        with TemporaryDirectory() as directory:
            source, target = Path(directory, 'source'), Path(directory, 'target')
            source.write_bytes(b'original')
            with patch('shutil.os.rename', side_effect=OSError(errno.EXDEV, 'cross-device')), \
                    patch.object(files, 'copyfile', side_effect=PermissionError(errno.EPERM, 'failed')):
                with self.assertRaises(PermissionError):
                    files.rename_file(str(source), str(target))
            self.assertEqual(source.read_bytes(), b'original')
            self.assertFalse(target.exists())

    def test_metadata_failure_after_copy_still_moves(self):
        with TemporaryDirectory() as directory:
            source, target = Path(directory, 'source'), Path(directory, 'target')
            source.write_bytes(b'original')
            with patch('shutil.os.rename', side_effect=OSError(errno.EXDEV, 'cross-device')), \
                    patch.object(files, 'copystat', side_effect=PermissionError(errno.EPERM, 'metadata')):
                files.rename_file(str(source), str(target))
            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), b'original')

    def test_rar_failure_and_empty_output_preserve_archive(self):
        for code, partial in ((2, True), (0, False)):
            with self.subTest(code=code), TemporaryDirectory() as directory:
                source = Path(directory, 'source.cbr')
                source.write_bytes(b'original')
                staging = Path(directory, 'staging')
                staging.mkdir()
                (staging / 'existing.cbz').write_bytes(b'keep')

                def extract(args):
                    if partial:
                        (Path(args[-1]) / 'partial.cbz').write_bytes(b'partial')
                    return SimpleNamespace(returncode=code)
                with patch.object(converters.FilesDB, 'volume_of_file', return_value=1), \
                        patch.object(converters, 'Volume', return_value=SimpleNamespace(vd=SimpleNamespace(folder=directory))), \
                        patch.object(converters, 'generate_archive_folder', return_value=str(staging)), \
                        patch.object(converters, 'run_rar', side_effect=extract):
                    self.assertEqual(converters.rar_to_folder(str(source)), [str(source)])
                self.assertEqual(source.read_bytes(), b'original')
                self.assertEqual((staging / 'existing.cbz').read_bytes(), b'keep')

    def test_extracted_file_cannot_overwrite_source_or_existing_file(self):
        for name in ('source.zip', 'existing.zip'):
            with self.subTest(name=name), TemporaryDirectory() as directory:
                source = Path(directory, 'source.zip')
                existing = Path(directory, 'existing.zip')
                existing.write_bytes(b'keep existing')
                with ZipFile(source, 'w') as archive:
                    archive.writestr(name, b'nested data')
                original = source.read_bytes()
                data = SimpleNamespace(folder=directory, year=2020)
                volume = SimpleNamespace(vd=data, get_data=lambda: data,
                                         get_issues=lambda: [], get_ending_year=lambda: None)
                with patch.object(converters.FilesDB, 'volume_of_file', return_value=1), \
                        patch.object(converters, 'Volume', return_value=volume), \
                        patch.object(converters, 'folder_extraction_filter', return_value=True), \
                        patch.object(converters, 'set_detected_extension', side_effect=lambda path: path):
                    self.assertEqual(converters.zip_to_folder(str(source)), [str(source)])
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(existing.read_bytes(), b'keep existing')

    def test_empty_rename_keeps_archive_and_stable_parser_path(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, 'Batman.zip')
            with ZipFile(source, 'w') as archive:
                archive.writestr('pages/001.jpg', b'image')
            data = SimpleNamespace(folder=directory, year=2020)
            volume = SimpleNamespace(vd=data, get_data=lambda: data,
                                     get_issues=lambda: [], get_ending_year=lambda: None)
            with patch.object(converters.FilesDB, 'volume_of_file', return_value=1), \
                    patch.object(converters, 'Volume', return_value=volume), \
                    patch.object(converters, 'extract_filename_data', return_value={}) as parser, \
                    patch.object(converters, 'folder_extraction_filter', return_value=True), \
                    patch.object(converters, 'set_detected_extension', side_effect=lambda path: path), \
                    patch.object(converters, 'scan_files'), \
                    patch.object(converters, 'mass_rename', return_value=[]) as rename:
                self.assertEqual(converters.zip_to_folder(str(source)), [str(source)])
            self.assertTrue(source.exists())
            self.assertEqual(parser.call_args.args[0], str(Path(directory, 'Batman/pages/001.jpg')))
            self.assertFalse(rename.call_args.kwargs['rename_volume_folder'])

    def test_conversion_rename_does_not_relocate_empty_volume(self):
        data = SimpleNamespace(folder='/old', custom_folder=False, root_folder=1)
        volume = SimpleNamespace(get_data=lambda: data, get_all_files=lambda: [])
        with patch.object(naming, 'Volume', return_value=volume), \
                patch.object(naming, 'RootFolders', return_value={1: '/root'}), \
                patch.object(naming, 'generate_volume_folder_path', return_value='/new'):
            self.assertEqual(naming.preview_mass_rename(1, rename_volume_folder=False), ({}, None))
            self.assertEqual(naming.preview_mass_rename(1), ({}, '/new'))

    def test_zip_with_no_scannable_files_preserves_archive(self):
        with TemporaryDirectory() as directory:
            source = Path(directory, 'source.zip')
            with ZipFile(source, 'w') as archive:
                archive.writestr('readme.txt', 'nothing to convert')
            staging = Path(directory, 'staging')
            with patch.object(converters.FilesDB, 'volume_of_file', return_value=1), \
                    patch.object(converters, 'Volume', return_value=SimpleNamespace(vd=SimpleNamespace(folder=directory))), \
                    patch.object(converters, 'generate_archive_folder', return_value=str(staging)), \
                    patch.object(converters, 'extract_files_from_folder', return_value=[]):
                self.assertEqual(converters.zip_to_folder(str(source)), [str(source)])
            self.assertTrue(source.exists())
