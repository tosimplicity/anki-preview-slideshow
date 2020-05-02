import os.path
import sys
import locale
import logging

from aqt import mw
from PyQt5.Qt import QMessageBox


def get_path(*args):

    path = mw.addonManager.addonsFolder(__name__.split(".")[0])
    for item in args:
        path = os.path.join(path, str(item).strip())
    return path

def show_text(text):

    result = QMessageBox(QMessageBox.Information, "Information:", text).exec()
    return result

def log(*args):
    return logging.getLogger(__name__).info(*args)


def decode_sp(message, encoding=""):
    'special decoding, will also try coding:\n'
    '"utf-8", sys.stdout.encoding, locale.getpreferredencoding(), sys.getdefaultencoding()'
    try:
        if encoding:
            message_decoded = message.decode(encoding)
    except UnicodeDecodeError:
        pass
    try:
        message_decoded = message.decode("utf-8")
    except UnicodeDecodeError:
        try:
            message_decoded = message.decode(sys.stdout.encoding)
        except UnicodeDecodeError:
            try:
                message_decoded = message.decode(locale.getpreferredencoding())
            except UnicodeDecodeError:
                message_decoded = message.decode(sys.getdefaultencoding())
    return message_decoded


if __name__ == "__main__":
    pass
