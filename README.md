# Video Streaming Client / Server

An RTSP/RTP-based MJPEG video streaming application with a Tkinter GUI client and a Python streaming server. Built as a Computer Networks course final project.

## Features

- **Playback controls**: Play, Pause, Forward (+5s), Backward (-5s)
- **Variable speed**: 8 levels from 0.5x to 32x via Slow/Fast buttons
- **Progress bar with time display** (MM:SS / MM:SS), driven by the server-side movie frame number sent via the RTP timestamp field
- **In-GUI file selection** via a file picker dialog (`.Mjpeg` files)
- **Configurable connection** with server address, RTSP port, and RTP port input fields
- **Session reset on Teardown** -- play multiple videos in one session without restarting the app
- **Connect / Disconnect** toggle to manage the TCP/RTSP connection

## Requirements

- Python 2.7
- [Pillow (PIL)](https://pillow.readthedocs.io/): `pip install Pillow`
- Tkinter (bundled with Python)

## How to Run

The application has two parts: the server and the client. Run them in separate terminals.

### Server

```bash
python Server.py <port>
```

Example:

```bash
python Server.py 25000
```

The server listens on the given port for RTSP control messages and streams RTP packets back over UDP.

### Client

```bash
python ClientLauncher.py
```

No command-line arguments needed; all connection settings are configured in the GUI.

## GUI Usage

1. **Connect**: Enter the server's IP/hostname, the RTSP port (must match the server's port), and the RTP port (any unused UDP port on the client machine). Click **Connect**.
2. **Setup**: Click **Setup** and choose a `.Mjpeg` file. The session starts and the first frame should appear.
3. **Play / Pause**: Standard playback controls.
4. **Backward / Forward**: Jump back / forward by 5 seconds (100 frames).
5. **Slow / Fast**: Cycle through speed levels: 0.5x, 1.0x, 1.5x, 2.0x, 4.0x, 8.0x, 16.0x, 32.0x (and back).
6. **Teardown**: End the current session. The GUI stays open; you can click **Setup** again to play another video.
7. **Disconnect**: Close the RTSP connection (sends Teardown first if a session is active).
8. **X (close window)**: Quit the application (sends Teardown if still in a session).

## Network Setup

The default values (`127.0.0.1` / `25000` / `25001`) target a local-machine setup where the server and client run on the same computer.

For remote streaming, replace the server address with the server's reachable IP. Tailscale IPs (`100.x.x.x`) work transparently -- no protocol changes needed. Just ensure both machines are on the same Tailnet.

## Version History

See [CHANGELOG.md](./CHANGELOG.md) for detailed per-version changes.

## Architecture

- **RTSP** (TCP) carries control messages: `SETUP`, `PLAY`, `PAUSE`, `TEARDOWN`, plus custom extensions `FAST`, `SLOW`, `FORWARD`, `BACKWARD`.
- **RTP** (UDP) carries the MJPEG video payload. Each packet's RTP timestamp field is used to carry the source movie frame number (instead of wall-clock time), enabling the client's progress bar to track the true playback position regardless of network reordering or speed changes.
- The client uses a single long-lived RTP listener thread that runs from SETUP until TEARDOWN, so seek frames sent during PAUSE can still be received.