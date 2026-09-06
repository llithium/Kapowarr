# -*- coding: utf-8 -*-

"""Read ComicInfo.xml metadata embedded in ZIP/CBZ comic archives."""

from os.path import basename, splitext
from typing import Dict, List, TypedDict, Union
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from backend.base.logging import LOGGER


class ComicInfoData(TypedDict, total=False):
    """Useful ComicInfo.xml fields for identifying a comic during import."""

    series: str
    title: str
    issue_number: str
    volume: int
    issue_count: int
    year: int
    month: int
    day: int
    publisher: str
    format: str
    web: str
    gtin: str
    alternate_series: str


_FIELD_MAP = {
    'series': 'series',
    'title': 'title',
    'number': 'issue_number',
    'publisher': 'publisher',
    'format': 'format',
    'web': 'web',
    'gtin': 'gtin',
    'alternateseries': 'alternate_series'
}

_INT_FIELD_MAP = {
    'volume': 'volume',
    'count': 'issue_count',
    'year': 'year',
    'month': 'month',
    'day': 'day'
}

_ZIP_COMIC_EXTENSIONS = {'.cbz', '.zip'}


def _local_name(tag: str) -> str:
    """Return an XML tag without its optional namespace prefix."""
    return tag.rsplit('}', 1)[-1].lower()


def _normalise_text(value: Union[str, None]) -> Union[str, None]:
    if value is None:
        return None

    value = value.strip()
    return value or None


def _to_int(value: Union[str, None]) -> Union[int, None]:
    value = _normalise_text(value)
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _find_comicinfo_files(filenames: List[str]) -> List[str]:
    """Find ComicInfo.xml entries, preferring files closest to archive root."""
    matches = [
        filename
        for filename in filenames
        if basename(filename).lower() == 'comicinfo.xml'
    ]
    matches.sort(key=lambda f: (f.count('/'), len(f), f.lower()))
    return matches


def _parse_comicinfo(xml_data: bytes) -> Union[ComicInfoData, None]:
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError:
        return None

    values: Dict[str, str] = {}
    for child in root.iter():
        name = _local_name(child.tag)
        if name in values:
            continue

        value = _normalise_text(child.text)
        if value is not None:
            values[name] = value

    result: ComicInfoData = {}

    for xml_name, result_name in _FIELD_MAP.items():
        value = values.get(xml_name)
        if value is not None:
            result[result_name] = value  # type: ignore[literal-required]

    for xml_name, result_name in _INT_FIELD_MAP.items():
        value = _to_int(values.get(xml_name))
        if value is not None:
            result[result_name] = value  # type: ignore[literal-required]

    return result or None


def read_comicinfo(filepath: str) -> Union[ComicInfoData, None]:
    """Read embedded ComicInfo.xml metadata from a ZIP-compatible comic.

    The reader is intentionally non-destructive. It only supports CBZ/ZIP in
    this first implementation; unsupported archives, missing metadata and
    malformed metadata all return ``None`` so callers can fall back to filename
    parsing.

    Args:
        filepath (str): Path to a comic archive.

    Returns:
        Union[ComicInfoData, None]: Parsed metadata, or ``None`` when no usable
            ComicInfo.xml can be read.
    """
    if splitext(filepath)[1].lower() not in _ZIP_COMIC_EXTENSIONS:
        return None

    try:
        with ZipFile(filepath, 'r') as archive:
            comicinfo_files = _find_comicinfo_files(archive.namelist())
            if not comicinfo_files:
                return None

            # If an archive contains multiple metadata files, use the one
            # closest to the archive root. This is the least surprising choice
            # for normal CBZ files while still supporting nested metadata.
            xml_data = archive.read(comicinfo_files[0])

    except (BadZipFile, KeyError, OSError):
        LOGGER.debug('Unable to read ComicInfo.xml from %s', filepath)
        return None

    return _parse_comicinfo(xml_data)
