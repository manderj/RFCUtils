import functools
import itertools
import urllib.request
from urllib.parse import urljoin
import shutil

import click
from lxml import etree

from rfcutils import constant
from rfcutils import settings


width, _height = shutil.get_terminal_size()


@functools.lru_cache(1)
def update_rfc_index():
    rfc_index_request = urllib.request.urlopen(constant.RFC_INDEX_URL)
    root = etree.parse(rfc_index_request)

    index = {}
    for entry in root.findall(constant.RFC_ENTRY_TAG):
        rfc_number = entry.find(constant.RFC_DOC_ID_TAG).text.split('RFC')[1]
        index.update({
            rfc_number: {
                'url': functools.partial(constant.RFC_FILE_URL, rfc_number),
                'formats': [child.text for child in entry.find(constant.RFC_FORMAT_TAG).getchildren()],
                'current-status': entry.find(constant.RFC_CURRENT_STATUS_TAG).text,
                'abstract': ' '.join(child.text.replace('\n', ' ').replace('  ', ' ') for child in (
                    entry.find(constant.RFC_ABSTRACT_TAG).getchildren()
                    if entry.find(constant.RFC_ABSTRACT_TAG) is not None else []
                )),
            }
        })
    return index


def _get_rfc_index_subset(rfc_index, predicate):
    return {rfc_number: rfc_values for rfc_number, rfc_values in rfc_index.items() if predicate(rfc_number, rfc_values)}


def _get_text_snippet(text, max_length):
    max_length = max_length - 3
    _current_length = 0

    for index, word in enumerate(text.split(' ')):
        length = len(word) + 1 if index else len(word)
        if _current_length + length > max_length:
            break
        _current_length += length
    return f"{text[:_current_length]}{'...' if len(text) > _current_length else ''}"


@click.group()
def rfcutils():
    # mandatory for click to group all commands in same file
    # to work correcly
    pass


@rfcutils.command()
@click.argument('keywords', nargs=-1)
@click.pass_context
def search(ctx, keywords):
    rfc_index = update_rfc_index()
    # FIXME: can't call another command directly
    # ensure all rfc have been downloaded locally in txt format
    ctx.invoke(download, filetypes=[constant.TXT])

    rfc_matching = {}
    for rfc in settings.download_path.rglob('*.txt'):
        rfc_number = rfc.stem.split("rfc_")[1]
        if any(keyword in rfc.read_text() for keyword in keywords):
            rfc_matching.update({rfc_number: rfc_index[rfc_number]})

    for rfc_number, rfc_values in sorted(rfc_matching.items(), key=lambda item: item[0]):
        abstract = _get_text_snippet(rfc_values['abstract'], max_length=width - 8)  # 8 = '[RFC_NUMBER]: ' prefix length
        click.echo(click.style(f'[{rfc_number}]', fg='green') + f":\t{abstract}")

    return rfc_matching.keys()


@rfcutils.command()
@click.option('--rfc_numbers', default=['all'], multiple=True, help="rfc_numbers list to get")
@click.option(
    '--desc_contain', type=click.STRING, multiple=True,
    help="filter on rfc description containing the given words",
)
@click.option('--statuses', type=click.Choice(constant.RFC_STATUSES), default=[], multiple=True)
@click.option(
    '--filetypes', type=click.Choice(constant.RFC_FILETYPES),
    default=constant.DEFAULT_FILETYPES, multiple=True, help="format to retrieved",
)
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
            constant.FILETYPE_TO_FORMAT_MAPPING[filetype] in rfc_values['formats'] for filetype in kwargs['filetypes']
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
