from urllib.parse import urljoin


SITE_URL = 'https://www.ietf.org/rfc/'
RFC_INDEX_URL = urljoin(SITE_URL, 'rfc-index.xml')
RFC_FILE_URL = lambda rfc_number, filetype: urljoin(SITE_URL, f'rfc{rfc_number}.{filetype}')

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
HTML = 'HTML'
PDF = 'PDF'
XML = 'XML'
DEFAULT_FILETYPES = [TXT, PDF, HTML]
FILETYPE_TO_FORMAT_MAPPING = {
    TXT: 'TEXT',
    HTML: 'HTML',
    PDF: 'PDF',
    XML: 'XML',
}
RFC_FILETYPES = FILETYPE_TO_FORMAT_MAPPING.keys()
