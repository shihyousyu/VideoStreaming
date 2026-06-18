from Tkinter import *
import tkMessageBox
from PIL import Image, ImageTk
import socket, threading, os, time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	DESCRIBE = 0
	SETUP = 1
	PLAY = 2
	PAUSE = 3
	TEARDOWN = 4

	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
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

		self.pendingPlay = False
		self.replyThreadStarted = False
		self.rtpListening = False
		self.resetStats()
		

	def createWidgets(self):
		"""Build GUI."""
		# Create Play button
		self.play = Button(self.master, width=20, padx=3, pady=3)
		self.play["text"] = "Play"
		self.play["command"] = self.playMovie
		self.play.grid(row=1, column=0, padx=2, pady=2)

		# Create Pause button
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=1, padx=2, pady=2)

		# Create Pause button
		self.stop = Button(self.master, width=20, padx=3, pady=3)
		self.stop["text"] = "Stop"
		self.stop["command"] = self.stopMovie
		self.stop.grid(row=1, column=2, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=3, sticky=W+E+N+S, padx=5, pady=5)

	def resetStats(self):
		self.statsStart = None
		self.statsEnd = None
		self.receivedPackets = 0
		self.receivedBytes = 0
		self.firstSeq = None
		self.highestSeq = 0
		self.receivedSeq = set()

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		if self.state == self.INIT:
			if self.teardownAcked == 1:
				self.reconnectSession()
			self.pendingPlay = True
			self.sendRtspRequest(self.DESCRIBE)
		elif self.state == self.READY:
			# Create a new thread to listen for RTP packets
			if not self.rtpListening:
				self.playEvent = threading.Event()
				self.playEvent.clear()
				threading.Thread(target=self.listenRtp).start()
				self.rtpListening = True
			self.sendRtspRequest(self.PLAY)

	def stopMovie(self):
		"""Stop button handler."""
		if self.state != self.INIT:
			self.pendingPlay = False
			self.sendRtspRequest(self.TEARDOWN)

	def reconnectSession(self):
		"""Open a RTSP connection after a previous STOP/TEARDOWN."""
		self.sessionId = 0
		self.rtspSeq = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.replyThreadStarted = False
		self.rtpListening = False
		self.frameNbr = 0
		self.resetStats()
		self.connectToServer()

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

					self.updateStats(currFrameNbr, len(rtpPacket.getPayload()))

					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet():
					self.rtpListening = False
					break

				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.closeRtpSocket()
					self.rtpListening = False
					break

	def updateStats(self, seq, payloadBytes):
		now = time.time()
		if self.statsStart is None:
			self.statsStart = now
			self.firstSeq = seq
		self.statsEnd = now
		self.receivedPackets += 1
		self.receivedBytes += payloadBytes
		self.receivedSeq.add(seq)
		if seq > self.highestSeq:
			self.highestSeq = seq

	def statsReport(self):
		if self.receivedPackets == 0:
			return "No RTP packets were received in this session."

		expected = self.highestSeq - self.firstSeq + 1
		lost = max(0, expected - len(self.receivedSeq))
		lossRate = (lost / float(expected)) * 100.0 if expected > 0 else 0.0
		duration = max(0.001, (self.statsEnd or time.time()) - self.statsStart)
		dataRate = self.receivedBytes / duration

		return "RTP session statistics:\n" + \
			   "Received packets: %d\n" % self.receivedPackets + \
			   "Expected packets: %d\n" % expected + \
			   "Lost packets: %d\n" % lost + \
			   "Packet loss rate: %.2f%%\n" % lossRate + \
			   "Video data rate: %.2f bytes/sec" % dataRate

	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()

		return cachename

	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image=photo, height=288)
		self.label.image = photo

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		request = None

		if requestCode == self.DESCRIBE and self.state == self.INIT:
			if not self.replyThreadStarted:
				threading.Thread(target=self.recvRtspReply).start()
				self.replyThreadStarted = True

			self.rtspSeq += 1
			request = "DESCRIBE " + self.fileName + " RTSP/1.0\n" + \
					  "CSeq: " + str(self.rtspSeq)
			self.requestSent = self.DESCRIBE

		elif requestCode == self.SETUP and self.state == self.INIT:
			self.rtspSeq += 1
			request = "SETUP " + self.fileName + " RTSP/1.0\n" + \
					  "CSeq: " + str(self.rtspSeq) + "\n" + \
					  "Transport: RTP/UDP; client_port= " + str(self.rtpPort)
			self.requestSent = self.SETUP

		elif requestCode == self.PLAY and self.state == self.READY:
			self.rtspSeq += 1
			request = "PLAY " + self.fileName + " RTSP/1.0\n" + \
					  "CSeq: " + str(self.rtspSeq) + "\n" + \
					  "Session: " + str(self.sessionId)
			self.requestSent = self.PLAY

		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			self.rtspSeq += 1
			request = "PAUSE " + self.fileName + " RTSP/1.0\n" + \
					  "CSeq: " + str(self.rtspSeq) + "\n" + \
					  "Session: " + str(self.sessionId)
			self.requestSent = self.PAUSE

		elif requestCode == self.TEARDOWN and self.state != self.INIT:
			self.rtspSeq += 1
			request = "TEARDOWN " + self.fileName + " RTSP/1.0\n" + \
					  "CSeq: " + str(self.rtspSeq) + "\n" + \
					  "Session: " + str(self.sessionId)
			self.requestSent = self.TEARDOWN

		if request is None:
			return

		self.rtspSocket.send(request.encode())
		print('\nData sent:\n' + request)

	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(4096)

			if reply:
				self.parseRtspReply(reply.decode("utf-8"))

			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				self.replyThreadStarted = False
				break

	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		status = int(lines[0].split(' ')[1])
		seqNum = int(lines[1].split(' ')[1])

		if seqNum != self.rtspSeq:
			return

		if status != 200:
			tkMessageBox.showwarning('RTSP Error', lines[0])
			self.pendingPlay = False
			return

		if self.requestSent == self.DESCRIBE:
			body = data.split('\n\n', 1)[1] if '\n\n' in data else ''
			print("Session description:\n" + body)
			self.sendRtspRequest(self.SETUP)
			return

		session = int(lines[2].split(' ')[1])
		if self.sessionId == 0:
			self.sessionId = session

		if self.sessionId == session:
			if self.requestSent == self.SETUP:
				self.state = self.READY
				self.openRtpPort()
				if self.pendingPlay:
					self.playMovie()

			elif self.requestSent == self.PLAY:
				self.state = self.PLAYING

			elif self.requestSent == self.PAUSE:
				self.state = self.READY
				self.playEvent.set()

			elif self.requestSent == self.TEARDOWN:
				self.state = self.INIT
				self.teardownAcked = 1
				self.pendingPlay = False
				if hasattr(self, 'playEvent'):
					self.playEvent.set()
				self.master.after(0, self.showStats)

	def openRtpPort(self):
		"""Open RTP socket bound to a specified port."""
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtpSocket.settimeout(0.5)

		try:
			self.rtpSocket.bind(("", self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

	def closeRtpSocket(self):
		try:
			self.rtpSocket.shutdown(socket.SHUT_RDWR)
		except:
			pass
		try:
			self.rtpSocket.close()
		except:
			pass

	def showStats(self):
		tkMessageBox.showinfo('Session Statistics', self.statsReport())
		self.removeCacheFile()

	def removeCacheFile(self):
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		if os.path.exists(cachename):
			os.remove(cachename)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		if self.state != self.INIT:
			self.sendRtspRequest(self.TEARDOWN)
		self.master.destroy()
