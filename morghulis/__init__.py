import os

from widerface import Wider
from fddb import FDDB
from afw import AFW


def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
