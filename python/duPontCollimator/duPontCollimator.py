from __future__ import division, absolute_import

import collections

import numpy

from twisted.internet.protocol import Protocol, Factory

from .config import focusInterval, getCollimation, minTranslation, minTipTilt

ON = "ON"
OFF = "OFF"

helpString ="""
Commands:

help
Show this help.

status
Show current status.

focus [off|on]
Apply focus model. if off or on specified start or stop the timer.
Slews automatically trigger focus move to input RA and Dec coords.

collimate [force] [target]
Apply flexure model.  If target specified move to collimation
for input RA and Dec coords, else collimate to current telescope
position. If force specified, move themirror even if below minimum
threshold.
"""


class DuPontCollimator(Protocol):
    def __init__(self, tcsDevice, m2Device):
        self.tcsDevice = tcsDevice
        self.m2Device = m2Device
        self.focusBase = None
        self.tempBase = None
        self.autofocus = OFF
        self.autofocusInterval = focusInterval

    def getTargetCollimationUpdate(self):
        return getCollimation(self.tcsDevice.targetHA, self.tcsDevice.targetDec)

    def getCurrentCollimationUpdate(self):
        return getCollimation(self.tcsDevice.ha, self.tcsDevice.dec)

    def getCurrentCollimation(self):
        return collections.OrderedDict((
            ("tip", self.m2Device.orientation[1]),
            ("tilt", self.m2Device.orientation[2]),
            ("X", self.m2Device.orientation[3]),
            ("Y", self.m2Device.orientation[4]),
            ))

    def getDeltaCollimation(self, collimation):
        deltaCol = collections.OrderedDict()
        for key, currValue in self.getCurrentCollimation().iteritems():
            deltaCol[key] = currValue-collimation[key]
        return deltaCol

    def connectionMade(self):
        self.reply("HOLA!")

    def connectionLost(self, reason):
        pass

    def dataReceived(self, userInput):
        # parse the incomming command
        self.parseCommand(userInput)

    def reply(self, replyToUser):
        replyToUser = replyToUser.strip() + "\n"
        self.transport.write(replyToUser)

    def parseCommand(self, userInput):
        userInput = userInput.lower().strip()
        if not userInput:
            return
        if userInput == "help":
            self.reply(helpString)
        elif userInput == "status":
            for line in self.statusLines():
                self.reply(line)
        elif userInput.startswith("collimate"):
            doForce = False
            doTarget = False
            for arg in userInput.split():
                if arg == "collimate":
                    continue
                elif arg == "force":
                    doForce == True
                elif arg == "target":
                    doTarget == True
                else:
                    self.reply("Bad User Input: %s"%arg)
                    return
            self.updateCollimation(force=doForce, target=doTarget)
        else:
            self.reply("Bad User Input: %s"%userInput)
        # print("got %s"%userInput)
        # self.reply(str(self.tcsDevice.dec))
        # self.reply(str(self.tcsDevice.ha))
        # self.reply(str(self.tcsDevice.targetDec))
        # self.reply(str(self.tcsDevice.targetHA))
        # self.reply(str(self.m2Device.state))
        # self.reply(str(self.m2Device.orientation))

    def formatCollimationStr(self, collimationDict):
        collStrList = []
        for key, value in collimationDict.iteritems():
            collStrList.append("%s=%.2f"%(key, value))
        return " ".join(collStrList)

    def statusLines(self):
        focusBaseStr = "None" if self.focusBase is None else "%.1f"%self.focusBase
        tempBaseStr = "None" if self.tempBase is None else "%.1f"%self.tempBase
        afStr = OFF if self.autofocus==OFF else "%.2f seconds"%self.autofocusInterval
        collTargUpdate = self.getTargetCollimationUpdate()
        collCurrUpdate = self.getCurrentCollimationUpdate()
        deltaTargColl = self.getDeltaCollimation(collTargUpdate)
        deltaCurrColl = self.getDeltaCollimation(collCurrUpdate)

        statusLines = [
            "[Focus, Temp] zeropoint: [%s, %s]"%(focusBaseStr, tempBaseStr),
            "Autofocus updates: %s"%afStr,
            "Delta-Collimation values:",
            "--Target: %s"%self.formatCollimationStr(deltaTargColl),
            "--Current: %s"%self.formatCollimationStr(deltaCurrColl),
        ]
        return statusLines

    def updateCollimation(self, force=False, target=False):
        if target:
            newColl = self.getTargetCollimationUpdate()
            deltaColl = self.getDeltaCollimation(newColl)
        else:
            newColl = self.getTargetCollimationUpdate()
            deltaColl = self.getDeltaCollimation(newColl)
        if not force:
            # check limits before proceeding
            overMinTilt = numpy.max([numpy.abs(deltaColl["tip"]), numpy.abs(deltaColl["tilt"])]) > minTipTilt
            overMinTrans = numpy.max([numpy.abs(deltaColl["X"]), numpy.abs(deltaColl["Y"])]) > minTranslation
            doMove = overMinTilt or overMinTrans
            if not doMove:
                self.reply("Delta collimation too small for move:")
                self.reply(self.formatCollimationStr(deltaColl))
                return
        # command the new collimation with current focus value
        currentFocus = self.m2Device.orientation[0]
        self.reply("Updating collimation: ")
        self.reply(self.formatCollimationStr(newColl))
        newFullOrientation = [currentFocus] + newColl.values()
        self.m2Device.move(newFullOrientation)

def getFactory(m2Device, tcsDevice):
    # construct m2Device and tcsDevcie have
    # active communication with the m2 and tcs
    class DuPontCollimatorFactory(Factory):
        def buildProtocol(self, addr):
            return DuPontCollimator(m2Device, tcsDevice)
    return DuPontCollimatorFactory
