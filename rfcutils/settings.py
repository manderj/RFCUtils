import pathlib
import os


DEFAULT_DOWNLOAD_FOLDER = './rfc'
download_path = pathlib.Path(os.getenv('RFCDOWNLOADER_FOLDER', DEFAULT_DOWNLOAD_FOLDER)).expanduser()
