from Tkinter import *
import tkMessageBox
from PIL import Image, ImageTk
import socket, threading, io
import ttk

from RtpPacket import RtpPacket

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	FAST = 4
	SLOW = 5
	FORWARD = 6
	BACKWARD = 7
	
	SPEED = [0.5, 1.0, 1.5, 2.0]

	# New
	FPS = 20
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.speedIdx = 1
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		# New
		self.totalFrames = 0

	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create Backward button
		self.backward = Button(self.master, width=20, padx=3, pady=3)
		self.backward["text"] = "Backward"
		self.backward["command"] = self.backwardMovie
		self.backward.grid(row=2, column=0, padx=2, pady=2)
		
		# Create Slow button		
		self.slow = Button(self.master, width=20, padx=3, pady=3)
		self.slow["text"] = "Slow"
		self.slow["command"] = self.slowMovie
		self.slow.grid(row=2, column=1, padx=2, pady=2)
		
		# Create Fast button			
		self.fast = Button(self.master, width=20, padx=3, pady=3)
		self.fast["text"] = "Fast"
		self.fast["command"] = self.fastMovie
		self.fast.grid(row=2, column=2, padx=2, pady=2)
		
		# Create Forward button
		self.forward = Button(self.master, width=20, padx=3, pady=3)
		self.forward["text"] = "Forward"
		self.forward["command"] =  self.forwardMovie
		self.forward.grid(row=2, column=3, padx=2, pady=2)

		# Create a label to display the speed
		self.speed = Label(self.master, text="Speed: 1.0x")
		self.speed.grid(row=3, column=0, columnspan=4, pady=5)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

# ----------------------------- NEW ITEMS -----------------------------

		# Create Progress Bar
		self.progress = ttk.Progressbar(self.master, orient=HORIZONTAL, mode='determinate', length=500)
		self.progress.grid(row=4, column=0, columnspan=4, padx=5, pady = 2, sticky=W+E)

		# Create Time label
		self.time = Label(self.master, text="00:00/00:00")
		self.time.grid(row=5, column=0, columnspan=4, pady=2)

# ---------------------------------------------------------------------

	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window

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
						# New
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
	
# ----------------------------- NEW ITEMS -----------------------------

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

# ---------------------------------------------------------------------
	
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
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			
			# Update RTSP sequence number.
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			request = "SETUP " + self.fileName + " RTSP/1.0\n" + \
						"CSeq: " + str(self.rtspSeq) + "\n" + \
						"Transport: RTP/UDP; client_port= " + str(self.rtpPort)
			
			# Keep track of the sent request.
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			request = "PLAY " + self.fileName + " RTSP/1.0\n" + \
						"CSeq: " + str(self.rtspSeq) + "\n" + \
						"Session: " + str(self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.PLAY
		
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			request = "PAUSE " + self.fileName + " RTSP/1.0\n" + \
						"CSeq: " + str(self.rtspSeq) + "\n" + \
						"Session: " + str(self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			request = "TEARDOWN " + self.fileName + " RTSP/1.0" + "\n" + \
						"CSeq: " + str(self.rtspSeq) + "\n" + \
						"Session: " + str(self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.TEARDOWN
			
		# FAST/SLOW/FORWARD/BACKWARD request
		elif requestCode in (self.FAST, self.SLOW, self.FORWARD, self.BACKWARD) and self.state in (self.READY, self.PLAYING):
			self.rtspSeq += 1
			method = {
				self.FAST: 		"FAST",
				self.SLOW: 		"SLOW",
				self.FORWARD: 	"FORWARD",
				self.BACKWARD:	"BACKWARD"
			}[requestCode]
			request = method + " " + self.fileName + " RTSP/1.0" + "\n" + \
						"CSeq: " + str(self.rtspSeq) + "\n" + \
						"Session: " + str(self.sessionId)
			self.requestSent = requestCode

		else:
			return
		
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

						# New: parase Frames cnt from reply
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
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()