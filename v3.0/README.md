# RTSP/RTP Video Streaming

This project is a Python socket programming assignment for a simple MJPEG video streaming system.

The client and server use RTSP over TCP for playback control and RTP over UDP for video frame delivery.

## Features

- RTSP control flow:
  - `DESCRIBE`
  - `SETUP`
  - `PLAY`
  - `PAUSE`
  - `TEARDOWN`
- RTP packetization for MJPEG video frames
- Tkinter client GUI for video playback
- Media-player style controls:
  - `Play`
  - `Pause`
  - `Stop`
- Automatic `DESCRIBE -> SETUP -> PLAY` when `Play` is pressed for the first time
- `Stop` sends `TEARDOWN` to end the RTSP session
- Session statistics shown after `Stop`:
  - received packets
  - expected packets
  - lost packets
  - packet loss rate
  - video data rate
- Optional exercise support:
  - RTP session statistics
  - Play/Pause/Stop UI with automatic SETUP
  - RTSP `DESCRIBE` method

## Requirements

- Python 2.7
- Tkinter
- Pillow

Install Pillow:

```bash
pip install Pillow
```

## Usage

Open two terminals and run both commands from the `v3.0` directory.

### 1. Start the Server

```bash
python Server.py 8000
```

`8000` is the RTSP TCP port. You may replace it with another available port greater than 1024.

### 2. Start the Client

```bash
python ClientLauncher.py 127.0.0.1 8000 8001 movie.Mjpeg
```

Arguments:

```text
server_host server_port rtp_port video_file
```

Example meaning:

- `127.0.0.1`: server address
- `8000`: server RTSP port
- `8001`: client RTP/UDP receiving port
- `movie.Mjpeg`: video file streamed by the server

## Controls

- `Play`
  - On the first click, the client automatically sends `DESCRIBE`, `SETUP`, then `PLAY`.
  - After setup is complete, later clicks send `PLAY`.

- `Pause`
  - Sends `PAUSE`.
  - The server pauses RTP packet transmission.

- `Stop`
  - Sends `TEARDOWN`.
  - The server ends the session.
  - The client shows session statistics.

## Assignment Coverage

Required parts:

- Client RTSP requests:
  - `SETUP`
  - `PLAY`
  - `PAUSE`
  - `TEARDOWN`
- Client RTSP states:
  - `INIT`
  - `READY`
  - `PLAYING`
- RTP/UDP receiving socket with a 0.5 second timeout
- Server-side RTP packetization in `RtpPacket.encode()`

Optional exercises:

- Packet loss rate and video data rate calculation
- Media-player style UI without a visible SETUP button
- RTSP `DESCRIBE` request and SDP-style response