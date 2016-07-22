from __future__ import division, absolute_import

import collections
import traceback
import sys

import numpy

from twisted.internet import task
from twisted.internet.protocol import Protocol, ClientFactory
#http://twistedmatrix.com/documents/12.1.0/core/howto/clients.html

from .config import statusRefreshRate

Slewing = "Slewing"
NotSlewing = "NotSlewing"
DegreesPerHour = 15.0

def dms2deg(dmsString):
    """Convert a d:m:s or h:m:s to decimal degrees or decimal hours respectively
    """
    direction = 1
    if dmsString.startswith("-"):
        direction = -1
    dmsString = dmsString.strip("-+")
    degrees, minutes, seconds = [float(val) for val in dmsString.split(":")]
    decimalDegrees = degrees + minutes/60. + seconds/3600.
    return direction * decimalDegrees

def hms2deg(hmsString):
    """Convert a string looking like [-+]hours:minutes:seconds
    to decimal degrees
    """
    decimalHours = dms2deg(hmsString)
    return decimalHours * DegreesPerHour


def castTelState(tcsStateResponse):
    """Convert the enumerated telescope state into a string
    """
    tcsIntResponse = int(tcsStateResponse)
    if tcsIntResponse == 3:
        # slewing stage
        return Slewing
    else:
        return NotSlewing

def castPos(tcsPosStr):
    return [numpy.degrees(float(x)) for x in tcsPosStr.split()]

statusFieldDict = collections.OrderedDict((
   ("inpra", hms2deg),
   ("inpdc", dms2deg),
   ("st", hms2deg),
   ("pos", castPos),
   ("ttruss", float),
   ("telel", float),
   ("state", castTelState), # important that state remains last in this list! for checking new slew
))

class TCSDevice(Protocol):

    def __init__(self, slewCallback = None):
        # initialize all status fields as
        # attributes on this class with value none
        self.statusCmdQueue = [] # this is populated by self.getStatus()
        self.slewCallback = slewCallback

    @property
    def dec(self):
        return self.pos[1] if self.pos is not None else None

    @property
    def ha(self):
        return self.pos[0] if self.pos is not None else None

    @property
    def targetDec(self):
        return self.inpdc if self.inpdc is not None else None

    @property
    def targetHA(self):
        st = self.st
        ra = self.inpra
        if st is None or ra is None:
            return None
        else:
            ha = st - ra
            return ha

    @property
    def temp(self):
        return self.ttruss

    @property
    def elevation(self):
        return self.telel

    @property
    def isSlewing(self):
        return self.state == Slewing

    def connectionMade(self):
        print("TCS connection made, starting status polling")
        loop = task.LoopingCall(self.getStatus)
        loop.start(statusRefreshRate)

    def clearStatus(self):
        # set all status pieces to None,
        # to ensure we get a fresh status
        # each time.
        for attr in statusFieldDict.keys():
            setattr(self, attr, None)

    def dataReceived(self, data):
        # called each time data is output from tcs
        try:
            data = str(data.strip())
            if not self.statusCmdQueue:
                # ignore unsolicited output
                print("TCS ignoring output %s"%data)
                return
            # print("tcs says: %s"%(str(data)))
            currCmd = self.statusCmdQueue.pop(0) #pop from list and parse output
            newValue = statusFieldDict[currCmd](data)
            # check if we just moved from not slew, to a slew state
            if newValue == Slewing and not self.isSlewing and self.slewCallback is not None:
                # fire callback on slewing state
                # note state is last value quered so by time
                # callback all status has been refreshed
                print("Slewing state detected")
                self.slewCallback()
            setattr(self, currCmd, newValue)
        except:
            print("TCS could not parse %s for command %s"%(data, currCmd))
            traceback.print_exc(file=sys.stdout)
        # if more status commands are on queue, run next one
        if self.statusCmdQueue:
            # more commands on queue
            # send the next one
            self.sendNextStatus()

    def sendNextStatus(self):
        nextCmd = self.statusCmdQueue[0]
        # print("writing to tcs: %s"%(str(nextCmd)))
        self.transport.write("%s\r\n"%nextCmd)

    def getStatus(self):
        # print("getStatus")
        # clear status to ensure we get a fresh one
        self.clearStatus()
        self.statusCmdQueue = statusFieldDict.keys()
        self.sendNextStatus()

    def addSlewCallback(self, slewCallback):
        """each time telescpe goes from
        not slewing to slewing, call slewCallback
        """
        assert callable(slewCallback)
        self.slewCallback = slewCallback


class TCSFact(ClientFactory):
    def buildProtocol(self, addr):
        return TCSDevice()






