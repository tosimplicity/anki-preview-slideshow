import os.path
import sys
import locale
import time, datetime
import logging
import codecs

from aqt import mw
from PyQt5.Qt import QMessageBox


def get_path(*args):

    path = mw.addonManager.addonsFolder(__name__.split(".")[0])
    for item in args:
        path = os.path.join(path, str(item).strip())
    return path


def datetime_from_struct_time(struct_time):
    return datetime.datetime.fromtimestamp(time.mktime(struct_time))


def show_text(text):

    result = QMessageBox(QMessageBox.Information, "Information:", text).exec()
    return result


def html_to_text(html):

    try:
        soup = BeautifulSoup(html, 'lxml')
        # kill all script and style elements
        for script in soup(["script", "style"]):
            script.extract()    # rip it out
        # get text
        text = soup.get_text()
    except:
        try:
            soup = BeautifulSoup(html, 'html')
            # kill all script and style elements
            for script in soup(["script", "style"]):
                script.extract()    # rip it out
            # get text
            text = soup.get_text()
        except:
            return html
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text


def log(*args):
    return logging.getLogger(__name__).info(*args)


def detect_by_bom(path, default="utf-8"):
    with open(path, 'rb') as f:
        raw = f.read(4)
    for enc, boms in \
            ('utf-8-sig', (codecs.BOM_UTF8,)),\
            ('utf-16', (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)),\
            ('utf-32', (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        if any(raw.startswith(bom) for bom in boms): return enc
    return default


def get_file_data(file_path):
    encoding_list = ("ansi", "cp1252", "gbk", "latin-1")
    utf_encoding = detect_by_bom(file_path)
    try:
        with open(file_path, "r", encoding=utf_encoding) as f:
            f_data = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding=encoding_list[0]) as f:
                f_data = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding=encoding_list[1]) as f:
                    f_data = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding=encoding_list[2]) as f:
                        f_data = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, "r", encoding=encoding_list[3]) as f:
                            f_data = f.read()
                    except UnicodeDecodeError:
                        return (False, "")
    return (True, f_data)


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
