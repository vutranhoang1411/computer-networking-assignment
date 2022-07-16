from asyncio.windows_events import NULL
from cProfile import label
from email import message
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
from PIL import Image, ImageTk
import socket
import threading
import sys
import traceback
import os

from numpy import require

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    CHOOSING = 3
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    DESCRIBE = 4
    BACKWARD = 5
    FORWARD = 6
    SWITCH = 7
    # Initiation..

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        # widget
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        # server info
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        # manage info
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.totalTime = 0
        self.connectToServer()
        self.frameNbr = 0
        self.frameCheck = - 1
        self.playNormal = 0
        self.setupMovie()

    # THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI
    def createWidgets(self):
        """Build GUI."""
        # Create slider
        self.slider = ttk.Scale(
            self.master, orient=HORIZONTAL, from_=0, to_=100)
        self.slider.grid(row=1, column=0, columnspan=3,
                         sticky=W+E+N+S, padx=2, pady=2)
        self.slider_text = Label(self.master, text='0')
        self.slider_text.grid(row=1, column=3, padx=2, pady=2)

        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=2, column=0, padx=2, pady=2)

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=1, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=2, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=2, column=3, padx=2, pady=2)

        # Create Describe button
        self.describe = Button(self.master, width=20, padx=3, pady=3)
        self.describe["text"] = "Describe"
        self.describe["command"] = self.describeMovie
        self.describe.grid(row=3, column=0, padx=2, pady=2)

        # Create Backward button
        self.next = Button(self.master, width=20, padx=3, pady=3)
        self.next["text"] = "Backward"
        self.next["command"] = self.backMovie
        self.next.grid(row=3, column=1, padx=2, pady=2)

        # Create Foward button
        self.backward = Button(self.master, width=20, padx=3, pady=3)
        self.backward["text"] = "FastForward"
        self.backward["command"] = self.forwardMovie
        self.backward.grid(row=3, column=2, padx=2, pady=2)

        #Create Switch button
        self.switch = Button(self.master, width=20, padx=3, pady=3)
        self.switch["text"] = "Switch"
        self.switch["command"] = self.switchMovie
        self.switch.grid(row=3, column=3, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)  # sticky=W+E+N+S
        self.label.grid(row=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

    def setupMovie(self):
        """Setup button handler."""
        if (self.state == self.INIT or self.state == self.CHOOSING):
            self.openRtpPort()
            self.sendRtspRequest(self.SETUP)
            self.recvRtspReply()
    
    def exitClient(self):
        if (self.state == self.READY or self.state == self.PLAYING):
            self.master.destroy()
            self.event.set()
            self.rtpSocket.close()
            self.sendRtspRequest(self.TEARDOWN)
            self.recvRtspReply()
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

    def pauseMovie(self):
        if (self.state == self.PLAYING):
            self.sendRtspRequest(self.PAUSE)
            self.recvRtspReply()

    def playMovie(self):
        if (self.state == self.READY or self.state == self.CHOOSING):
            self.sendRtspRequest(self.PLAY)
            self.recvRtspReply()

    def describeMovie(self):
        self.sendRtspRequest(self.DESCRIBE)
        self.recvRtspReply()

    def backMovie(self):
        self.sendRtspRequest(self.BACKWARD)
        self.playNormal = 1
        self.recvRtspReply()

    def forwardMovie(self):
        self.sendRtspRequest(self.FORWARD)
        self.playNormal = 1
        self.recvRtspReply()

    def switchMovie(self):
        if(self.state != self.INIT):
            self.sendRtspRequest(self.SWITCH)
            self.recvRtspReply()

    def updateSlider(self, value):
        self.slider['value'] = value
        m1, s1 = divmod(value, 60)
        m2, s2 = divmod(self.totalTime, 60)
        self.slider_text.config(
            text=f'{m1:02d}:{s1:02d}' + f' : {m2:02d}:{s2:02d}')
        self.slider.config(to=self.totalTime)

    def listenRtp(self):
        rtpPac = RtpPacket()
        while (TRUE):
            self.event.wait(0.05)
            if (self.event.is_set()):
                break
            try:
                data = self.rtpSocket.recv(150000)
            except TimeoutError:
                self.pauseMovie()
                break
            self.state = self.PLAYING
            rtpPac.decode(data)
            self.currFrameNbr = rtpPac.seqNum()
            self.updateMovie(self.writeFrame(rtpPac.payload))
            if ( (self.frameCheck <= self.currFrameNbr and self.currFrameNbr <=(self.frameCheck + int(self.totalFrame/10)))  or self.playNormal == 0):
                self.frameNbr = self.currFrameNbr
                print( "Frame Number: " , self.frameNbr  )
                self.updateSlider(int(self.frameNbr/20))
                self.playNormal = 0

    def writeFrame(self, data):
        fileName = CACHE_FILE_NAME+str(self.sessionId)+CACHE_FILE_EXT
        file = open(fileName, "wb")
        file.write(data)
        file.close()

        return Image.open(fileName)
        """Write the received frame to a temp image file. Return the image file."""

    def updateMovie(self, imageFile):
        img = ImageTk.PhotoImage(imageFile)
        self.label.configure(image=img, height=288)
        self.label.image = img
        """Update the image file as video frame in the GUI."""

    def connectToServer(self):
        self.rstpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rstpSocket.connect((self.serverAddr, self.serverPort))

        """Connect to the Server. Start a new RTSP/TCP session."""
        
    def sendRtspRequest(self, requestCode):
        rstpMessage = ""
        self.rtspSeq += 1
        """Send RTSP request to the server."""
        # -------------
        if (requestCode == self.SETUP):
            rstpMessage += "SETUP"
        elif (requestCode == self.PLAY):
            rstpMessage += "PLAY"
        elif (requestCode == self.PAUSE):
            rstpMessage += "PAUSE"
        elif (requestCode == self.DESCRIBE):
            rstpMessage += "DESCRIBE"
        elif (requestCode == self.TEARDOWN):
            rstpMessage += "TEARDOWN"
        elif (requestCode == self.BACKWARD):
            rstpMessage += "BACKWARD"
        elif (requestCode == self.FORWARD):
            rstpMessage += "FORWARD"
        elif (requestCode == self.SWITCH):
            rstpMessage += "SWITCH"
        rstpMessage += f' {self.fileName} RSTP/1.0\nCSeq: {self.rtspSeq}\n'

        if (requestCode == self.SETUP):
            rstpMessage += f'Transport: RTP/UDP; client_port= {self.rtpPort}'
        else:
            if ( requestCode == self.PLAY ):
                rstpMessage += f'Session: {self.sessionId}\n{int(self.slider.get())}'
            else :
                rstpMessage += f'Session: {self.sessionId}'
        self.rstpSocket.send(rstpMessage.encode())
        self.requestSent = requestCode
        # -------------

    def recvRtspReply(self):
        data = self.rstpSocket.recv(256)
        self.handleRtspReply(data.decode('utf-8'))

    def handleRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        dataByLine = data.split('\n')
        sessionID = int(dataByLine[2].split(' ')[1])
        responseCode = int(dataByLine[0].split(' ')[1])
        if (self.sessionId == 0 or self.state == self.CHOOSING):
            if (self.state == self.CHOOSING and os.path.exists(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)):
                os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
            self.sessionId = sessionID

        if (self.sessionId == sessionID and responseCode == 200):
            if (self.requestSent == self.SETUP):
                self.totalTime = round(int(dataByLine[3].split(' ')[1])/20)
                self.totalFrame = int(dataByLine[3].split(' ')[1])
                self.state = self.READY
            elif (self.requestSent == self.PLAY):
                self.event = threading.Event()
                threading.Thread(target=self.listenRtp).start()
                self.state = self.PLAYING
            elif (self.requestSent == self.PAUSE):
                self.event.set()
                self.state = self.READY
            elif (self.requestSent == self.TEARDOWN):
                self.state = self.INIT
                self.teardownAcked = 1
                self.rstpSocket.close()
            elif (self.requestSent == self.DESCRIBE):
                self.displayDescribe(data)
            elif (self.requestSent == self.BACKWARD):
                self.frameNbr = int(max(0, self.frameNbr - self.totalTime*20*0.2))
                self.frameCheck = int(dataByLine[3]) + 2
                self.updateSlider(int(self.frameNbr/20))
            elif (self.requestSent == self.FORWARD):
                self.frameNbr = int(min(self.frameNbr + self.totalTime*20*0.2, self.totalTime*20))
                self.curframe = int(dataByLine[3])
                self.frameCheck = int(dataByLine[3]) + 2
                self.updateSlider(int(self.frameNbr/20))
            elif (self.requestSent == self.SWITCH):
                if( hasattr(self, 'event')):
                    self.event.set()
                self.state = self.CHOOSING

                # Get list and a default choice
                self.fileList = dataByLine[3].split(' ')
                selected = StringVar()
                selected.set(self.fileList[self.fileList.index(self.fileName)])

                # Create new window
                newWin = Toplevel(self.master)
                newWin.geometry("300x300")
                Label(newWin, text ='Choose a movie: ', font=("Arial", 14)).pack(pady = 10)

                # Create a drop menu
                def getChange(value):
                    self.fileName = value
                    self.frameNbr = 0
                    self.updateSlider(0)
                    self.setupMovie()
                    newWin.destroy()

                menu = OptionMenu(newWin, selected, *self.fileList, command = getChange)
                menu.config(font=("Arial", 14))
                opt = self.master.nametowidget(menu.menuname)
                opt.config(font=("Arial", 14))       
                menu.pack()    

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        # self.rtpSocket = ...
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.bind(('', self.rtpPort))
        # Set the timeout value of the socket to 0.5sec
        # ...
        self.rtpSocket.settimeout(0.5)

    def handler(self):
        self.pauseMovie()
        if (messagebox.askokcancel("Quit?", "Are you sure want to quit?")):
            self.exitClient()
        else:
            self.playMovie()

    def displayDescribe(self, recvData):
        recvData = recvData.split('\n', 3)
        messagebox.showinfo(title="Describe", message=recvData[3])

