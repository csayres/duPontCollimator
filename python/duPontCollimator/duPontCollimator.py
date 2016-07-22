from __future__ import division, absolute_import

import collections

import numpy

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import task

from .config import focusInterval, getCollimation, minTranslation, minTipTilt, minFocusMove, getFocus

ON = "on"
OFF = "off"

helpString ="""
Commands:

help
--Show this help.

status
--Show current status.

focus [on] [off] [set] [force]
--Apply focus model. If "on" specified, apply focus AND start the timer.
--If "off" specified, stop timer (if active) and don't apply focus. If "set" specified,
--use current focus and temperature for focus model zero points. If force specified,
--move the mirror even if move is below minimum offset threshold.
--"off" argument may not be present with either "on" nor "force"
--but "off" is valid with "set", in which case the focus/temp baselines are set
--but the focus move is not applied.


collimate [force] [target]
--Apply flexure model.  If target specified move to collimation
--for input RA and Dec coords, else collimate to current telescope
--position. If force specified, move the mirror even if move is below
--minimum offset threshold.
"""


class DuPontCollimator(Protocol):
    def __init__(self, tcsDevice, m2Device):
        self.tcsDevice = tcsDevice
        self.m2Device = m2Device
        self.focusBase = None
        self.tempBase = None
        self.autofocus = OFF
        self.focusTimer = task.LoopingCall(self.updateFocus)

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
        # send a string back to the user
        replyToUser = replyToUser.strip() + "\n"
        self.transport.write(replyToUser)

    def parseCommand(self, userInput):
        # parse an incomming user command
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
            args = userInput.split()
            for arg in args:
                if arg == "collimate":
                    continue
                elif arg == "force":
                    doForce = True
                elif arg == "target":
                    doTarget = True
                else:
                    self.reply("Bad User Input: %s"%arg)
                    self.reply(helpString)
                    return
            self.updateCollimation(force=doForce, target=doTarget)
        elif userInput.startswith("focus"):
            timer = None
            setFocus = False
            force = False
            args = userInput.split()
            if OFF in args and (ON in args or "force" in args):
                self.reply("Bad User Input: may not specify 'off' with 'on' nor 'force'")
                self.reply(helpString)
                return
            for arg in args:
                if arg == "focus":
                    continue
                elif arg == ON:
                    timer = ON
                elif arg == OFF:
                    timer = OFF
                elif arg == "set":
                    setFocus = True
                elif arg == "force":
                    force = True
                else:
                    self.reply("Bad User Input: %s"%arg)
                    self.reply(helpString)
                    return
            self.updateFocus(timer=timer, setFocus=setFocus, userCommanded=True, force=force)

        else:
            self.reply("Bad User Input: %s"%userInput)
            self.reply(helpString)

    def formatCollimationStr(self, collimationDict):
        collStrList = []
        for key, value in collimationDict.iteritems():
            collStrList.append("%s=%.2f"%(key, value))
        return " ".join(collStrList)

    def statusLines(self):
        focusBaseStr = "None" if self.focusBase is None else "%.1f"%self.focusBase
        tempBaseStr = "None" if self.tempBase is None else "%.1f"%self.tempBase
        afStr = OFF if self.autofocus==OFF else "%.2f seconds"%focusInterval
        collTargUpdate = self.getTargetCollimationUpdate()
        collCurrUpdate = self.getCurrentCollimationUpdate()
        deltaTargColl = self.getDeltaCollimation(collTargUpdate)
        deltaCurrColl = self.getDeltaCollimation(collCurrUpdate)

        statusLines = [
            "[Focus, Temp] zeropoint: [%s, %s]"%(focusBaseStr, tempBaseStr),
            "Autofocus updates: %s"%afStr,
            "Collimation absolute values:",
            "--Target: %s"%self.formatCollimationStr(collTargUpdate),
            "--Current: %s"%self.formatCollimationStr(collCurrUpdate),
            "Collimation offset (delta) values:",
            "--Target: %s"%self.formatCollimationStr(deltaTargColl),
            "--Current: %s"%self.formatCollimationStr(deltaCurrColl),
        ]
        return statusLines

    def updateCollimation(self, force=False, target=False):
        if target:
            # check that HA is within 5 hours
            if numpy.abs(self.tcsDevice.targetHA)/15. > 5:
                self.reply("Target HA > 5hrs!!!! Not allowed, enter a new ra")
                return
            newColl = self.getTargetCollimationUpdate()
        else:
            newColl = self.getCurrentCollimationUpdate()
        deltaColl = self.getDeltaCollimation(newColl)
        if not force:
            # check limits before proceeding
            overMinTilt = numpy.max([numpy.abs(deltaColl["tip"]), numpy.abs(deltaColl["tilt"])]) > minTipTilt
            overMinTrans = numpy.max([numpy.abs(deltaColl["X"]), numpy.abs(deltaColl["Y"])]) > minTranslation
            doMove = overMinTilt or overMinTrans
            if not doMove:
                self.reply("Collimation offset too small for move:")
                self.reply(self.formatCollimationStr(deltaColl))
                return
        if not self.m2Device.isReady:
            self.reply("M2 device not ready to collimate. State=%s Galil=%s"%(str(self.m2Device.state), str(self.m2Device.galil)))
            return
        # command the new collimation with current focus value
        currentFocus = self.m2Device.orientation[0]
        self.reply("Updating collimation: ")
        self.reply(self.formatCollimationStr(newColl))
        newFullOrientation = [currentFocus] + newColl.values()
        self.m2Device.move(newFullOrientation)

    def updateFocus(self, timer=None, setFocus=None, userCommanded=False, force=False):
        # if userCommanded is True, focus was commanded by the user,
        # do it regardless of whether or not the timer is on or off.
        # if userCommanded is False, this was triggered
        # by the timer so check for timer state before applying
        # focus update.
        if setFocus:
            self.focusBase = self.m2Device.focus
            self.tempBase = self.tcsDevice.temp
            self.reply("Setting baseFocus=%.2f baseTemmp=%.2f"%(self.focusBase, self.tcsDevice.temp))
        if timer == OFF:
            self.autofocus = OFF
            # stop the timer if active
            self.focusTimer.stop()
            self.reply("Stopping focus interval")
            # return not doing anything!
            return
        elif timer == ON:
            self.autofocus = ON
            # call this again after the interval has elapsed
            self.reply("Starting focus interval %.2f seconds"%focusInterval)
            self.focusTimer.start(focusInterval, now=False)

        if not userCommanded and self.autofocus == OFF:
            # focus update was fired on a timer (not user commanded)
            # but autofocus is was off, so
            # don't do anything
            # autofocus is off timer should already be off
            # but do it again for paranoia?
            self.focusTimer.stop()
            return
        if None in [self.focusBase, self.tempBase]:
            self.reply("Cannot set focus without a baseline, please issue focus set (at a good focus)")
            self.reply(self.statusLines()[0])
            return
        elif None in [self.tcsDevice.temp, self.tcsDevice.elevation]:
            self.reply("Cannot set focus, missing tcs Data, is it connected?")
            return
        newFocusValue = getFocus(self.focusBase, self.tempBase, self.tcsDevice.temp, self.tcsDevice.elevation)
        deltaFocus = newFocusValue - self.m2Device.focus
        if numpy.abs(deltaFocus) < minFocusMove and not force:
            self.reply("Focus offset %.2f too small to apply"%deltaFocus)
            return
        if not self.m2Device.isReady:
            self.reply("M2 device not ready to focus. State=%s Galil=%s"%(str(self.m2Device.state), str(self.m2Device.galil)))
            return
        self.reply("Updating focus to %.2f"%newFocusValue)
        self.m2Device.move([newFocusValue])

def getFactory(m2Device, tcsDevice):
    # construct m2Device and tcsDevcie have
    # active communication with the m2 and tcs
    class DuPontCollimatorFactory(Factory):
        def buildProtocol(self, addr):
            return DuPontCollimator(m2Device, tcsDevice)
    return DuPontCollimatorFactory
