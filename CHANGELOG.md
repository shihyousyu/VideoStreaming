# Changelog

## [v2.4] - 2026-05-21
### Added
* Custom RTSP `LIST` method for browsing server-side files:
    * Server scans its working directory for `.Mjpeg` files and returns them in a `Files` field
    * Client shows the list in a dialog so the user picks a file that exists on the server

### Changed
* Setup now browses the server's files instead of the client's local filesystem. This enables cross-machine streaming -- the previous local file picker only worked when client and server shared a filesystem (same machine).

## [v2.3] - 2026-05-18
### Changed
* GUI layout reorganized

## [v2.2] - 2026-05-16
### Added
* File picker on Setup.
    * `tkFileDialog.askopenfilename` filtered to `*.Mjpeg`/`*.mjpeg`.
* Connection bar.
    * Entry fields for Server address, RTSP port, RTP port.
    * Connect/Disconnect toggle button.
* 4 new speed levels: 4.0x, 8.0x, 16.0x, 32.0x.

### Changed
* Teardown resets all UI state (frame, progress, time, speed).
* Clicking Setup after Teardown opens a new session.
* All CLI arguement are set in GUI.

### Fixed
* Server no longer crashes on TEARDOWN when PLAY hasn't been called yet.
    * `clientInfo['event']` and `clientInfo['rtpSocket']` are now checked before access — both are created on PLAY but TEARDOWN can arrive without PLAY.

## [v2.1.2] - 2026-05-15
### Changed
* Shrank from ~80 lines of branching to ~15 lines.
    * Add look-up tables `METHOD`, `VALID_STATE` and `BUTTON` to refactor functions `sendRtspRequest` and `createWidgets`.
* `Teardown` button no longer closes GUI window. `X` button is the only way to quit but still sends TEARDOWN request before closing.

## [v2.1.1] - 2026-05-14
### Fixed
* Complete missing return in `ServerWorker.processRtspRequest`'s SETUP IOError handler.
    * Avoid crashing during SETUP with a non-existing file.

## [v2.1] - 2026-05-14
### Added
* Progress bar and time display (MM:SS / MM:SS):
    * Server adds `Total-Frames` field in SETUP reply
    * Server writes the current movie frame number into each RTP packet's timestamp field

## [v2.0.1] - 2026-05-13
### Fixed
* Instead of saving `cache-{session-id}.jpg` to disk, using `io.BytesIO`. No more leftover cache files on the client-side.
* Display now updates on Forward/Backward while paused. The client no longer stops receiving RTP packets while paused.

## [v2.0] - 2026-05-13
### Added
* Fast / Slow: Speed control (0.5x, 1.0x, 1.5x, 2.0x)
* Forward / Backward: Jump over +/-5 secs (100 frames)

## [v1.0] - 2026-05-12
* Complete example code