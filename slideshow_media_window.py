import logging
import threading

from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QSizePolicy, QMenu
from PyQt5.Qt import QPixmap
from PyQt5.QtGui import QMovie, QCursor
from PyQt5.QtCore import Qt, QByteArray

from . import mplayer_extended


logger = logging.getLogger(__name__)


class SlideshowMediaWindow(QDialog):

    def __init__(self, parent, area=None, *args, **kwargs):
        "parent: parent widget"
        "area: top-left-x(to screen), top-left-y(to screen), width, height"
        super(SlideshowMediaWindow, self).__init__(parent, *args, **kwargs)
        self.setWindowTitle("Slideshow External Media Window")
        sizePolicy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setSizePolicy(sizePolicy)
        self.setAttribute(Qt.WA_DeleteOnClose, on=True)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setSizeGripEnabled(True)

        self.layout = QVBoxLayout()
        self.media_container = QLabel(self)
        self.media_container.setAttribute(Qt.WA_NativeWindow, on=True)
        # self.media_container.setFrameShape(QFrame.NoFrame)
        sizePolicy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        sizePolicy.setHeightForWidth(self.media_container.sizePolicy().hasHeightForWidth())
        self.media_container.setSizePolicy(sizePolicy)
        self.media_container.setAlignment(Qt.AlignCenter)
        self.media_container.setStyleSheet("background-color: black;")

        self.layout.addWidget(self.media_container)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.setLayout(self.layout)
        self.area = area
        if any(area):
            self.resize(area[2], area[3])
            self.move(area[0], area[1])
        else:
            self.resize(400, 300)
        self.mouse_pos = [0, 0]
        self.allow_resize_mouse_press = False

        self.pic_image = None
        self.media_container.setScaledContents(False)
        self.media_container.original_resizeEvent = self.media_container.resizeEvent

        def media_container_resizeEvent(event):
            if self.pic_image and isinstance(self.pic_image, QPixmap):
                if self.pic_image.width() > self.media_container.width() - 2 \
                   and self.pic_image.height() > self.media_container.height() - 2:
                    target_width = self.media_container.width() - 2
                    target_height = self.media_container.height() - 2
                else:
                    target_width = self.pic_image.width()
                    target_height = self.pic_image.height()
                scaled_image = self.pic_image.scaled(target_width,
                                                     target_height,
                                                     aspectRatioMode=Qt.KeepAspectRatio,
                                                     transformMode=Qt.FastTransformation)
                self.media_container.setPixmap(scaled_image)
            elif self.pic_image and isinstance(self.pic_image, QMovie):
                if self.pic_image.original_size.width() > self.media_container.width() - 2 \
                   and self.pic_image.original_size.height() > self.media_container.height() - 2:
                    target_width = self.media_container.width() - 2
                    target_height = self.media_container.height() - 2
                else:
                    target_width = self.pic_image.original_size.width()
                    target_height = self.pic_image.original_size.height()
                scaled_size = self.pic_image.original_size.scaled(target_width, target_height, Qt.KeepAspectRatio)
                self.pic_image.setScaledSize(scaled_size)
            else:
                self.media_container.original_resizeEvent(event)
        self.media_container.resizeEvent = media_container_resizeEvent

        self.show()

        self.last_media_path = ""
        self.media_show_completed_notice = None
        # this should be a function to be called like self.stop_media_show()
        self.stop_media_show = lambda: None

        self.gif_completed_notice = threading.Event()

    def show_video(self, path):
        self.stop_media_show()
        self.media_container.clear()
        # some say the winId change all the time...so...
        mplayer_extended.setup(int(self.media_container.winId()))
        self.media_show_completed_notice = mplayer_extended.play(path)
        logger.debug("ext-media-win showed video: %s" % path)
        self.last_media_path = path
        self.stop_media_show = mplayer_extended.stop

    def show_pic(self, path):
        self.stop_media_show()
        self.media_container.clear()
        if not path.lower().endswith(".gif"):
            self.pic_image = QPixmap(path)
            if self.pic_image.width() > self.media_container.width() - 2 \
               and self.pic_image.height() > self.media_container.height() - 2:
                target_width = self.media_container.width() - 2
                target_height = self.media_container.height() - 2
            else:
                target_width = self.pic_image.width()
                target_height = self.pic_image.height()
            scaled_image = self.pic_image.scaled(target_width,
                                                 target_height,
                                                 aspectRatioMode=Qt.KeepAspectRatio,
                                                 transformMode=Qt.SmoothTransformation)
            self.media_container.setPixmap(scaled_image)
            logger.debug("ext-media-win showed pic: %s" % path)
            self.stop_media_show = lambda: None
            self.media_show_completed_notice = None
        else:
            self.last_media_path = path
            self.pic_image = QMovie(path, QByteArray(), self)
            if not self.pic_image.isValid():
                self.media_show_completed_notice = None
                return
            self.pic_image.setCacheMode(QMovie.CacheAll)
            self.pic_image.jumpToNextFrame()
            self.pic_image.original_size = self.pic_image.currentPixmap().size()
            if self.pic_image.original_size.width() > self.media_container.width() - 2 \
               and self.pic_image.original_size.height() > self.media_container.height() - 2:
                target_width = self.media_container.width() - 2
                target_height = self.media_container.height() - 2
            else:
                target_width = self.pic_image.original_size.width()
                target_height = self.pic_image.original_size.height()
            scaled_size = self.pic_image.original_size.scaled(target_width, target_height, Qt.KeepAspectRatio)
            self.pic_image.setScaledSize(scaled_size)
            self.pic_image.setSpeed(100)
            self.media_container.setMovie(self.pic_image)

            self.media_show_completed_notice = self.gif_completed_notice
            self.media_show_completed_notice.clear()

            def frameChanged_Handler(frameNumber):
                if frameNumber >= self.pic_image.frameCount() - 1:
                    self.pic_image.stop()
                    self.media_show_completed_notice.set()
            self.pic_image.frameChanged.connect(frameChanged_Handler)
            self.pic_image.start()
            logger.debug("ext-media-win showed gif: %s" % path)

            def stop_gif():
                try:
                    self.pic_image.stop()
                    self.media_show_completed_notice.set()
                except Exception:
                    pass
            self.stop_media_show = stop_gif

    def contextMenuEvent(self, event):
        m = QMenu(self)
        item = m.addAction("Stop Media")
        item.triggered.connect(self.stop_media_show)
        item = m.addAction("Exit Media Window")
        item.triggered.connect(self.close)
        m.popup(QCursor.pos())

    def mousePressEvent(self, event):
        self.mouse_pos[0] = event.x()
        self.mouse_pos[1] = event.y()
        if event.globalX() < self.x() + self.frameGeometry().width() - 20 \
           or event.globalY() < self.y() + self.frameGeometry().height() - 20:
            self.allow_resize_mouse_press = True
        else:
            self.allow_resize_mouse_press = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.allow_resize_mouse_press = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.allow_resize_mouse_press:
            self.move(event.globalX() - self.mouse_pos[0],
                      event.globalY() - self.mouse_pos[1])
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.stop_media_show()
        self.area[0] = self.x()
        self.area[1] = self.y()
        self.area[2] = self.width()
        self.area[3] = self.height()
        event.accept()
