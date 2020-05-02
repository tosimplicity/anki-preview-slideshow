# -*- coding:utf-8 -*-
import time
import re
import logging

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable
from aqt import appVersion


logger = logging.getLogger(__name__)


class SlideshowPreviewThreadSignals(QObject):
    next_slide_signal = pyqtSignal(bool)
    elapsed_time_signal = pyqtSignal(int)
    request_show_external_media_signal = pyqtSignal(str)
    request_change_windows_stack_signal = pyqtSignal(str)


class SlideshowPreviewThread(QRunnable):

    def __init__(self, slideshow_profile, browser, preview_window):
        super(SlideshowPreviewThread, self).__init__()
        self.slideshow_profile = slideshow_profile
        self.signals = SlideshowPreviewThreadSignals()
        self.browser = browser
        self.preview_window = preview_window
        self.external_media_show_completed_notice = None

    def run(self):
        last_slide_time = 0
        last_elapsed_time = 0
        if self.slideshow_profile["timeout"] < 1:
            self.slideshow_profile["timeout"] = 1
        timeout_in_tag_pattern = re.compile(r"slideshow_(\d+)s")
        # slide_counter = 0
        while self.slideshow_profile["is_on"]:
            elapsed_time = int(time.time() - last_slide_time)
            if self.slideshow_profile["should_play_next"] \
               or (not self.slideshow_profile["should_pause"]
                   and elapsed_time >= self.slideshow_profile["timeout"]):

                # need to turn to next slide
                self.slideshow_profile["should_play_next"] = False
                self.external_media_show_completed_notice = None
                if last_slide_time != 0:
                    self.signals.elapsed_time_signal.emit(self.slideshow_profile["timeout"])
                    self.signals.next_slide_signal.emit(True)
                # slide_counter += 1
                # logger.debug(f"SIGNAL NEXT SLIDE >>> NO {slide_counter}")
                last_slide_time = time.time()
                last_elapsed_time = 0
                # wait a while for next action
                time.sleep(0.5)
                try:
                    if not self.browser.isVisible() or not self.preview_window.isVisible():
                        # let main thread handle this problem
                        self.signals.next_slide_signal.emit(True)
                        return
                except Exception:
                    # let main thread handle this problem
                    self.signals.next_slide_signal.emit(True)
                    return
                c = self.browser.card
                if not c or not self.browser.singleCard:
                    return
                if appVersion >= "2.1.24":
                    preview_state = self.preview_window._state
                    card_question = self.browser.card.render_output().question_text
                else:
                    preview_state = self.browser._previewState
                    card_question = self.browser.card._getQA()['q']
                if preview_state == "question":
                    # default values
                    self.slideshow_profile["is_timeout_special"] = False
                    self.slideshow_profile["is_showing_question"] = True
                    # check if default is not the case
                    timeout_tag_match = None
                    # check if question slide is answer slide
                    for tag in self.browser.card.note().tags:
                        if tag.strip().lower() == "slideshow_aisq":
                            self.slideshow_profile["is_showing_question"] = False
                            if appVersion >= "2.1.24":
                                self.preview_window._state = "answer"
                            else:
                                self.browser._previewState = "answer"
                        if not timeout_tag_match:
                            timeout_tag_match = timeout_in_tag_pattern.match(tag)
                            if timeout_tag_match:
                                logger.debug("Card with time tag: %s" % tag + card_question)
                                self.slideshow_profile["is_timeout_special"] = True
                                self.slideshow_profile["special_timeout"] = int(timeout_tag_match.group(1))
                    if self.slideshow_profile["is_showing_question"]:
                        self.slideshow_profile["timeout"] = self.slideshow_profile["q_time"]
                        logger.debug("use question timeout: " + card_question)
                        if self.slideshow_profile["external_media_show_mode"] == "on_and_backoff_if_empty":
                            self.signals.request_change_windows_stack_signal.emit("preview_window")
                    else:
                        # a slide is same as q slide
                        if self.slideshow_profile["external_media_show_mode"] in ["on", "on_and_backoff_if_empty"]:
                            self._process_external_media()
                        if self.external_media_show_completed_notice:
                            # showing external media
                            self.slideshow_profile["timeout"] = 60 * 60 * 24
                            logger.debug("timeout - wait for ext media play: " + card_question)
                        elif not self.slideshow_profile["is_timeout_special"]:
                            self.slideshow_profile["timeout"] = self.slideshow_profile["a_time"]
                            logger.debug("use answer timeout (q=a): " + card_question)
                        else:
                            self.slideshow_profile["timeout"] = self.slideshow_profile["special_timeout"]
                            logger.debug("use special_timeout (q=a): " + card_question)
                else:
                    self.slideshow_profile["is_showing_question"] = False
                    self.slideshow_profile["is_timeout_special"] = False
                    if self.slideshow_profile["external_media_show_mode"] in ["on", "on_and_backoff_if_empty"]:
                        self._process_external_media()
                    if self.external_media_show_completed_notice:
                        # showing external media
                        self.slideshow_profile["timeout"] = 60 * 60 * 24
                        logger.debug("timeout - wait for ext media play: " + card_question)
                    else:
                        # still need this because question may not be showed in the process
                        for tag in self.browser.card.note().tags:
                            match = timeout_in_tag_pattern.match(tag)
                            if match:
                                logger.debug("Card with time tag: %s" % tag + card_question)
                                self.slideshow_profile["is_timeout_special"] = True
                                self.slideshow_profile["special_timeout"] = int(match.group(1))
                                break
                        if not self.slideshow_profile["is_timeout_special"]:
                            self.slideshow_profile["timeout"] = self.slideshow_profile["a_time"]
                            logger.debug("use answer timeout: " + card_question)
                        else:
                            self.slideshow_profile["timeout"] = self.slideshow_profile["special_timeout"]
                            logger.debug("use special_timeout: " + card_question)
            else:
                if self.external_media_show_completed_notice and self.external_media_show_completed_notice.is_set():
                    self.slideshow_profile["timeout"] = 0
                    self.external_media_show_completed_notice = None
                elif self.external_media_show_completed_notice:
                    self.signals.elapsed_time_signal.emit(-1)
                elif elapsed_time > last_elapsed_time:
                    self.signals.elapsed_time_signal.emit(elapsed_time)
                last_elapsed_time = elapsed_time
                time.sleep(0.2)
        return

    def _process_external_media(self):

        self.external_media_show_completed_notice = None
        try:
            if not self.browser.isVisible() or not self.preview_window.isVisible():
                return
        except Exception:
            return
        c = self.browser.card
        if not c or not self.browser.singleCard:
            return
        note = c.note()
        if "Slideshow_External_Media" in self.browser.col.models.fieldNames(note.model()):
            # there is external media in this card
            # logger.debug("Card with Slideshow_External_Media field: '%s'" % c._getQA()['q'])
            path = note["Slideshow_External_Media"].strip()
            if appVersion >= "2.1.24":
                card_question = c.render_output().question_text
            else:
                card_question = c._getQA()['q']
            logger.debug("Card '%s' External_Media field: '%s'" % (card_question, path))
            if not path:
                if self.slideshow_profile["external_media_show_mode"] == "on_and_backoff_if_empty":
                    self.signals.request_change_windows_stack_signal.emit("preview_window")
                return
        else:
            # there is no external media in this card
            if self.slideshow_profile["external_media_show_mode"] == "on_and_backoff_if_empty":
                self.signals.request_change_windows_stack_signal.emit("preview_window")
            return
        self.slideshow_profile["show_external_media_event"].clear()
        self.signals.request_show_external_media_signal.emit(path)
        self.slideshow_profile["show_external_media_event"].wait(timeout=3)
        if not self.slideshow_profile["show_external_media_event"].is_set():
            return
        try:
            if not self.preview_window.slideshow_media_window.media_show_completed_notice.is_set():
                self.external_media_show_completed_notice \
                    = self.preview_window.slideshow_media_window.media_show_completed_notice
        except Exception:
            pass
        return

