from random import randint
import sys
import traceback
import threading
import socket
import os
from VideoStream import VideoStream
from RtpPacket import RtpPacket


class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    DESCRIBE = 'DESCRIBE'
    BACKWARD = 'BACKWARD'
    FORWARD = 'FORWARD'
    SWITCH = 'SWITCH'

    INIT = 0
    READY = 1
    PLAYING = 2
    CHOOSING = 3
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
                temp = data.decode("utf-8")
                if (temp.split('\n')[0].split(' ')[0] == self.PLAY) :
                    print("Data received:\n" + temp.split('\n')[0] +"\n" + temp.split('\n')[1]  +"\n" +temp.split('\n')[2] )
                else:
                    print("Data received:\n" + temp)
                self.processRtspRequest(temp)

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
            if self.state == self.INIT or self.state == self.SWITCH:
                # Update state
                print("processing SETUP\n")

                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.state = self.READY
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

                # Generate a randomized RTSP session ID
                self.clientInfo['session'] = randint(100000, 999999)
                self.clientInfo['isDescribed-rq'] = False
                self.clientInfo['filename'] = filename
                # Send RTSP reply
                self.request = self.SETUP
                self.replyRtsp(self.OK_200, seq[1])

                # Get the RTP/UDP port from the last line
                self.clientInfo['rtpPort'] = request[2].split(' ')[3]

        # Process PLAY request
        elif requestType == self.PLAY:
            if self.state == self.READY or self.state == self.SWITCH:
                print("processing PLAY\n")
                self.state = self.PLAYING

                # Create a new socket for RTP/UDP
                self.clientInfo["rtpSocket"] = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM)
                self.clientInfo['isDescribed-rq'] = False
                self.request = self.PLAY
                self.replyRtsp(self.OK_200, seq[1])

                # Create a new thread and start sending RTP packets
                self.clientInfo['event'] = threading.Event()
                self.clientInfo['worker'] = threading.Thread(
                    target=self.sendRtp ,args=(int(request[3]),))
                self.clientInfo['worker'].start()

        # Process PAUSE request
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY
                self.clientInfo['event'].set()
                self.clientInfo['isDescribed-rq'] = False
                self.request = self.PAUSE
                self.replyRtsp(self.OK_200, seq[1])

        # Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")

            self.clientInfo['event'].set()
            self.clientInfo['isDescribed-rq'] = False
            self.request = self.TEARDOWN
            self.replyRtsp(self.OK_200, seq[1])

            # Close the RTP socket
            self.clientInfo['rtpSocket'].close()

        # Process DESCRIBE request
        elif requestType == self.DESCRIBE:
            print("Processing DESCRIBE\n")
            self.clientInfo['isDescribed-rq'] = True
            self.replyRtsp(self.OK_200, seq[1])

        # Process BACKWARD request
        elif requestType == self.BACKWARD:
            print("Processing BACKWARD\n")
            self.clientInfo['videoStream'].back()
            self.replyRtsp(self.OK_200, seq[1])
          
        # Process FOWARD request    
        elif requestType == self.FORWARD:
            print("Processing FORWARD\n")
            self.clientInfo['videoStream'].forward()
            self.replyRtsp(self.OK_200, seq[1])

        # Process SWITCH request
        elif requestType == self.SWITCH:
            print("Processing SWITCH\n")
            self.state = self.SWITCH
            try:
                self.clientInfo['event'].set()
            except:
                pass
            self.request = self.SWITCH
            self.replyRtsp(self.OK_200, seq[1])

    def sendRtp(self , curTime):
        """Send RTP packets over UDP."""
        self.clientInfo['videoStream'].setFrame(curTime*20)
        while True:
            self.clientInfo['event'].wait(0.05)

            # Stop sending if request is PAUSE or TEARDOWN
            if self.clientInfo['event'].is_set():
                break

            data = self.clientInfo['videoStream'].m_getNextFrame()

            if data:
                frameNumber = self.clientInfo['videoStream'].getCurrentFrame()
                try:
                    address = self.clientInfo['rtspSocket'][1][0]
                    port = int(self.clientInfo['rtpPort'])
                    self.clientInfo['rtpSocket'].sendto(
                        self.makeRtp(data, frameNumber), (address, port))
                except:
                    print("Connection Error")

    def makeRtp(self, payload, frameNbr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26  # MJPEG type
        seqnum = frameNbr
        ssrc = 0

        rtpPacket = RtpPacket()

        rtpPacket.encode(version, padding, extension, cc,
                         seqnum, marker, pt, ssrc, payload)

        return rtpPacket.getPacket()

    def replyRtsp(self, code, seq):
        """Send RTSP reply to the client."""
        if code == self.OK_200:
            #print("200 OK")
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + \
                '\nSession: ' + str(self.clientInfo['session'])
            if (self.request != self.SETUP and self.request != self.SWITCH and self.clientInfo['isDescribed-rq'] == False ):
               reply += '\n'+str(self.clientInfo['videoStream'].getCurrentFrame())
            if (self.clientInfo['isDescribed-rq']):
                body=f"""      
Protocol version: RTSP/1.0
RTP Port: {self.clientInfo['rtpPort']}
RTSP Port: {str(self.clientInfo['rtspSocket'][0]).split(', ')[5][0:-1]}
Session ID: {self.clientInfo['session']}
Encoding Type: utf-8
Video Name: {self.clientInfo['filename']}
Video Size: {"{:.2f}".format(float(os.path.getsize('movie.Mjpeg')/1024/1024))} MB
Content Type: application/sd
"""
                reply += body
                self.clientInfo['isDescribed-rq'] = False

            if (self.request == self.SETUP):
                totalFrame = self.clientInfo['videoStream'].frameNbr()
                reply += f'\nTotalframe: {totalFrame}'

            if (self.request == self.SWITCH):
                fileList = [f for f in os.listdir() if f.endswith('.Mjpeg')]
                reply += '\n' + ' '.join(fileList)
            connSocket = self.clientInfo['rtspSocket'][0]
            print(f'Data sent:\n{reply}\n')
            connSocket.send(reply.encode())

        # Error messages
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")
