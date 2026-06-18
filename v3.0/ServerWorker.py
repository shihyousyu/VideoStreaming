from random import randint
import sys, traceback, threading, socket, os

from VideoStream import VideoStream
from RtpPacket import RtpPacket

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	DESCRIBE = 'DESCRIBE'

	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2

	clientInfo = {}

	def __init__(self, clientInfo):
		self.clientInfo = clientInfo

	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()

	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))

	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		filename = line1[1]
		seq = request[1].split(' ')

		if requestType == self.DESCRIBE:
			print("processing DESCRIBE\n")
			self.replyDescribe(seq[1], filename)
			return

		if requestType == self.SETUP:
			if self.state == self.INIT:
				print("processing SETUP\n")

				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
					return

				self.clientInfo['session'] = randint(100000, 999999)
				self.replyRtsp(self.OK_200, seq[1])
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]

		elif requestType == self.PLAY:
			if self.state == self.READY:
				print("processing PLAY\n")
				self.state = self.PLAYING

				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				self.replyRtsp(self.OK_200, seq[1])

				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
				self.clientInfo['worker'].start()

		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY

				self.clientInfo['event'].set()
				self.replyRtsp(self.OK_200, seq[1])

		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			if 'event' in self.clientInfo:
				self.clientInfo['event'].set()

			self.replyRtsp(self.OK_200, seq[1])

			if 'rtpSocket' in self.clientInfo:
				self.clientInfo['rtpSocket'].close()
			self.state = self.INIT

	def describeBody(self, filename):
		"""Return a small SDP-style description for the requested MJPEG stream."""
		size = 0
		if os.path.exists(filename):
			size = os.path.getsize(filename)

		lines = [
			"v=0",
			"o=VideoStreaming 0 0 IN IP4 127.0.0.1",
			"s=" + filename,
			"t=0 0",
			"m=video 0 RTP/AVP 26",
			"a=control:streamid=0",
			"a=rtpmap:26 JPEG/90000",
			"a=filesize:%d" % size,
		]
		return "\n".join(lines)

	def replyDescribe(self, seq, filename):
		body = self.describeBody(filename)
		reply = "RTSP/1.0 200 OK\n" + \
				"CSeq: " + seq + "\n" + \
				"Content-Type: application/sdp\n" + \
				"Content-Length: " + str(len(body)) + "\n\n" + \
				body

		connSocket = self.clientInfo['rtspSocket'][0]
		connSocket.send(reply.encode())

	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(0.05)

			if self.clientInfo['event'].isSet():
				break

			data = self.clientInfo['videoStream'].nextFrame()
			if data:
				frameNumber = self.clientInfo['videoStream'].frameNbr()
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber), (address, port))
				except:
					print("Connection Error")

	def makeRtp(self, payload, frameNbr):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26
		seqnum = frameNbr
		ssrc = 0

		rtpPacket = RtpPacket()
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)

		return rtpPacket.getPacket()

	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		connSocket = self.clientInfo['rtspSocket'][0]

		if code == self.OK_200:
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket.send(reply.encode())

		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
			reply = 'RTSP/1.0 404 FILE NOT FOUND\nCSeq: ' + seq
			connSocket.send(reply.encode())

		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
			reply = 'RTSP/1.0 500 CONNECTION ERROR\nCSeq: ' + seq
			connSocket.send(reply.encode())
