# -*- coding: utf-8 -*-
# Anki sound.py is changed and extended to get more functions required by Anki Relate to My Doc add-on

import re, sys, threading, time, subprocess, os, atexit
import os.path
import random
import logging
from queue import Queue
from queue import Empty as Queue_Empty
from PyQt5.Qt import QMessageBox
from anki.hooks import addHook
from anki.utils import tmpdir, isWin, isMac, isLin
from aqt import mw

from .utils import decode_sp

logger = logging.getLogger(__name__)

# Packaged commands
##########################################################################

# return modified command array that points to bundled command, and return
# required environment
def _packagedCmd(cmd):
    cmd = cmd[:]
    env = os.environ.copy()
    if "LD_LIBRARY_PATH" in env:
        del env['LD_LIBRARY_PATH']
    if isMac:
        dir = os.path.dirname(os.path.abspath(__file__))
        exeDir = os.path.abspath(dir + "/../../Resources/audio")
    else:
        exeDir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if isWin and not cmd[0].endswith(".exe"):
            cmd[0] += ".exe"
    path = os.path.join(exeDir, cmd[0])
    if not os.path.exists(path):
        return cmd, env
    cmd[0] = path
    return cmd, env

##########################################################################

# don't show box on windows
if isWin:
    si = subprocess.STARTUPINFO()
    try:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    except:
        # python2.7+
        si.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
else:
    si = None

# Mplayer in slave mode
##########################################################################

# if anki crashes, an old mplayer instance may be left lying around,
# which prevents renaming or deleting the profile
def cleanupOldMplayerProcesses():
    # pylint: disable=import-error
    try:
        import psutil
    except ImportError:
        return

    exeDir = os.path.dirname(os.path.abspath(sys.argv[0]))

    for proc in psutil.process_iter():
        try:
            info = proc.as_dict(attrs=['pid', 'name', 'exe'])
            if not info['exe'] or info['name'] != 'mplayer.exe':
                continue

            # not anki's bundled mplayer
            if os.path.dirname(info['exe']) != exeDir:
                continue

            print("terminating old mplayer process...")
            proc.kill()
        except:
            print("error iterating mplayer processes")

# mplayerCmd = ["mplayer", "-really-quiet", "-noautosub"]
# mplayerCmd = ["mplayer", "-identify", "-really-quiet", "-noautosub"]
mplayerCmd = ["mplayer", "-msglevel", "all=0:global=6:identify=4",
              "-noautosub"]
if isWin:
    mplayerCmd += ["-vo", "directx:noaccel", "-ao", "win32"]

# media play variables
media_to_play = ""
media_in_play = ""
start_sec = 0
end_sec = 0
stop_play_timer = None
completed_play_notice = threading.Event()
mplayer_stdout_msg_queue = Queue()
mplayer_start_parsing_notice = threading.Event()
# player controller
mplayerManager = None
mplayerEvt = threading.Event()
mplayerClear = False
wid_mplayer_container = 0
mplayer_stdout_msg_parser = None
mplay_readiness_state = 'init'


class MplayerMsgQueueParser(threading.Thread):

    def run(self):

        while True:
            mplayer_start_parsing_notice.wait()
            mplayer_start_parsing_notice.clear()
            start_time = time.time()
            media_length = 0
            # clear existing msg
            while True:
                try:
                    line = mplayer_stdout_msg_queue.get_nowait()
                except Queue_Empty:
                    break
            # work on the msg
            # if there is another job request, drop current one
            while not (completed_play_notice.is_set()
                       or mplayer_start_parsing_notice.is_set()):
                try:
                    line = mplayer_stdout_msg_queue.get(timeout=0.2)
                except Queue_Empty:
                    continue
                try:
                    line = decode_sp(line)
                except Exception:
                    continue
                if "EOF code" in line:
                    completed_play_notice.set()
                    logger.debug("Got std out eof: %s" % line)
                    break
                if not media_length:
                    length_block = re.search(r"ID_LENGTH=(\d+\.*\d*)", line)
                    if length_block:
                        media_length = length_block.group(1)
                        # logger.debug("got media_length %s" % media_length)
                        media_length = float(media_length)
                        if media_length < 1:
                            media_length = 1
                if media_length and time.time() - start_time > media_length + 3:
                    logger.debug("playing over time: %s" % media_length)
                    break


class MplayerMonitor(threading.Thread):

    def run(self):
        global mplayerEvt
        global mplayerClear, media_to_play, start_sec, media_in_play
        self.mplayer = None
        self.deadPlayers = []
        while 1:
            mplayerEvt.wait()
            mplayerEvt.clear()
            # clearing queue?
            if mplayerClear and self.mplayer:
                try:
                    self.mplayer.stdin.write(b"stop\n")
                    self.mplayer.stdin.flush()
                except:
                    # mplayer quit by user (likely video)
                    self.deadPlayers.append(self.mplayer)
                    self.mplayer = None
            # for our add-on only one file is allowed each run
            if media_to_play:
                # new job
                # logger.debug("play thread got new request: %s" % media_to_play)
                # ensure started
                if not self.mplayer:
                    try:
                        self.startProcess()
                    except OSError:
                        return
                # play target file
                if mplayerClear:
                    mplayerClear = False
                cmd = b'loadfile "%s"\n' % media_to_play.encode("utf8")
                if start_sec:
                    seek_cmd = b'seek %s 2\n' % str(start_sec).encode("utf8")
                completed_play_notice.clear()
                mplayer_start_parsing_notice.set()
                try:
                    self.mplayer.stdin.write(cmd)
                    if start_sec:
                        self.mplayer.stdin.write(seek_cmd)
                    self.mplayer.stdin.flush()
                except:
                    # mplayer has quit and needs restarting
                    logger.info("restart mplayer")
                    self.deadPlayers.append(self.mplayer)
                    self.mplayer = None
                    try:
                        self.startProcess()
                    except OSError:
                        return
                    self.mplayer.stdin.write(cmd)
                    if start_sec:
                        self.mplayer.stdin.write(seek_cmd)
                    self.mplayer.stdin.flush()
                logger.debug("mplay cmd: %s" % cmd)
                media_in_play = media_to_play
                media_to_play = ""
                # if we feed mplayer too fast it loses files
                # time.sleep(1)
            # wait() on finished processes. we don't want to block on the
            # wait, so we keep trying each time we're reactivated

            def clean(pl):
                if pl.poll() is not None:
                    pl.wait()
                    return False
                else:
                    return True
            self.deadPlayers = [pl for pl in self.deadPlayers if clean(pl)]

    def kill(self):
        if not self.mplayer:
            return
        try:
            self.mplayer.stdin.write(b"quit\n")
            self.mplayer.stdin.flush()
            self.deadPlayers.append(self.mplayer)
            completed_play_notice.set()
        except:
            pass
        self.mplayer = None

    def startProcess(self):
        try:
            global wid_mplayer_container
            if not wid_mplayer_container:
                return
            try:
                config = mw.addonManager.getConfig(__name__)
                volume = int(config["mplayer_startup_volume"])
            except Exception:
                volume = 50
            if volume < 0 or volume > 100:
                volume = 50
            cmd = mplayerCmd + ["-volume", str(volume), "-slave", "-idle"]
            #cmd = [cmd[0], "-fs", "-wid", str(wid_mplayer_container)] + cmd[1:]
            try:
                cmd += ["-fs", "-wid", str(wid_mplayer_container)]
                cmd, env = _packagedCmd(cmd)
                self.mplayer = subprocess.Popen(
                    cmd, startupinfo=si, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=env)
            except:
                cmd += ["-wid", str(wid_mplayer_container)]
                cmd, env = _packagedCmd(cmd)
                self.mplayer = subprocess.Popen(
                    cmd, startupinfo=si, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=env)
            logger.debug("start mplayer: %s" % cmd)

            def read_stdout_to_queue(mplayer):
                while True:
                    if not mplayer:
                        break
                    line = mplayer.stdout.readline()
                    try:
                        mplayer_stdout_msg_queue.put_nowait(line)
                        # logger.debug("stdout reader: %s" % repr(line))
                    except Exception:
                        pass
                    if not line:
                        break

            self.mplayer.stdout_reader = threading.Thread(target=read_stdout_to_queue,
                                                          args=(self.mplayer,),
                                                          daemon=True)
            self.mplayer.stdout_reader.start()

        except OSError:
            mplayerEvt.clear()
            global mplay_readiness_state, completed_play_notice
            if mplay_readiness_state == 'init':
                mplay_readiness_state = 'tried and failed'
            completed_play_notice.set()
            raise
            # raise Exception("Did you install mplayer?")

def queueMplayer(path, start_sec_p=0, end_sec_p=0):
    global media_to_play, start_sec, end_sec, stop_play_timer
    global completed_play_notice, mplayerEvt
    # logger.debug("queueMplayer in: %s" % path)
    ensureMplayerThreads()
    # logger.debug("queueMplayer after ensureMplayerThreads")
    if isWin and os.path.exists(path):
        # mplayer on windows doesn't like the encoding, so we create a
        # temporary file instead. oddly, foreign characters in the dirname
        # don't seem to matter.
        config = mw.addonManager.getConfig(__name__)
        if "my_mplayer_need_copying_file_to_temp" in config \
                and config["my_mplayer_need_copying_file_to_temp"]:
            dir = tmpdir()
            name = os.path.join(dir, "audio%s%s" % (
                random.randrange(0, 1000000), os.path.splitext(path)[1]))
            f = open(name, "wb")
            f.write(open(path, "rb").read())
            f.close()
            # it wants unix paths, too!
            path = name
        path = path.replace("\\", "/")
    media_to_play = path
    if isinstance(start_sec_p, int) and start_sec_p >= 0:
        start_sec = start_sec_p
    else:
        start_sec = 0
    if isinstance(end_sec_p, int) and end_sec_p > start_sec:
        end_sec = end_sec_p
        if stop_play_timer and stop_play_timer.is_alive():
            stop_play_timer.cancel()
        stop_play_timer = threading.Timer(end_sec - start_sec, stop_as_planned, kwargs={"media_path_to_stop": media_to_play})
        stop_play_timer.start()
    else:
        end_sec = 0
    completed_play_notice.clear()
    mplayerEvt.set()

def stop_as_planned(media_path_to_stop):
    global media_in_play
    if media_path_to_stop == media_in_play:
        clearMplayerPlaying()


def clearMplayerPlaying():
    global mplayerClear, media_to_play, start_sec, end_sec, media_in_play
    media_to_play = ""
    start_sec = 0
    end_sec = 0
    # this line stop the current play
    mplayerClear = True
    mplayerEvt.set()
    media_in_play = ""
    completed_play_notice.set()


def ensureMplayerThreads():
    global mplayerManager, mplayer_stdout_msg_parser
    if not mplayerManager:
        mplayerManager = MplayerMonitor()
        mplayerManager.daemon = True
        mplayerManager.start()
        # ensure the tmpdir() exit handler is registered first so it runs
        # after the mplayer exit
        tmpdir()
        # clean up mplayer on exit
        atexit.register(stopMplayer)
    if not mplayer_stdout_msg_parser:
        mplayer_stdout_msg_parser = MplayerMsgQueueParser()
        mplayer_stdout_msg_parser.daemon = True
        mplayer_stdout_msg_parser.start()


def stopMplayer(*args):
    if not mplayerManager:
        return
    mplayerManager.kill()
    if isWin:
        cleanupOldMplayerProcesses()


addHook("unloadProfile", stopMplayer)


# interface
##########################################################################
def setup(wid=0):
    global wid_mplayer_container
    if wid_mplayer_container != wid:
        stopMplayer()
        logger.debug("Using a new window ID for video playing %s" % wid)
    wid_mplayer_container = wid


def play(path, start_sec=0, end_sec=0):
    logger.info("mplayer interface in: %s" % path)
    global mplay_readiness_state
    if mplay_readiness_state == 'failed and notified':
        completed_play_notice.set()
        return completed_play_notice
    elif mplay_readiness_state == 'tried and failed':
        QMessageBox.critical(
            None, 'Mplayer Missing!',
            'Cannot open mplayer. \n'
            'Have you installed mplayer?\n'
            '(On Windows, you can copy mplayer.exe '
            'from 2.1.26- anki installation)')
        completed_play_notice.set()
        mplay_readiness_state = 'failed and notified'
        return completed_play_notice
    queueMplayer(path, start_sec, end_sec)
    return completed_play_notice


def stop():
    clearMplayerPlaying()
