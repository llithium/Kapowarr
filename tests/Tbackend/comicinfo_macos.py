import unittest
from os.path import join
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import call, patch

from backend.base.definitions import OSType
from backend.implementations.comicinfo import read_comicinfo


class MacOSComicInfoReader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_uses_native_bsdtar_for_cbr_on_macos(self):
        filepath = join(
            self.temp_dir.name,
            'Batman - Knightfall - 25th Anniversary Edition (2018) '
            'Volume 001.cbr'
        )
        xml = b'''<?xml version="1.0" encoding="utf-8"?>
<ComicInfo>
    <Title>Volume 1</Title>
    <Series>Batman: Knightfall: 25th Anniversary Edition</Series>
    <Web>https://comicvine.gamespot.com/batman-knightfall-25th-anniversary-edition-1-volum/4000-684877/</Web>
    <Publisher>DC Comics</Publisher>
    <Number>1</Number>
    <Count>2</Count>
    <Day>12</Day>
    <Month>9</Month>
    <Year>2018</Year>
</ComicInfo>'''

        with patch(
            'backend.implementations.comicinfo.get_os_type',
            return_value=OSType.MACOS
        ), patch(
            'backend.implementations.comicinfo.subprocess_run',
            side_effect=(
                SimpleNamespace(
                    returncode=0,
                    stdout='Pages/001.jpg\nComicInfo.xml\n'
                ),
                SimpleNamespace(returncode=0, stdout=xml)
            )
        ) as mocked_bsdtar, patch(
            'backend.implementations.comicinfo.run_rar'
        ) as mocked_rar:
            self.assertEqual(
                read_comicinfo(filepath),
                {
                    'series': 'Batman: Knightfall: 25th Anniversary Edition',
                    'title': 'Volume 1',
                    'issue_number': '1',
                    'issue_count': 2,
                    'year': 2018,
                    'month': 9,
                    'day': 12,
                    'publisher': 'DC Comics',
                    'web': 'https://comicvine.gamespot.com/batman-knightfall-25th-anniversary-edition-1-volum/4000-684877/',
                    'comicvine_issue_id': 684877
                }
            )

        self.assertEqual(
            mocked_bsdtar.call_args_list,
            [
                call(
                    ['/usr/bin/bsdtar', '-tf', filepath],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                ),
                call(
                    ['/usr/bin/bsdtar', '-xOf', filepath, 'ComicInfo.xml'],
                    capture_output=True
                )
            ]
        )
        mocked_rar.assert_not_called()

    def test_falls_back_when_bsdtar_cannot_read_archive(self):
        filepath = join(self.temp_dir.name, 'fallback.cbr')
        xml = '<ComicInfo><Series>Fallback</Series><Number>3</Number></ComicInfo>'

        with patch(
            'backend.implementations.comicinfo.get_os_type',
            return_value=OSType.MACOS
        ), patch(
            'backend.implementations.comicinfo.subprocess_run',
            return_value=SimpleNamespace(returncode=1, stdout='')
        ), patch(
            'backend.implementations.comicinfo.run_rar',
            side_effect=(
                SimpleNamespace(returncode=0, stdout='ComicInfo.xml\n'),
                SimpleNamespace(returncode=0, stdout=xml)
            )
        ):
            self.assertEqual(
                read_comicinfo(filepath),
                {'series': 'Fallback', 'issue_number': '3'}
            )
