import threading

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		self.lock = threading.Lock()
		self.buildIndex()
	
	def buildIndex(self):
		self.offset = []
		self.file.seek(0)
		while True:
			offset = self.file.tell()
			data = self.file.read(5)

			if not data or len(data) < 5:
				break

			try:
				frameLen = int(data)
			except ValueError:
				break

			self.offset.append(offset)
			self.file.seek(frameLen, 1)
		self.totalFrames = len(self.offset)
		self.file.seek(0)

	def nextFrame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data: 
			framelength = int(data)
							
			# Read the current frame
			data = self.file.read(framelength)
			self.frameNum += 1
		return data
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	def seekFrame(self, n):
		with self.lock:
			if self.totalFrames == 0:
				return 0
			n = max(0, min(n, self.totalFrames - 1))
			self.file.seek(self.offset[n])
			self.frameNum = n
			return n