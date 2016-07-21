from __future__ import division, absolute_import

import collections
import numpy

from twisted.internet import task

from .baseDevice import BaseDevice, DeviceClientFactory
import .config

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

statusFieldDict = collections.OrderedDict(
   ("inpra", hms2deg),
   ("inpdc", dms2deg),
   ("st", hms2deg),
   ("pos", castPos),
   ("state", castTelState),
)

class TCSDevice(BaseDevice):

    def __init__(self, slewCallback = None):
        # initialize all status fields as
        # attributes on this class with value none
        self.statusCmdQueue = [] # this is populated by self.getStatus()
        self.slewCallback = slewCallback
        # begin status timer
        loop = task.LoopingCall(self.getStatus)
        loop.start(config.statusRefreshRate)

    @property
    def dec(self):
        return self.pos[1] if self.pos is not None else None

    @property
    def ha(self):
        return self.pos[0] if self.pos is not None else None

    @property
    def targetDec(self):
        return self.pos[1] if self.pos is not None else None

    @property
    def targetRA(self):
        return self.ha[1] if self.pos is not None else None

    @property
    def isSlewing(self):
        return self.state == Slewing

    def clearStatus(self):
        # set all status pieces to None,
        # to ensure we get a fresh status
        # each time.
        for attr in statusFieldDict.keys():
            setattr(self, attr, None)

    def dataReceived(self, data):
        # called each time data is output from tcs
        data = data.strip()
        if not self.statusCmdQueue:
            # ignore unsolicited output
            print("TCS ignoring output %s"%data)
            return
        currCmd = self.statusCmdQueue.pop(0) #pop from list and parse output
        try:
            newValue = statusFieldDict[currCmd](data)
            # check if we just moved from not slew, to a slew state
            if newValue == Slewing and not self.isSlewing and self.slewCallback is not None:
                # fire callback on slewing state
                # note state is last value quered so by time
                # callback all status has been refreshed
                print("Slewing state detected")
                self.slewCallback()
            self.setattr(self, currCmd, newValue)
        except:
            print("TCS could not parse %s for command %s"%(data, currCmd))
        # if more status commands are on queue, run next one
        if self.statusCmdQueue:
            # more commands on queue
            # send the next one
            self.sendNextStatus()

    def sendNextStatus(self):
        self.transport.write("%s\r\n"%self.statusCmdQueue[0])

    def getStatus(self):
        self.statusCmdQueue = statusFieldDict.keys()

    def addSlewCallback(self, slewCallback):
        """each time telescpe goes from
        not slewing to slewing, call slewCallback
        """
        assert callable(slewCallback)
        self.slewCallback = slewCallback



class TCSFact(DeviceClientFactory):
    def buildProtocol(self, addr):
        return TCSDevice()

def connectTCS():
    from twisted.internet import reactor
    reactor.connectTCP(conifg.tcsHost, config.tcsPort, TCSFact())







