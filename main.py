# -*- coding:utf-8 -*-
import os
import os.path
import sys
import time
import random
import traceback
import logging
from threading import Event

from PyQt5.Qt import *
from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout

from aqt import mw
from anki.consts import *

from .utils import show_text
from .slideshow_media_window import SlideshowMediaWindow
from .slideshow_thread import SlideshowPreviewThread
from . import mplayer_extended

logger = logging.getLogger(__name__)

MEDIAS = (".mp4", ".mkv", ".avi", ".flv", ".m4v", ".f4v", ".rmvb",
          ".mpg", ".mpeg", ".mov", ".mp3", ".flac", ".m4a")
AUDIOS = (".mp3", ".flac", ".m4a")
PICTURES = (".jpg", ".png", ".gif", ".jpeg")
INSTRUCTIONS = """1. Check/Uncheck "Slideshow On/Off" to start/stop slideshow
2. Check/Uncheck "Random Seq" to activate/disable random sequence
3. Click "||" button to pause slideshow
4. Click "|>" button to continue slideshow or go to next slide
5. Use tag like "slideshow_Xs" to indicate showing answer for X seconds
   (no time tag for question)
   for example, "slideshow_17s" for 17 seconds
6. Use tag "slideshow_aisq" to indicate question slide is same with answer slide and answer slide should be skipped.
7. To show external media like mp4, jpg, gif.
   a. Create a field in exact name "Slideshow_External_Media"
   b. Put the file path for the external media file there like "D:/somefolder/myvideo.mp4"
   c. Root forder can also be set in settings. Like setting it to "D:/somefolder"
      then "Slideshow_External_Media" field can work in relative path like "myvideo.mp4", "sometype/blabla.png"
8. A trick: to align buttons in preview window left, open preview window, resize it to a very small one, reopen it
9. Hover over buttons to see tooltips
"""

# global variable to get ref to browser window and preview window and ui elements
browser = None
preview_window = None
preview_slideshow_switch = None
set_slideshow_q_time_button = None
set_slideshow_a_time_button = None
change_slideshow_setting_dialog = None
external_media_show_mode_button = None
slideshow_media_window_area = [0, 0, 0, 0]
config = mw.addonManager.getConfig(__name__)
# is_timeout_special: if certain card has its own timeout setting
slideshow_profile = {"q_time": 3,
                     "a_time": 5,
                     "is_on": False,
                     "timeout": 0,
                     "is_timeout_special": False,
                     "special_timeout": 0,
                     "random_sequence": False,
                     "is_showing_question": False,
                     "showed_cards": [],
                     "should_pause": False,
                     "should_play_next": False,
                     "show_external_media_event": Event(),
                     "external_media_show_mode": "on"}
# set up slideshow_profile default value
if "preview_slideshow_show_question_time" in config:
    q_time = config["preview_slideshow_show_question_time"]
    try:
        q_time = int(q_time)
    except Exception:
        q_time = 3
    if q_time < 1:
        q_time = 3
    if q_time != config["preview_slideshow_show_question_time"]:
        config["preview_slideshow_show_question_time"] = q_time
        mw.addonManager.writeConfig(__name__, config)
    slideshow_profile["q_time"] == q_time
if "preview_slideshow_show_answer_time" in config:
    a_time = config["preview_slideshow_show_answer_time"]
    try:
        a_time = int(a_time)
    except Exception:
        a_time = 5
    if a_time < 1:
        a_time = 5
    if a_time != config["preview_slideshow_show_answer_time"]:
        config["preview_slideshow_show_answer_time"] = a_time
        mw.addonManager.writeConfig(__name__, config)
    slideshow_profile["a_time"] = a_time
if "external_media_show_mode" in config:
    if config["external_media_show_mode"] not in ["off",
                                                  "on",
                                                  "on_and_backoff_if_empty"]:
        config["external_media_show_mode"] = "on"
        mw.addonManager.writeConfig(__name__, config)
    else:
        slideshow_profile["external_media_show_mode"] = config["external_media_show_mode"]

if "external_media_folder_path" in config and config["external_media_folder_path"]:
    EXTERNAL_MEDIA_ROOT = config["external_media_folder_path"]
else:
    EXTERNAL_MEDIA_ROOT = ""


def setup_preview_slideshow(target_browser):
    "prepare when browser window shows up."
    if target_browser:
        global browser
        browser = target_browser
    else:
        return
    form = target_browser.form
    form.previewButton.clicked.connect(add_slideshow_ui_to_preview_window)


def add_slideshow_ui_to_preview_window():
    "add ui elements to preview window"
    global browser
    if not browser:
        return
    time.sleep(0.5)
    global preview_window
    i = 0
    while True:
        try:
            if browser._previewWindow.isVisible() and browser._previewNext.isVisible():
                preview_window = browser._previewWindow
                break
        except Exception:
            pass
        if i >= 10:
            # preview_window is closing
            preview_window = None
            return
        else:
            # well pc is really slow
            i += 1
            time.sleep(0.2)
            continue

    bbox = browser._previewNext.parentWidget()

    slideshow_profile["is_on"] = False
    global preview_slideshow_switch
    preview_slideshow_switch = QCheckBox("Slideshow On/Off")
    preview_slideshow_switch.setToolTip("Activate to start auto slideshow")
    preview_slideshow_switch.setChecked(False)
    bbox.addButton(preview_slideshow_switch, QDialogButtonBox.ActionRole)
    preview_slideshow_switch.toggled.connect(on_switch_preview_slideshow)

    slideshow_pause_button = bbox.addButton("||", QDialogButtonBox.ActionRole)
    slideshow_pause_button.setAutoDefault(True)
    slideshow_pause_button.setToolTip("Pause the Slideshow")
    slideshow_pause_button.clicked.connect(request_pause_slideshow)

    slideshow_next_button = bbox.addButton("|>", QDialogButtonBox.ActionRole)
    slideshow_next_button.setAutoDefault(True)
    slideshow_next_button.setToolTip("Pause the Slideshow")
    slideshow_next_button.clicked.connect(request_play_next_slideshow)

    width = slideshow_next_button.fontMetrics().boundingRect("  |>  ").width() + 6
    slideshow_pause_button.setMaximumWidth(width)
    slideshow_next_button.setMaximumWidth(width)

    preview_slideshow_rand_seq = QCheckBox("Random Seq")
    preview_slideshow_rand_seq.setToolTip("Choose if slideshow in random sequence")
    preview_slideshow_rand_seq.setChecked(False)
    slideshow_profile["random_sequence"] = False
    bbox.addButton(preview_slideshow_rand_seq, QDialogButtonBox.ActionRole)
    preview_slideshow_rand_seq.toggled.connect(set_slideshow_preview_sequence)

    change_slideshow_setting_button = bbox.addButton("Slideshow Setting", QDialogButtonBox.ActionRole)
    change_slideshow_setting_button.setAutoDefault(True)
    change_slideshow_setting_button.setToolTip("Change Slideshow Settings")
    change_slideshow_setting_button.clicked.connect(change_slideshow_setting)

    # dev_debug_button = bbox.addButton(f"Debug", QDialogButtonBox.ActionRole)
    # dev_debug_button.setAutoDefault(True)
    # dev_debug_button.clicked.connect(dev_debug)

    width = browser._previewNext.fontMetrics().boundingRect("  >  ").width() + 6
    browser._previewNext.setMaximumWidth(width)
    browser._previewPrev.setMaximumWidth(width)

    preview_window.layout().removeWidget(bbox)
    bbox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    scroll_area = QScrollArea(preview_window)
    scroll_area.setWidget(bbox)
    #scroll_area.setWidget(QLabel("LAAAABEL"))
    scroll_area.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll_area.setFixedHeight(bbox.height() + 5)
    preview_window.layout().addWidget(scroll_area)

    # add context menu
    preview_window.setContextMenuPolicy(Qt.CustomContextMenu)
    preview_window.customContextMenuRequested.connect(show_context_menu_of_preview_window)


def show_context_menu_of_preview_window(pos):

    m = QMenu(preview_window)
    if not preview_slideshow_switch.isChecked():
        item = m.addAction("Start Slideshow")
        item.triggered.connect(lambda: preview_slideshow_switch.setChecked(True))
    else:
        item = m.addAction("End Slideshow")
        item.triggered.connect(lambda: preview_slideshow_switch.setChecked(False))
    item = m.addAction("Pause Slideshow")
    item.triggered.connect(request_pause_slideshow)
    item = m.addAction("Pause Slideshow - Keep Media Show")
    item.triggered.connect(lambda: request_pause_slideshow(keep_media_show=True))
    item = m.addAction("Play Next - Slideshow")
    item.triggered.connect(request_play_next_slideshow)
    m.popup(QCursor.pos())


def change_slideshow_setting():

    global change_slideshow_setting_dialog
    config = mw.addonManager.getConfig(__name__)
    change_slideshow_setting_dialog = QDialog(preview_window)
    change_slideshow_setting_dialog.setWindowTitle("Preview Slideshow Setting")
    layout = QVBoxLayout()

    if "preview_slideshow_show_question_time" in config:
        q_time = config["preview_slideshow_show_question_time"]
        try:
            q_time = int(q_time)
        except Exception:
            q_time = 3
        if q_time < 1:
            q_time = 3
        if q_time != config["preview_slideshow_show_question_time"]:
            config["preview_slideshow_show_question_time"] = q_time
            mw.addonManager.writeConfig(__name__, config)
    else:
        q_time = config["preview_slideshow_show_question_time"] = 3
        mw.addonManager.writeConfig(__name__, config)
    slideshow_profile["q_time"] = q_time
    global set_slideshow_q_time_button
    set_slideshow_q_time_button = QPushButton("Set Question Time(%ss)" % q_time)
    set_slideshow_q_time_button.setToolTip("Set the time displaying question")
    set_slideshow_q_time_button.clicked.connect(set_preview_slideshow_question_time)

    # show_text(repr(config["preview_slideshow_show_answer_time"]))
    if "preview_slideshow_show_answer_time" in config:
        a_time = config["preview_slideshow_show_answer_time"]
        try:
            a_time = int(a_time)
        except Exception:
            a_time = 5
        if a_time < 1:
            a_time = 5
        if a_time != config["preview_slideshow_show_answer_time"]:
            config["preview_slideshow_show_answer_time"] = a_time
            mw.addonManager.writeConfig(__name__, config)
    else:
        a_time = config["preview_slideshow_show_answer_time"] = 5
        mw.addonManager.writeConfig(__name__, config)
    slideshow_profile["a_time"] = a_time
    global set_slideshow_a_time_button
    set_slideshow_a_time_button = QPushButton("Set Answer Time(%ss)" % a_time)
    set_slideshow_a_time_button.setToolTip("Set the time displaying answer")
    set_slideshow_a_time_button.clicked.connect(set_preview_slideshow_answer_time)

    # external_media_show_mode
    # below line is required, otherwise ref is missing
    global external_media_show_mode_button
    if "external_media_show_mode" in config:
        external_media_show_mode = config["external_media_show_mode"]
        if external_media_show_mode not in ["off",
                                            "on",
                                            "on_and_backoff_if_empty"]:
            external_media_show_mode = "on"
    else:
        external_media_show_mode = "on"
    slideshow_profile["external_media_show_mode"] = external_media_show_mode
    if "external_media_show_mode" not in config \
       or config["external_media_show_mode"] != external_media_show_mode:
        config["external_media_show_mode"] = external_media_show_mode
        mw.addonManager.writeConfig(__name__, config)
    if external_media_show_mode == "on_and_backoff_if_empty":
        external_media_show_mode_button_text = "\n" + external_media_show_mode.capitalize()
    else:
        external_media_show_mode_button_text = external_media_show_mode.capitalize()
    external_media_show_mode_button = QPushButton("External Media Show Mode: %s" % external_media_show_mode_button_text)
    external_media_show_mode_button.setToolTip("Loop through setting on how to show external media:\n"
                                               "off - ignore any exteral media\n"
                                               "on - show external media window after first exteral media found\n"
                                               "on_and_backoff_if_empty - show external media window if any, \n"
                                               "but bring up preview window if external media field is empty.")

    def change_external_media_show_mode():
        if slideshow_profile["external_media_show_mode"] == "off":
            external_media_show_mode = "on"
        if slideshow_profile["external_media_show_mode"] == "on":
            external_media_show_mode = "on_and_backoff_if_empty"
        if slideshow_profile["external_media_show_mode"] == "on_and_backoff_if_empty":
            external_media_show_mode = "off"
        slideshow_profile["external_media_show_mode"] = external_media_show_mode
        config = mw.addonManager.getConfig(__name__)
        if "external_media_show_mode" not in config \
           or config["external_media_show_mode"] != external_media_show_mode:
            config["external_media_show_mode"] = external_media_show_mode
            mw.addonManager.writeConfig(__name__, config)
        if external_media_show_mode == "on_and_backoff_if_empty":
            external_media_show_mode_button_text = "\n" + external_media_show_mode.capitalize()
        else:
            external_media_show_mode_button_text = external_media_show_mode.capitalize()
        external_media_show_mode_button.setText("External Media Show Mode: %s" % external_media_show_mode_button_text)
    external_media_show_mode_button.clicked.connect(change_external_media_show_mode)

    set_external_media_folder_button = QPushButton("Set External Media Folder Root")
    set_external_media_folder_button.setToolTip("Select root folder for external media."
                                                "When set, relative path can be use in"
                                                ' "Slideshow_External_Media" field')
    set_external_media_folder_button.clicked.connect(change_external_media_folder)

    set_external_media_volume_button = QPushButton("Set External Media Volume")
    set_external_media_volume_button.setToolTip("Set External Media Volume.\n"
                                                "Effective after external media window restarted.")

    def set_external_media_volume():
        global change_slideshow_setting_dialog
        volume_control = ExternalMediaVolumeControlSlider(change_slideshow_setting_dialog)
        volume_control.show()
    set_external_media_volume_button.clicked.connect(set_external_media_volume)

    show_instruction_button = QPushButton("Show Instruction")
    show_instruction_button.clicked.connect(lambda: show_text(INSTRUCTIONS))

    layout.addWidget(set_slideshow_q_time_button)
    layout.addWidget(set_slideshow_a_time_button)
    layout.addWidget(external_media_show_mode_button)
    layout.addWidget(set_external_media_folder_button)
    layout.addWidget(set_external_media_volume_button)
    layout.addWidget(show_instruction_button)
    change_slideshow_setting_dialog.setLayout(layout)
    change_slideshow_setting_dialog.exec()


class ExternalMediaVolumeControlSlider(QSlider):

    def __init__(self, parent, *args, **kwargs):
        super().__init__(Qt.Horizontal, parent, *args, **kwargs)
        self.setMinimum(0)
        self.setMaximum(100)
        self.config = mw.addonManager.getConfig(__name__)
        try:
            self.volume = int(config["mplayer_startup_volume"])
        except Exception:
            self.volume = 50
        if self.volume < 0 or self.volume > 100:
            self.volume = 50
        self.setValue(self.volume)
        self.setToolTip("Current - %s%%" % self.volume)
        self.valueChanged.connect(self.set_volume)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.Popup)
        self.setStyleSheet("border:1px solid grey;")
        self.move(QCursor.pos().x() - self.width(), QCursor.pos().y())

    def set_volume(self, volume):
        self.config = mw.addonManager.getConfig(__name__)
        self.volume = self.config["mplayer_startup_volume"] = volume
        self.setToolTip("Current - %s%%" % volume)
        QToolTip.showText(QCursor.pos(), "%s%%" % volume, self)


    def mousePressEvent(self, event):
        if event.globalX() < self.x() \
           or event.globalX() > self.x() + self.frameGeometry().width() \
           or event.globalY() < self.y() \
           or event.globalY() > self.y() + self.frameGeometry().height():
            mw.addonManager.writeConfig(__name__, self.config)
            logger.debug("External Media Volume Set to %s" % self.volume)
            self.close()
        super().mousePressEvent(event)


def set_preview_slideshow_question_time():
    new_q_time, is_ok = QInputDialog.getInt(change_slideshow_setting_dialog,
                                            "Change Question Displaying Time",
                                            "Input question displaying time in seconds",
                                            value=slideshow_profile["q_time"],
                                            min=1,
                                            max=60 * 60,
                                            step=1)
    q_time = slideshow_profile["q_time"]
    global set_slideshow_q_time_button
    if is_ok:
        if new_q_time != q_time:
            q_time = new_q_time
            config = mw.addonManager.getConfig(__name__)
            config["preview_slideshow_show_question_time"] = q_time
            mw.addonManager.writeConfig(__name__, config)
            set_slideshow_q_time_button.setText("Set Question Time(%ss)" % q_time)
            slideshow_profile["q_time"] = q_time


def set_preview_slideshow_answer_time():
    new_a_time, is_ok = QInputDialog.getInt(change_slideshow_setting_dialog,
                                            "Change Answer Displaying Time",
                                            "Input answer displaying time in seconds",
                                            value=slideshow_profile["a_time"],
                                            min=1,
                                            max=60 * 60,
                                            step=1)
    a_time = slideshow_profile["a_time"]
    global set_slideshow_a_time_button
    if is_ok:
        if new_a_time != a_time:
            a_time = new_a_time
            config = mw.addonManager.getConfig(__name__)
            config["preview_slideshow_show_answer_time"] = a_time
            mw.addonManager.writeConfig(__name__, config)
            set_slideshow_a_time_button.setText("Set Answer Time(%ss)" % a_time)
            slideshow_profile["a_time"] = a_time


def change_external_media_folder():
    config = mw.addonManager.getConfig(__name__)
    if "external_media_folder_path" in config:
        path = config["external_media_folder_path"]
        if not os.path.isdir(path):
            path = ""
    else:
        path = ""
    new_path = QFileDialog.getExistingDirectory(change_slideshow_setting_dialog,
                                                "Set External Media Folder Root",
                                                path,
                                                QFileDialog.ShowDirsOnly
                                                | QFileDialog.DontResolveSymlinks)
    if not os.path.isdir(new_path):
        return
    else:
        show_text("External media folder root set to:\n" + new_path)
        config["external_media_folder_path"] = new_path
        mw.addonManager.writeConfig(__name__, config)
        global EXTERNAL_MEDIA_ROOT
        EXTERNAL_MEDIA_ROOT = new_path

def set_slideshow_preview_sequence(state):

    if state:
        slideshow_profile["random_sequence"] = True
    else:
        slideshow_profile["random_sequence"] = False


def request_pause_slideshow(keep_media_show=False):
    global preview_window
    slideshow_profile["should_pause"] = True
    slideshow_profile["should_play_next"] = False
    if not keep_media_show:
        try:
            preview_window.slideshow_media_window.stop_media_show()
        except Exception:
            pass


def request_play_next_slideshow():

    try:
        preview_window.slideshow_media_window.stop_media_show()
    except Exception:
        pass
    slideshow_profile["should_play_next"] = True
    slideshow_profile["should_pause"] = False


def on_switch_preview_slideshow(switch_state):
    if not switch_state:
        if slideshow_profile["is_on"]:
            stop_slideshow()
        return

    slideshow_profile["should_play_next"] = False
    slideshow_profile["should_pause"] = False

    try:
        if not browser.isVisible() or not preview_window.isVisible():
            return
    except Exception:
        return
    browser.destroyed.connect(stop_slideshow)
    preview_window.destroyed.connect(stop_slideshow)
    c = browser.card
    if not c or not browser.singleCard:
        show_text("please select 1 card.")
        stop_slideshow()
        return

    slideshow_profile["is_on"] = True
    slideshow_profile["should_pause"] = False
    slideshow_profile["should_play_next"] = False
    slideshow_preview_thread = SlideshowPreviewThread(slideshow_profile, browser, preview_window)
    slideshow_preview_thread.signals.next_slide_signal.connect(turn_to_next_slide_preview)
    slideshow_preview_thread.signals.elapsed_time_signal.connect(update_preview_slideshow_switch_text)
    slideshow_preview_thread.signals.request_show_external_media_signal.connect(show_external_media)
    slideshow_preview_thread.signals.request_change_windows_stack_signal.connect(_arrange_windows_stack_sequence)
    thread_pool = QThreadPool.globalInstance()
    thread_pool.start(slideshow_preview_thread)
    logger.info("----------started preview slideshow thread----------")

    return


def turn_to_next_slide_preview(flag_go_next):
    if not flag_go_next:
        return
    try:
        if not browser.isVisible() or not preview_window.isVisible():
            stop_slideshow()
            return
    except Exception:
        stop_slideshow()
        return
    if not slideshow_profile["is_on"]:
        return
    #  can not use browser._previewState == "question", don't know why
    if slideshow_profile["is_showing_question"]:
        browser._onPreviewNext()
    elif not slideshow_profile["random_sequence"]:
        canForward = browser.currentRow() < browser.model.rowCount(None) - 1
        if not not (browser.singleCard and canForward):
            browser._onPreviewNext()
        else:
            stop_slideshow()
    else:
        if len(browser.model.cards) > 1:
            # if all cards are showed, start like no card has been showed
            if len(slideshow_profile["showed_cards"]) >= browser.model.rowCount(None):
                slideshow_profile["showed_cards"] = []
            new_row = browser.model.cards.index(random.choice(list(
                set(browser.model.cards)
                - set(slideshow_profile["showed_cards"])
                )))
            slideshow_profile["showed_cards"].append(browser.model.cards[new_row])
            # logger.debug("recorded showed_cards, row %s, card " % new_row
            #              + browser.model.question(browser.model.getCard(browser.model.index(new_row, 0))))
        else:
            stop_slideshow()
            return
        browser.editor.saveNow(lambda: browser._moveCur(None, browser.model.index(new_row, 0)))
    # logger.debug("main thread seeing card " + browser.card._getQA()['q'])
    return


def update_preview_slideshow_switch_text(elapsed_time):
    if elapsed_time == -1:
        # wait for external media, maybe...
        count_down = "X"
    elif slideshow_profile["is_timeout_special"] and not slideshow_profile["is_showing_question"]:
        count_down = slideshow_profile["special_timeout"] - elapsed_time
    else:
        count_down = slideshow_profile["timeout"] - elapsed_time
    # x = "show_q" if slideshow_profile["is_showing_question"] else "not_q"
    # y = "sp_t" if slideshow_profile["is_timeout_special"] else "not_sp_t"
    # preview_slideshow_switch.setText(f"Slideshow On: {count_down}s {x} {y}")
    if slideshow_profile["should_pause"]:
        preview_slideshow_switch.setText("Slideshow On: Pause")
    else:
        preview_slideshow_switch.setText("Slideshow On: %ss" % count_down)


def show_external_media(path):
    global browser, preview_window, EXTERNAL_MEDIA_ROOT
    path = os.path.join(EXTERNAL_MEDIA_ROOT, path)
    # logger.debug("get rqt for ext media: %s" % path)
    if not path or not os.path.isfile(path) \
       or not any([path.lower().endswith(ext) for ext in MEDIAS + PICTURES]) \
       or not preview_window or not browser:
        if not (preview_window and browser):
            logger.debug("show ext media denied: no browser/preview_window")
        elif not (os.path.isfile(path)):
            logger.debug("show ext media denied: '%s' not existing" % path)
        elif not any([path.lower().endswith(ext) for ext in MEDIAS + PICTURES]):
            logger.debug("show ext media denied: '%s' not in ext %s" % (path, repr(MEDIAS + PICTURES)))
        slideshow_profile["show_external_media_event"].set()
        return
    global slideshow_media_window_area
    try:
        if not preview_window.slideshow_media_window.isVisible():
            preview_window.slideshow_media_window = SlideshowMediaWindow(preview_window.parent(),
                                                                         slideshow_media_window_area)
            logger.info("started new slideshow media window")
    except Exception:
        preview_window.slideshow_media_window = SlideshowMediaWindow(preview_window.parent(),
                                                                     slideshow_media_window_area)
        logger.info("started new slideshow media window")
    try:
        if any([path.lower().endswith(ext) for ext in MEDIAS]):
            preview_window.slideshow_media_window.show_video(path)
            logger.debug("sent ext medio play request %s" % path)
        else:
            preview_window.slideshow_media_window.show_pic(path)
            logger.debug("sent ext pic show request %s" % path)
        if slideshow_profile["external_media_show_mode"] == "on_and_backoff_if_empty":
            if not any([path.lower().endswith(ext) for ext in AUDIOS]):
                _arrange_windows_stack_sequence("slideshow_media_window")
            else:
                _arrange_windows_stack_sequence("preview_window")
    except Exception:
        # don't care if external can't be showed correctly
        # though we hope it can
        pass
    slideshow_profile["show_external_media_event"].set()
    return


def _arrange_windows_stack_sequence(name_of_widget_to_raise):

    try:
        if name_of_widget_to_raise == "preview_window":
            preview_window.raise_()
        if name_of_widget_to_raise == "slideshow_media_window":
            preview_window.slideshow_media_window.raise_()
    except Exception:
        pass


def stop_slideshow(source_object=None):

    slideshow_profile["is_on"] = False
    slideshow_profile["timeout"] = 0
    slideshow_profile["is_timeout_special"] = False
    slideshow_profile["special_timeout"] = 0
    slideshow_profile["is_showing_question"] = False
    slideshow_profile["showed_cards"] = []
    slideshow_profile["should_pause"] = False
    slideshow_profile["should_play_next"] = False

    if preview_slideshow_switch:
        preview_slideshow_switch.setText("Slideshow On/Off")
        preview_slideshow_switch.setChecked(False)

    mplayer_extended.stop()
    try:
        preview_window.slideshow_media_window.close()
    except Exception:
        pass
    logger.info("stopped slideshow")


def dev_debug():
    from PyQt5.QtWidgets import QListWidget
    from PyQt5.QtCore import Qt

    debug_actions = {}

    def close_media_window():
        preview_window.slideshow_media_window.stop_media_show()
        preview_window.slideshow_media_window.close()
    debug_actions["close_media_window"] = close_media_window

    def play_mp4():
        path = r"d:\Downloads\InstaDown\45164780_311995036059669_6665285820453537716_n.mp4"
        show_external_media(path)
    debug_actions["play_mp4"] = play_mp4

    def show_pic():
        show_external_media(r"tumblr_p5nc3j7HyR1vlrtooo1_540.jpg")
    debug_actions["show_pic"] = show_pic

    debug_choices = QListWidget(preview_window)
    debug_choices.setWindowFlags(Qt.Window)
    for action_name in debug_actions:
        debug_choices.addItem(action_name)
        debug_choices.itemDoubleClicked.connect(lambda item: debug_actions[item.text()]())
    debug_choices.show()
