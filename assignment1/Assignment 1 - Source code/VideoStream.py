from inspect import currentframe
import time

class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        if( hasattr(self, 'file')):
            self.file.close()
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError
        self.frameNum = 0
        self.frameList = []
        self.getFrameList()
        self.currentFrame = 0

    def getFrameList(self):
        data = self.nextFrame()
        while (data):
            self.frameList.append(data)
            data = self.nextFrame()

    def nextFrame(self):
        """Get next frame."""
        data = self.file.read(5)  # Get the framelength from the first 5 bits
        if data:
            framelength = int(data)
            # Read the current frame
            data = self.file.read(framelength)
            self.frameNum += 1
        return data

    def m_getNextFrame(self):
        if (self.currentFrame < self.frameNum):
            self.currentFrame += 1
            return self.frameList[self.currentFrame-1]
        return ''

    def getCurrentFrame(self):
        return self.currentFrame

    def frameNbr(self):
        """Get frame number."""
        return self.frameNum

    def back(self):
        ammount = int(self.frameNum/5)
        if (self.currentFrame < ammount):
            self.currentFrame = 0
        else:
            self.currentFrame -= ammount

    def forward(self):
        ammount = int(self.frameNum/5)
        if (self.currentFrame > self.frameNum-1-ammount):
            self.currentFrame = self.frameNum-1
        else:
            self.currentFrame += ammount
            
    def setFrame(self,num):
        self.currentFrame = num
