import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.base.definitions import OSType
from backend.base.helpers import run_rar


class MacOSArchives(unittest.TestCase):
    def test_extraction_uses_bundled_unrar_without_a_system_installation(self):
        with TemporaryDirectory() as folder:
            unrar = Path(folder, 'unrar')
            unrar.touch()
            with patch('backend.base.helpers.get_os_type', return_value=OSType.MACOS), \
                    patch('backend.base.files.folder_path', return_value=str(unrar)), \
                    patch('backend.base.helpers.which', return_value=None), \
                    patch('backend.base.helpers.run') as run:
                run_rar(['x', 'comic.cbr', folder])
                run.assert_called_once_with(
                    [str(unrar), 'x', 'comic.cbr', folder], capture_output=True, text=True)

    def test_compression_requires_rar_and_never_attempts_unrar(self):
        with patch('backend.base.helpers.get_os_type', return_value=OSType.MACOS), \
                patch('backend.base.helpers.which', return_value=None), \
                patch('backend.base.helpers.run') as run:
            result = run_rar(['a', 'comic.rar', 'pages'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('separate RAR installation', result.stderr)
            run.assert_not_called()
