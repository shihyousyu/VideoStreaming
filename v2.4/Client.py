from Tkinter import *
import tkMessageBox
from PIL import Image, ImageTk
import socket, threading, io
import ttk

from RtpPacket import RtpPacket

class Client:

	# Connection state
	INIT 	= 0
	READY 	= 1
	PLAYING = 2
	state 	= INIT
	
	# Action code
	SETUP 	 = 0
	PLAY 	 = 1
	PAUSE 	 = 2
	TEARDOWN = 3
	FAST 	 = 4
	SLOW 	 = 5
	FORWARD  = 6
	BACKWARD = 7
	LIST 	 = 8

	# Action code -> RTSP method
	METHOD = ["SETUP", "PLAY", "PAUSE", "TEARDOWN", "FAST", "SLOW", "FORWARD", "BACKWARD", "LIST"]

	# VALID_STATE[action] -> allowed_states
	VALID_STATE = [
		(INIT,),
		(READY,),
		(PLAYING,),
		(READY, PLAYING),
		(READY, PLAYING),
		(READY, PLAYING),
		(READY, PLAYING), 
		(READY, PLAYING),
		(INIT,)
	]

	SPEED = [0.5, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0, 32.0]

	FPS = 20

	# Default connection params (pre-filled into Entry fields at startup)
	DEFAULT_SERVER_ADDR = "127.0.0.1"
	DEFAULT_RTSP_PORT 	= "25000"
	DEFAULT_RTP_PORT 	= "25001"

	# Playback controls - single centered row, in the order shown
	PLAYBACK_BUTTONS = [
		{"name": "Backward", "command": "backwardMovie"},
		{"name": "Slow",     "command": "slowMovie"},
		{"name": "Play",     "command": "playMovie"},
		{"name": "Pause",    "command": "pauseMovie"},
		{"name": "Fast",     "command": "fastMovie"},
		{"name": "Forward",  "command": "forwardMovie"},
	]

	# Session controls - bottom-left corner
	SESSION_BUTTONS = [
		{"name": "Setup",    "command": "setupMovie"},
		{"name": "Teardown", "command": "teardownMovie"},
	]

	def __init__(self, master):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)

		# Session / connection state
		self.connected     = False
		self.listening     = False
		self.serverAddr    = None
		self.serverPort    = None
		self.rtpPort       = None
		self.fileName      = ""
		self.serverFiles   = []
		self.speedIdx      = 1
		self.rtspSeq       = 0
		self.sessionId     = 0
		self.requestSent   = -1
		self.teardownAcked = 0
		self.frameNbr      = 0
		self.totalFrames   = 0

		self.createWidgets()

	def createWidgets(self):
		"""Build GUI."""
		# Row 0: connection bar
		self.connection = Frame(self.master)
		self.connection.grid(row=0, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)

		Label(self.connection, text="Server:").grid(row=0, column=0, padx=2)
		self.serverAddrEntry = Entry(self.connection, width=15)
		self.serverAddrEntry.grid(row=0, column=1, padx=2)
		self.serverAddrEntry.insert(0, self.DEFAULT_SERVER_ADDR)

		Label(self.connection, text="RTSP:").grid(row=0, column=2, padx=2)
		self.serverPortEntry = Entry(self.connection, width=6)
		self.serverPortEntry.grid(row=0, column=3, padx=2)
		self.serverPortEntry.insert(0, self.DEFAULT_RTSP_PORT)

		Label(self.connection, text="RTP:").grid(row=0, column=4, padx=2)
		self.rtpPortEntry = Entry(self.connection, width=6)
		self.rtpPortEntry.grid(row=0, column=5, padx=2)
		self.rtpPortEntry.insert(0, self.DEFAULT_RTP_PORT)

		self.connectBtn = self._makeButton(
			self.connection,
			{"name": "Connect", "command": "connectClient"},
		)
		self.connectBtn.grid(row=0, column=6, padx=(8, 2))

		# Row 1: movie display
		self.label = Label(self.master, height=19)
		self.label.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

		# Row 2: playback controls (centered)
		playback_frame = Frame(self.master)
		playback_frame.grid(row=2, column=0, columnspan=4, pady=(8, 4))

		for col, spec in enumerate(self.PLAYBACK_BUTTONS):
			btn = self._makeButton(playback_frame, spec)
			btn.grid(row=0, column=col, padx=2, pady=2)

		# Row 3: time | progress | speed
		progress_row = Frame(self.master)
		progress_row.grid(row=3, column=0, columnspan=4, sticky=W+E, padx=8, pady=4)
		progress_row.columnconfigure(1, weight=1)

		self.time = Label(progress_row, text="00:00 / 00:00")
		self.time.grid(row=0, column=0, padx=(0, 8), sticky=W)

		self.progress = ttk.Progressbar(progress_row, orient=HORIZONTAL, mode='determinate')
		self.progress.grid(row=0, column=1, sticky=W+E)

		self.speed = Label(progress_row, text="Speed: 1.0x")
		self.speed.grid(row=0, column=2, padx=(8, 0), sticky=E)

		# Row 4: session controls (bottom-left)
		session_frame = Frame(self.master)
		session_frame.grid(row=4, column=0, columnspan=4, sticky=W, padx=8, pady=(4, 8))

		for col, spec in enumerate(self.SESSION_BUTTONS):
			btn = self._makeButton(session_frame, spec)
			btn.grid(row=0, column=col, padx=(0, 4))

	def _makeButton(self, parent, spec):
		"""Create a default-style Tk button."""
		return Button(
			parent,
			text=spec["name"],
			command=getattr(self, spec["command"]),
			width=12,
			padx=3,
			pady=3,
		)

	def connectClient(self):
		"""Connect/Disconnect button handler."""
		if self.connected:
			# Disconnect: tear down active session first if any
			if self.state != self.INIT:
				self.sendRtspRequest(self.TEARDOWN)
			self.connected = False
			self.resetUI()
			self.setEntryEnabled(True)
			self.connectBtn["text"] = "Connect"
		else:
			# Connect: read params from Entry fields and try to open the socket
			try:
				self.serverAddr = self.serverAddrEntry.get().strip()
				self.serverPort = int(self.serverPortEntry.get().strip())
				self.rtpPort	= int(self.rtpPortEntry.get().strip())
			except ValueError:
				tkMessageBox.showwarning('Invalid Input', 'Ports must be integers.')
				return

			self.connectToServer()
			if self.connected:
				self.setEntryEnabled(False)
				self.connectBtn["text"] = "Disconnect"

	def setEntryEnabled(self, enabled):
		"""Enable/disable the connection-parameter Entry fields."""
		state = "normal" if enabled else "disabled"
		self.serverAddrEntry["state"] = state
		self.serverPortEntry["state"] = state
		self.rtpPortEntry["state"]    = state

	def setupMovie(self):
		"""Setup button handler - ask the server for its file list, then pick one."""
		if not self.connected:
			tkMessageBox.showwarning('Not Connected', 'Click Connect first.')
			return
		if self.state != self.INIT:
			return

		# Re-Setup after Teardown: reset session vars and reconnect RTSP socket
		if self.teardownAcked == 1:
			self.sessionId     = 0
			self.rtspSeq       = 0
			self.teardownAcked = 0
			self.connectToServer()

		# Ask the server which files it has; the picker dialog opens on reply
		self.sendRtspRequest(self.LIST)

	def showServerFileDialog(self):
		"""Show the server's available files in a listbox (runs on the main thread)."""
		win = Toplevel(self.master)
		win.title("Server videos")
		win.transient(self.master)

		if not self.serverFiles:
			Label(win, text="No .Mjpeg files found on the server.").pack(padx=20, pady=20)
			Button(win, text="Close", command=win.destroy, width=10).pack(pady=(0, 12))
			return

		Label(win, text="Choose a video on the server:").pack(padx=12, pady=(12, 4), anchor=W)

		listbox = Listbox(win, width=40, height=min(10, len(self.serverFiles)))
		listbox.pack(padx=12, pady=4, fill=BOTH, expand=True)
		for f in self.serverFiles:
			listbox.insert(END, f)
		listbox.selection_set(0)

		def choose():
			sel = listbox.curselection()
			if sel:
				chosen = listbox.get(sel[0])
				win.destroy()
				self.requestSetup(chosen)

		listbox.bind("<Double-Button-1>", lambda e: choose())

		btn_row = Frame(win)
		btn_row.pack(pady=(4, 12))
		Button(btn_row, text="Open",   command=choose,      width=10).grid(row=0, column=0, padx=4)
		Button(btn_row, text="Cancel", command=win.destroy, width=10).grid(row=0, column=1, padx=4)

	def requestSetup(self, filename):
		"""Send the SETUP request for the chosen server-side file."""
		self.fileName = filename
		self.sendRtspRequest(self.SETUP)

	def teardownMovie(self):
		"""Teardown button handler - end session and reset UI (window stays open)."""
		if self.state == self.INIT:
			return
		self.sendRtspRequest(self.TEARDOWN)
		self.resetUI()

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			self.sendRtspRequest(self.PLAY)

	def fastMovie(self):
		"""Fast button handler."""
		if self.state in (self.READY, self.PLAYING):
			if self.speedIdx < len(self.SPEED) - 1:
				self.speedIdx += 1
			else:
				self.speedIdx = 1

			self.updateSpeed()
			self.sendRtspRequest(self.FAST)

	def slowMovie(self):
		"""Slow button handler."""
		if self.state in (self.READY, self.PLAYING):
			if self.speedIdx > 0:
				self.speedIdx -= 1
			else:
				self.speedIdx = 1

			self.updateSpeed()
			self.sendRtspRequest(self.SLOW)

	def forwardMovie(self):
		"""Forward button handler."""
		if self.state in (self.READY, self.PLAYING):
			self.sendRtspRequest(self.FORWARD)

	def backwardMovie(self):
		"""Backward button handler."""
		if self.state in (self.READY, self.PLAYING):
			self.sendRtspRequest(self.BACKWARD)

	def updateSpeed(self):
		"""Update speed label."""
		self.speed["text"] = "Speed: %sx" % self.SPEED[self.speedIdx]

	def resetUI(self):
		"""Clear visual state so the GUI looks idle after Teardown/Disconnect."""
		self.label.configure(image='', height=19)
		self.label.image = None
		self.progress["value"] = 0
		self.time["text"] = "00:00 / 00:00"
		self.frameNbr    = 0
		self.totalFrames = 0
		self.speedIdx    = 1
		self.updateSpeed()

	def listenRtp(self):
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)

					currFrameNbr = rtpPacket.seqNum()
					print("Current Seq Num: " + str(currFrameNbr))

					if currFrameNbr > self.frameNbr:
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
						self.updateProgress(rtpPacket.timestamp())
			except:
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break

	def writeFrame(self, data):
		"""Wrap the received frame in an in-memory buffer."""
		return io.BytesIO(data)

	def formatTime(self, seconds):
		"""Format seconds as MM:SS."""
		seconds = int(seconds)
		return "%02d:%02d" % (seconds // 60, seconds % 60)

	def updateProgress(self, movieFrames):
		"""Update progress bar and time label given the current movie frame."""
		if self.totalFrames <= 0:
			return
		pos = max(0, min(movieFrames, self.totalFrames))
		self.progress["value"] = pos
		curr  = pos              / float(self.FPS)
		total = self.totalFrames / float(self.FPS)
		self.time["text"] = "%s / %s" % (self.formatTime(curr), self.formatTime(total))

	def updateMovie(self, imageFile):
		"""Update the image as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image=photo, height=288)
		self.label.image = photo

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
			self.connected = True
		except:
			tkMessageBox.showwarning('Connection Failed',
									"Connection to '%s' failed." % self.serverAddr)
			self.connected = False

	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		if not self.connected:
			return
		if self.state not in self.VALID_STATE[requestCode]:
			return

		self.rtspSeq += 1

		if requestCode == self.LIST:
			# LIST happens before a session exists; start the reply listener once
			if not self.listening:
				self.listening = True
				threading.Thread(target=self.recvRtspReply).start()
			header = None
		elif requestCode == self.SETUP:
			header = "Transport: RTP/UDP; client_port= " + str(self.rtpPort)
		else:
			header = "Session: " + str(self.sessionId)

		if header is None:
			# Server-wide request (no specific resource, no session)
			request = "%s * RTSP/1.0\nCSeq: %d" % (self.METHOD[requestCode], self.rtspSeq)
		else:
			request = "%s %s RTSP/1.0\nCSeq: %d\n%s" % (
				self.METHOD[requestCode], self.fileName, self.rtspSeq, header
			)
		self.requestSent = requestCode

		self.rtspSocket.send(request.encode())
		print('\nData sent:\n' + request)

	def recvRtspReply(self):
		"""Receive RTSP reply from the server. Lives from the first LIST until TEARDOWN."""
		while True:
			try:
				reply = self.rtspSocket.recv(1024)
			except:
				break

			if reply:
				self.parseRtspReply(reply.decode("utf-8"))

			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break

		self.listening = False

	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])

		if seqNum != self.rtspSeq:
			return

		# LIST reply has no Session line; handle it before session parsing
		if self.requestSent == self.LIST:
			if int(lines[0].split(' ')[1]) == 200:
				files = []
				for line in lines:
					if str(line).startswith('Files:'):
						raw = str(line).split(':', 1)[1].strip()
						files = [f for f in raw.split(',') if f]
						break
				self.serverFiles = files
				# Marshal the dialog back onto the Tk main thread
				self.master.after(0, self.showServerFileDialog)
			return

		session = int(lines[2].split(' ')[1])
		if self.sessionId == 0:
			self.sessionId = session

		if self.sessionId == session:
			if int(lines[0].split(' ')[1]) == 200:
				if self.requestSent == self.SETUP:
					self.state = self.READY

					for line in lines:
						if str(line).startswith('Total-Frames: '):
							try:
								self.totalFrames = int(str(line).split(':')[1].strip())
								self.progress["maximum"] = self.totalFrames
								self.updateProgress(0)
							except (ValueError, IndexError):
								pass
							break

					self.openRtpPort()

				elif self.requestSent == self.PLAY:
					self.state = self.PLAYING

				elif self.requestSent == self.PAUSE:
					self.state = self.READY

				elif self.requestSent == self.TEARDOWN:
					self.state = self.INIT
					self.teardownAcked = 1

	def openRtpPort(self):
		"""Open RTP socket bound to a specified port."""
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtpSocket.settimeout(0.5)

		try:
			self.rtpSocket.bind(("", self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind',
									'Unable to bind PORT=%d' % self.rtpPort)
			return

		threading.Thread(target=self.listenRtp).start()

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			if self.connected and self.state != self.INIT:
				self.sendRtspRequest(self.TEARDOWN)
			self.master.destroy()
		else:
			self.playMovie()