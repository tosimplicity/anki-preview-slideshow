# anki-preview-slideshow

**Make Anki preview window as slideshow. For each card, it also introduce a media window to show external media files(not stored in Anki DB) like mp4, mp3, jpg, etc. External media window can be disabled, of course.**


![](screenshots/preview_in_slideshow_mode.png)
![](screenshots/slideshow_with_external_window.png)

## Quick Start Guide:
0. Installation: https://ankiweb.net/shared/info/90397199
1. Click "Browse" -> on Browser window, select target deck or filter out desired cards
2. Click "Preview" to open preview slideshow window
3. Click "Slideshow on/off" to check the box and start slideshow

* If mplayer is not availabe in your anki, you will need to install it if you'd like to play video in external window.

## Instructions:

1. Check/Uncheck "Slideshow On/Off" to start/stop slideshow
2. Check/Uncheck "Random Seq" to activate/disable random sequence
3. Click "||" button to pause slideshow
4. Click "|>" button to continue slideshow or go to next slide
5. Use tag like "slideshow_Xs" to indicate showing answer for X seconds
   (no time tag for question)
   for example, "slideshow_17s" for 17 seconds
6. Use tag like "slideshow_audio_replays_X" to indicate replay audio X times before going to next slide
   (no audio replay tag for question)
   for example, "slideshow_audio_replays_17" for replay 17 times
7. Use tag "slideshow_aisq" to indicate question slide is same with answer slide and answer slide should be skipped.
8. To show external media like mp4, jpg, gif.
   a. Create a field in exact name "Slideshow_External_Media"
   b. Put the file path for the external media file there like "D:/somefolder/myvideo.mp4"
   c. Root forder can also be set in settings. Like setting it to "D:/somefolder"
      then "Slideshow_External_Media" field can work in relative path like "myvideo.mp4", "sometype/blabla.png"
   d. With root folder set, if you want to use absolute path accassion occasionally,
      put "$$" before the path, like "$$D:/somefolder/myvideo.mp4"
9. A trick: to align buttons in preview window left, open preview window, resize it to a very small one, reopen it
10. Hover over buttons to see tooltips
11. Right click on the toolbox in preview window, or the external media window, to access functions.

## Source Code

1. Source code can be found on https://github.com/tosimplicity/anki-preview-slideshow
2. This add-on is licensed under GPL v3, or higher

## Version History

Version 0.7
- activate Relate to My Doc plugin if available

Version 0.6
- replays audio according to tag

Version 0.5
- adapt to anki version 2.1.41+

Version 0.4
- use set interval when mplayer is not available.

Version 0.3
- fix bug in logging for Anki version between 2.1.20 and 2.1.23

Version 0.2
- Make it compatible with Anki 2.1.24+
- add absolute path marker support while root folder set

Version 0.1
- Initial release
