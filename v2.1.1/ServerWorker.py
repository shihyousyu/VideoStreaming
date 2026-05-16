from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'

	FAST = 'FAST'
	SLOW = 'SLOW'
	FORWARD = 'FORWARD'
	BACKWARD = 'BACKWARD'

	SPEED = [0.5, 1.0, 1.5, 2.0]
	BASE_INTERVAL = 0.05 # 1.0x ~= 20 fps
	SEEK_FRAMES = 100 # FORWARD / BACKWARD jump over (frames)

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
		self.speedIdx = 1
		self.speed = self.SPEED[self.speedIdx]
		self.sendSeq = 0
		
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
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				print("processing SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
					return # NEW
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1], self.clientInfo['videoStream'].totalFrames) # changed: total_frames
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]
		
		# Process PLAY request 		
		elif requestType == self.PLAY:
			if self.state == self.READY:
				print("processing PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq[1])
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()

		# Process FAST request
		elif requestType == self.FAST:
			print("processing FAST\n")
			if self.speedIdx < len(self.SPEED) - 1:
				self.speedIdx += 1
			else:
				self.speedIdx = 1
			
			self.speed = self.SPEED[self.speedIdx]
			print("speed --> %sx" % self.speed)
			self.replyRtsp(self.OK_200, seq[1])

		# Process SLOW request
		elif requestType == self.SLOW:
			print("processing SLOW\n")
			if self.speedIdx > 0:
				self.speedIdx -= 1
			else:
				self.speedIdx = 1

			self.speed = self.SPEED[self.speedIdx]
			print("speed --> %sx" % self.speed)
			self.replyRtsp(self.OK_200, seq[1])

		# Process FORWARD request
		elif requestType == self.FORWARD:
			print("processing FORWARD")
			self.doSeek(self.SEEK_FRAMES)
			self.replyRtsp(self.OK_200, seq[1])

		# Process BACKWARD request
		elif requestType == self.BACKWARD:
			print("processing BACKWARD")
			self.doSeek(-self.SEEK_FRAMES)
			self.replyRtsp(self.OK_200, seq[1])

	def doSeek(self, delta):
		if 'videoStream' not in self.clientInfo:
			return
		vs = self.clientInfo['videoStream']
		newFrame = vs.seekFrame(vs.frameNbr() + delta)
		print("Seek -> frame %d / %d" % (newFrame, vs.totalFrames))
		if self.state == self.READY and 'rtpSocket' in self.clientInfo:
			self._sendOneFrame()

	def _sendOneFrame(self):
		"""Send a single RTP packet (used for the seek-while-paused preview)."""
		data = self.clientInfo['videoStream'].nextFrame()
		if data:
			self.sendSeq += 1
			try:
				address = self.clientInfo['rtspSocket'][1][0]
				port = int(self.clientInfo['rtpPort'])
				self.clientInfo['rtpSocket'].sendto(
					self.makeRtp(data, self.sendSeq, self.clientInfo['videoStream'].frameNbr()), (address, port))
			except:
				print("Connection Error")

	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(self.BASE_INTERVAL / self.speed)
			
			if self.clientInfo['event'].isSet(): 
				break 
				
			data = self.clientInfo['videoStream'].nextFrame()
			if data: 
				self.sendSeq += 1
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					self.clientInfo['rtpSocket'].sendto(
						self.makeRtp(data, self.sendSeq, self.clientInfo['videoStream'].frameNbr()), (address, port))
				except:
					print("Connection Error")
					#print('-'*60)
					#traceback.print_exc(file=sys.stdout)
					#print('-'*60)

	def makeRtp(self, payload, frameNbr, movie_frame):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload, timestamp=movie_frame)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq, total_frames=None):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			if total_frames is not None:
				reply += '\nTotal-Frames: ' + str(total_frames)

			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
