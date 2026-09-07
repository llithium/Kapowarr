import unittest
from os.path import join
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import call, patch
from zipfile import ZipFile

from backend.implementations.comicinfo import (comicinfo_to_filename_data,
                                               read_comicinfo)


class ComicInfoReader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_cbz(
        self,
        filename: str,
        xml: str,
        xml_path: str = 'ComicInfo.xml'
    ):
        filepath = join(self.temp_dir.name, filename)
        with ZipFile(filepath, 'w') as archive:
            archive.writestr(xml_path, xml)
            archive.writestr('001.jpg', b'not-a-real-image')
        return filepath

    def test_reads_comictagger_style_metadata(self):
        filepath = self._make_cbz(
            'Batman (2022) Issue 085.cbz',
            '''<?xml version="1.0" encoding="utf-8"?>
<ComicInfo>
    <Title>Failsafe, Part One</Title>
    <Series>Batman</Series>
    <Number>125</Number>
    <Count>141</Count>
    <Volume>3</Volume>
    <Year>2022</Year>
    <Month>9</Month>
    <Day>6</Day>
    <Publisher>DC Comics</Publisher>
    <Format>Comic</Format>
    <Web>https://comicvine.gamespot.com/batman-125/4000-934000/</Web>
    <GTIN>76194134182812511</GTIN>
    <AlternateSeries>Batman (2016)</AlternateSeries>
</ComicInfo>'''
        )

        self.assertEqual(
            read_comicinfo(filepath),
            {
                'series': 'Batman',
                'title': 'Failsafe, Part One',
                'issue_number': '125',
                'volume': 3,
                'issue_count': 141,
                'year': 2022,
                'month': 9,
                'day': 6,
                'publisher': 'DC Comics',
                'format': 'Comic',
                'web': 'https://comicvine.gamespot.com/batman-125/4000-934000/',
                'gtin': '76194134182812511',
                'alternate_series': 'Batman (2016)',
                'comicvine_issue_id': 934000
            }
        )

    def test_extracts_comicvine_volume_id_from_web(self):
        filepath = self._make_cbz(
            'Batman Volume.cbz',
            '''<ComicInfo>
    <Series>Batman</Series>
    <Web>https://comicvine.gamespot.com/batman/4050-796/</Web>
</ComicInfo>'''
        )

        self.assertEqual(
            read_comicinfo(filepath),
            {
                'series': 'Batman',
                'web': 'https://comicvine.gamespot.com/batman/4050-796/',
                'comicvine_volume_id': 796
            }
        )

    def test_reads_explicit_comicvine_extension_ids(self):
        filepath = self._make_cbz(
            'explicit-ids.cbz',
            '''<ComicInfo>
    <Series>Batman</Series>
    <ComicVineIssueId>934000</ComicVineIssueId>
    <ComicVineVolumeId>796</ComicVineVolumeId>
</ComicInfo>'''
        )

        self.assertEqual(
            read_comicinfo(filepath),
            {
                'series': 'Batman',
                'comicvine_issue_id': 934000,
                'comicvine_volume_id': 796
            }
        )

    def test_issue_number_is_preserved_for_special_version(self):
        filepath = self._make_cbz(
            'Batman - The Killing Joke (1988) Issue 001.cbz',
            '''<ComicInfo>
    <Series>Batman: The Killing Joke</Series>
    <Number>1</Number>
    <Year>1988</Year>
    <Publisher>DC Comics</Publisher>
    <Format>One-Shot</Format>
</ComicInfo>'''
        )

        metadata = read_comicinfo(filepath)
        self.assertEqual(
            metadata,
            {
                'series': 'Batman: The Killing Joke',
                'issue_number': '1',
                'year': 1988,
                'publisher': 'DC Comics',
                'format': 'One-Shot'
            }
        )

        fallback = {
            'series': 'Wrong Filename Title',
            'year': 1988,
            'volume_number': 1,
            'special_version': None,
            'issue_number': 1.0,
            'annual': False
        }
        self.assertEqual(
            comicinfo_to_filename_data(metadata or {}, fallback),
            {
                'series': 'Batman: The Killing Joke',
                'year': 1988,
                'volume_number': 1,
                'special_version': 'one-shot',
                'issue_number': 1.0,
                'annual': False
            }
        )

    def test_library_import_does_not_treat_issue_year_as_series_year(self):
        metadata = {
            'series': 'Batman',
            'issue_number': '85',
            'year': 2021,
            'format': 'Comic'
        }
        fallback = {
            'series': 'Batman',
            'year': 2020,
            'volume_number': 1,
            'special_version': None,
            'issue_number': 85.0,
            'annual': False
        }

        self.assertEqual(
            comicinfo_to_filename_data(
                metadata,
                fallback,
                for_library_import=True
            ),
            {
                'series': 'Batman',
                'year': 2020,
                'volume_number': None,
                'special_version': None,
                'issue_number': 85.0,
                'annual': False
            }
        )

    def test_finds_nested_case_insensitive_metadata_filename(self):
        filepath = self._make_cbz(
            'nested.cbz',
            '<ComicInfo><Series>Example</Series><Number>7</Number></ComicInfo>',
            'metadata/COMICINFO.XML'
        )

        self.assertEqual(
            read_comicinfo(filepath),
            {'series': 'Example', 'issue_number': '7'}
        )

    def test_supports_xml_namespaces(self):
        filepath = self._make_cbz(
            'namespaced.cbz',
            '''<ComicInfo xmlns="urn:comicinfo">
    <Series>Namespace Test</Series>
    <Number>3</Number>
    <Year>2024</Year>
</ComicInfo>'''
        )

        self.assertEqual(
            read_comicinfo(filepath),
            {'series': 'Namespace Test', 'issue_number': '3', 'year': 2024}
        )

    def test_returns_none_for_missing_or_malformed_metadata(self):
        no_metadata = join(self.temp_dir.name, 'no-metadata.cbz')
        with ZipFile(no_metadata, 'w') as archive:
            archive.writestr('001.jpg', b'not-a-real-image')

        malformed = self._make_cbz(
            'malformed.cbz',
            '<ComicInfo><Series>Broken</ComicInfo>'
        )

        self.assertIsNone(read_comicinfo(no_metadata))
        self.assertIsNone(read_comicinfo(malformed))

    def test_reads_comicinfo_from_cbr(self):
        filepath = join(self.temp_dir.name, 'Hellwitch Issue 001.cbr')
        xml = '''<ComicInfo>
    <Series>Hellwitch vs Lady Death: Wargasm</Series>
    <Number>1</Number>
    <Year>2022</Year>
    <Publisher>Coffin Comics</Publisher>
    <Format>TPB</Format>
</ComicInfo>'''

        with patch(
            'backend.implementations.comicinfo.run_rar',
            side_effect=(
                SimpleNamespace(
                    returncode=0,
                    stdout='Pages\\001.jpg\nMetadata\\COMICINFO.XML\n'
                ),
                SimpleNamespace(returncode=0, stdout=xml)
            )
        ) as mocked_rar:
            self.assertEqual(
                read_comicinfo(filepath),
                {
                    'series': 'Hellwitch vs Lady Death: Wargasm',
                    'issue_number': '1',
                    'year': 2022,
                    'publisher': 'Coffin Comics',
                    'format': 'TPB'
                }
            )

        self.assertEqual(
            mocked_rar.call_args_list,
            [
                call(['lb', filepath]),
                call([
                    'p', '-inul', filepath,
                    'Metadata\\COMICINFO.XML'
                ])
            ]
        )

    def test_returns_none_when_rar_reader_fails(self):
        filepath = join(self.temp_dir.name, 'broken.cbr')

        with patch(
            'backend.implementations.comicinfo.run_rar',
            return_value=SimpleNamespace(returncode=2, stdout='')
        ):
            self.assertIsNone(read_comicinfo(filepath))

    def test_returns_none_for_unsupported_archive(self):
        filepath = join(self.temp_dir.name, 'example.pdf')
        self.assertIsNone(read_comicinfo(filepath))
