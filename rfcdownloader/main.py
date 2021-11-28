import functools
import itertools
import urllib.request
from urllib.parse import urljoin

import click
from lxml import etree
import requests

import settings

SITE_URL = 'https://www.ietf.org/rfc/'


XML_TAG = '{http://www.rfc-editor.org/rfc-index}'
RFC_ENTRY_TAG = f'{XML_TAG}rfc-entry'
RFC_DOC_ID_TAG = f'{XML_TAG}doc-id'
RFC_FORMAT_TAG = f'{XML_TAG}format'
RFC_CURRENT_STATUS_TAG = f'{XML_TAG}current-status'
RFC_ABSTRACT_TAG =f'{XML_TAG}abstract'

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
                'abstract': ' '.join(child.text for child in (
                    entry.find(RFC_ABSTRACT_TAG).getchildren() if entry.find(RFC_ABSTRACT_TAG) else []
                )),
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
@click.option('--download-again', default=False, is_flag=True, help="Download again the filtered rfc list")
def download(*args, **kwargs):
    rfc_index = update_rfc_index()

    # Narrow the RFC list to download
    rfc_subset = rfc_index
    if 'all' in kwargs['rfc_numbers']:
        kwargs['rfc_numbers'] = rfc_index.keys()
    else:
        # fill missing leading zero
        kwargs['rfc_numbers'] = [f'{rfc_number:0>4}' for rfc_number in kwargs['rfc_numbers']]

    predicate_by_filtering = {
        'rfc_numbers': lambda rfc_number, _rfc_values: rfc_number in kwargs['rfc_numbers'],
        'desc_contain': lambda _rfc_number, rfc_values: any(
            word in rfc_values['title'] or word in rfc_values['abstract'] for word in kwargs['desc_contain']
        ),
        'statuses': lambda _rfc_number, rfc_values: any(
             status in rfc_values['current-status'] for status in kwargs['statuses']
        ),
        # FIXME: sadly, rfc-index.xml isn't perfect and doesn't provide
        # an exaustive list of available formats for each RFC
        'filetypes': lambda _rfc_number, rfc_values: any(
            FILETYPE_TO_FORMAT_MAPPING[filetype] in rfc_values['formats'] for filetype in kwargs['filetypes']
        ),
    }

    for filtering, predicate in predicate_by_filtering.items():
        if kwargs[filtering]:
            rfc_subset = _get_rfc_index_subset(rfc_subset, predicate)

    if not rfc_subset:
        print("No RFC found with the current filterings.")
        return

    if not settings.download_path.exists():
        settings.download_path.mkdir()

    for rfc_number, rfc_values in rfc_subset.items():
        for filetype in kwargs['filetypes']:
            path = (settings.download_path / f'rfc_{rfc_number}.{filetype.lower()}')
            if not kwargs['download_again'] and path.exists() and path.stat().st_size:
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
