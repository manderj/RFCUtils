import functools
import itertools
import pathlib
import urllib.request
from urllib.parse import urljoin
import os

import click
from lxml import etree
import requests


SITE_URL = 'https://www.ietf.org/rfc/'

DEFAULT_DOWNLOAD_FOLDER = './rfc'

XML_TAG = '{http://www.rfc-editor.org/rfc-index}'
RFC_ENTRY_TAG = f'{XML_TAG}rfc-entry'
RFC_DOC_ID_TAG = f'{XML_TAG}doc-id'
RFC_FORMAT_TAG = f'{XML_TAG}format'
RFC_CURRENT_STATUS_TAG = f'{XML_TAG}current-status'

RFC_STATUSES = (
    'UNKNOWN',
    'EXPERIMENTAL',
    'INFORMATIONAL',
    'BEST CURRENT PRACTICE',
    'PROPOSED STANDARD',
)

TXT = 'TXT'
HTML= 'HTML'
PDF = 'PDF'
XML = 'XML'
FILETYPE_TO_FORMAT_MAPPING = {
    TXT: 'TEXT',
    HTML: 'HTML',
    PDF: 'PDF',
    XML: 'XML',
}
RFC_FILETYPES = FILETYPE_TO_FORMAT_MAPPING.keys()


@functools.lru_cache(1)
def update_rfc_index():
    rfc_index_request = urllib.request.urlopen(urljoin(SITE_URL, 'rfc-index.xml'))
    root = etree.parse(rfc_index_request)

    index = {}
    for entry in root.findall(RFC_ENTRY_TAG):
        rfc_number = entry.find(RFC_DOC_ID_TAG).text.split('RFC')[1]
        index.update({
            rfc_number: {
                'url': lambda filetype: urljoin(SITE_URL, f'rfc{rfc_number}.{filetype}'),
                'formats': [child.text for child in entry.find(RFC_FORMAT_TAG).getchildren()],
                'current-status': entry.find(RFC_CURRENT_STATUS_TAG).text,
            }
        })
    return index


def _get_rfc_index_subset(rfc_index, predicate):
    return {rfc_number: rfc_values for rfc_number, rfc_values in rfc_index.items() if predicate(rfc_number, rfc_values)}


@click.command()
@click.option('--rfc_numbers', default=['all'], multiple=True, help="rfc_numbers list to get")
@click.option('--desc_contain', multiple=True, type=click.STRING, help="download rfc description containing the given words")
@click.option('--statuses', type=click.Choice(RFC_STATUSES), default=[], multiple=True)
@click.option('--filetypes', type=click.Choice(RFC_FILETYPES), default=[TXT, PDF, HTML], multiple=True, help="format to retrieved")
def download(rfc_numbers, desc_contain, statuses, filetypes):
    rfc_index = update_rfc_index()

    defined_dl_folder = os.getenv('RFCDOWNLOADER_FOLDER', DEFAULT_DOWNLOAD_FOLDER)
    download_folder = pathlib.Path(defined_dl_folder).expanduser()

    # narrow the rfc list to download
    rfc_subset = {}
    if 'all' in rfc_numbers:
        rfc_subset = _get_rfc_index_subset(rfc_index, lambda rfc_number, _rfc_values: rfc_number in rfc_index.keys())
    else:
        # fill missing leading zero
        rfc_numbers = [f'{rfc_number:0>4}' for rfc_number in rfc_numbers]
        rfc_subset = _get_rfc_index_subset(rfc_index, lambda rfc_number, _rfc_values: rfc_number in rfc_numbers)

    if desc_contain:
        rfc_subset = _get_rfc_index_subset(rfc_subset, lambda _rfc_number, rfc_values: any(
            word in rfc_values['title'] or word in rfc_values.get('abstract', '') for word in desc_contain
        ))

    if statuses:
        rfc_subset = _get_rfc_index_subset(rfc_subset, lambda _rfc_number, rfc_values: any(
             status in rfc_values['current-status'] for status in statuses
        ))

    # FIXME: sadly, rfc-index isn't perfect and a lot of missing formats for each RFC
    if filetypes:
        rfc_subset = _get_rfc_index_subset(rfc_subset, lambda _rfc_number, rfc_values: any(
            FILETYPE_TO_FORMAT_MAPPING[filetype] in rfc_values['formats'] for filetype in filetypes
        ))

    if not rfc_subset:
        print("No RFC found.")
        return

    if not download_folder.exists():
        download_folder.mkdir()

    for rfc_number, rfc_values in rfc_subset.items():
        for filetype in filetypes:
            path = (download_folder / f'rfc_{rfc_number}.{filetype.lower()}')
            if path.exists() and path.stat().st_size:
                break
            try:
                rfc_request = urllib.request.urlopen(rfc_values['url'](filetype.lower()))
            except urllib.error.HTTPError:
                # raised an Http404 error since the filetype doesn't exists for this file
                # but it's fine we have already checked that this file should be downloaded anyway
                continue
            path.write_text(rfc_request.read().decode('utf8'))
            break

if __name__ == '__main__':
    download()
