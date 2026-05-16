from Tkinter import *
import tkMessageBox
import tkFileDialog
from PIL import Image, ImageTk
import socket, threading, io, os
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

	# Action code --> RTSP method
	METHOD = ["SETUP", "PLAY", "PAUSE", "TEARDOWN", "FAST", "SLOW", "FORWARD", "BACKWARD"]

	# VALID_STATE[action] -> allowed_states
	VALID_STATE = [
		(INIT,),
		(READY,),
		(PLAYING,),
		(READY, PLAYING),
		(READY, PLAYING),
		(READY, PLAYING),
		(READY, PLAYING), 
		(READY, PLAYING)
	]

	SPEED = [0.5, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0, 32.0]

	FPS = 20

	# Buttons
	BUTTON = [
		{
			"name"		: "Setup",
			"command"	: "setupMovie",
			"row"		: 2,
			"col"		: 0
		},
		{
			"name"		: "Play",
			"command"	: "playMovie",
			"row"		: 2,
			"col"		: 1
		},
		{
			"name"		: "Pause",
			"command"	: "pauseMovie",
			"row"		: 2,
			"col"		: 2
		},
		{
			"name"		: "Teardown",
			"command"	: "teardownMovie",
			"row"		: 2,
			"col"		: 3
		},
		{
			"name"		: "Backward",
			"command"	: "backwardMovie",
			"row"		: 3,
			"col"		: 0
		},
		{
			"name"		: "Slow",
			"command"	: "slowMovie",
			"row"		: 3,
			"col"		: 1
		},
		{
			"name"		: "Fast",
			"command"	: "fastMovie",
			"row"		: 3,
			"col"		: 2
		},
		{
			"name"		: "Forward",
			"command"	: "forwardMovie",
			"row"		: 3,
			"col"		: 3
		}
	]

	DEFAULT_SERVER_ADDR = "127.0.0.1"
	DEFAULT_RTSP_PORT 	= "25000"
	DEFAULT_RTP_PORT 	= "25001"

	# Initiation..
	def __init__(self, master):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)

		self.connected 		= False
		self.serverAddr 	= None
		self.serverPort 	= None
		self.rtpPort 		= None
		self.fileName 		= ""
		self.speedIdx 		= 1
		self.rtspSeq 		= 0
		self.sessionId 		= 0
		self.requestSent 	= -1
		self.teardownAcked 	= 0
		self.frameNbr 		= 0
		self.totalFrames 	= 0

		self.createWidgets()

	def createWidgets(self):
		"""Build GUI."""
		# Create Connection bar
		self.connection = Frame(self.master)
		self.connection.grid(row=0, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)

		Label(self.connection, text="Server: ").grid(row=0, column=0, padx=2)
		self.serverAddrEntry = Entry(self.connection, width=15)
		self.serverAddrEntry.grid(row=0, column=1, padx=2)
		self.serverAddrEntry.insert(0, self.DEFAULT_SERVER_ADDR)

		Label(self.connection, text="RTSP: ").grid(row=0, column=2, padx=2)
		self.serverPortEntry = Entry(self.connection, width=6)
		self.serverPortEntry.grid(row=0, column=3, padx=2)
		self.serverPortEntry.insert(0, self.DEFAULT_RTSP_PORT)

		Label(self.connection, text="RTP: ").grid(row=0, column=4, padx=2)
		self.rtpPortEntry = Entry(self.connection, width=6)
		self.rtpPortEntry.grid(row=0, column=5, padx=2)
		self.rtpPortEntry.insert(0, self.DEFAULT_RTP_PORT)

		self.connectBtn = Button(self.connection, text="Connect", command=self.connectClient, width=12)
		self.connectBtn.grid(row=0, column=6, padx=5)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

		# Create a label to display the speed
		self.speed = Label(self.master, text="Speed: 1.0x")
		self.speed.grid(row=4, column=0, columnspan=4, pady=5)

		# Create Progress Bar
		self.progress = ttk.Progressbar(self.master, orient=HORIZONTAL, mode='determinate', length=500)
		self.progress.grid(row=5, column=0, columnspan=4, padx=5, pady = 2, sticky=W+E)

		# Create Time label
		self.time = Label(self.master, text="00:00/00:00")
		self.time.grid(row=6, column=0, columnspan=4, pady=2)

		for i in self.BUTTON:
			btn = Button(self.master, width=20, padx=3, pady=3)
			btn["text"] = i["name"]
			btn["command"] = getattr(self, i["command"])
			btn.grid(row=i["row"], column=i["col"], padx=2, pady=2)

	def connectClient(self):
		"""Connect / disconnect button handler"""
		if self.connected:
			if self.state != self.INIT:
				self.sendRtspRequest(self.TEARDOWN)
			self.connected = False
			self.resetUI()
			self.setEntryEnabled(True)
			self.connectBtn["text"] = "Connect"

		else:
			try:
				self.serverAddr = self.serverAddrEntry.get().strip()
				self.serverPort = int(self.serverPortEntry.get().strip())
				self.rtpPort	= int(self.rtpPortEntry.get().strip())
			except ValueError:
				tkMessageBox.showwarning('Invalid input', 'Ports must be integers')
				return

			self.connectToServer()
			if self.connected:
				self.setEntryEnabled(False)
				self.connectBtn["text"] = "Disconnect"

	def setEntryEnabled(self, Enabled):
		state = "normal" if Enabled else "disabled"
		self.serverAddrEntry["state"] = state
		self.serverPortEntry["state"] = state
		self.rtpPortEntry["state"] = state

	def setupMovie(self):
		"""Setup button handler."""
		if not self.connected:
			tkMessageBox.showwarning("Not connected", "Click connect first")
			return
		if self.state != self.INIT:
			return
		
		filename = tkFileDialog.askopenfilename(
			title = "choose video",
			initialdir = ".",
			filetypes = [("MJPEG videos", "*.Mjpeg *.mjpeg")]
		)
		if not filename:
			return
		
		self.fileName = os.path.basename(filename)

		if self.teardownAcked == 1:
			self.sessionId = 0
			self.rtspSeq = 0
			self.teardownAcked = 0
			self.connectToServer()

		self.sendRtspRequest(self.SETUP)
	
	def teardownMovie(self):
		"""Teardown button handler."""
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
		"""Update speed"""
		self.speed["text"] = "Speed: %sx" % self.SPEED[self.speedIdx]

	def resetUI(self):
		self.label.configure(image="", height=19)
		self.label.image 		= None
		self.progress["value"] 	= 0
		self.time["text"] 		= "00:00 / 00:00"
		self.frameNbr 			= 0
		self.totalFrames 		= 0
		self.speedIdx 			= 1
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

					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
						self.updateProgress(rtpPacket.timestamp())
			except:
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Wrap the received frame in buffer"""
		return io.BytesIO(data)
	
	def formatTime(self, seconds):
		seconds = int(seconds)
		return "%02d:%02d" % (seconds // 60, seconds % 60)
	
	def updateProgress(self, movieFrames):
		if self.totalFrames <= 0:
			return

		pos = max(0, min(movieFrames, self.totalFrames))
		self.progress["value"] = pos
		curr = pos / float(self.FPS)
		total = self.totalFrames / float(self.FPS)
		self.time["text"] = "%s / %s" % (self.formatTime(curr), self.formatTime(total))
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
			self.connected = True
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
			self.connected = False
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		if self.state not in self.VALID_STATE[requestCode]:
			return
		
		self.rtspSeq += 1

		if requestCode == self.SETUP:
			threading.Thread(target=self.recvRtspReply).start()
			header = "Transport: RTP/UDP; client_port= " + str(self.rtpPort)
		else: header = "Session: " + str(self.sessionId)

		request = "%s %s RTSP/1.0\nCSeq: %d\n%s" % (self.METHOD[requestCode], self.fileName, self.rtspSeq, header)
		self.requestSent = requestCode
		
		# Send the RTSP request using rtspSocket.
		self.rtspSocket.send(request.encode())
		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply:
				
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						# Update RTSP state.
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
						
						# Open RTP port.
						self.openRtpPort()
						
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING

					elif self.requestSent == self.PAUSE:
						self.state = self.READY

					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.rtpSocket.bind(("", self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)
			return

		threading.Thread(target=self.listenRtp).start()

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			if self.state != self.INIT:
				self.sendRtspRequest(self.TEARDOWN)
			self.master.destroy()
		else: # When the user presses cancel, resume playing.
			self.playMovie()