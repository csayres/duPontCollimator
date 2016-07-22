from __future__ import division, absolute_import

import traceback
import sys

from twisted.internet import task

from .baseDevice import BaseDevice, DeviceClientFactory
from .config import statusRefreshRate

Done = "Done"
Moving = "Moving"
Error = "ERROR"
Failed = "Failed"
On = "on"
Off = "off"
validMotionStates = [Done, Moving, Failed, Error]
validGalilStates = [On, Off]

class M2Device(BaseDevice):

    def __init__(self):
        self.state = None
        self.orientation = [None]*5
        self.galil = None

    @property
    def isReady(self):
        # if moving or unknown, we're not ready
        self.state != Moving or self.state is not None

    def move(self, valueList):
        """Command an offset or absolute orientation move

        @param[in] valueList: list of 1 to 5 values specifying focus(um), tipx("), tilty("), transx(um), transy(um)

        Note: increasing focus means increasing spacing between primary and
        secondary mirrors.
        """
        print ("want to move: ", valueList)
        if self.isMoving:
            print("Not applying move, mirror is busy")
            return
        return
        strValList = " ".join(["%.2f"%val for val in valueList])
        cmdStr = "move %s"%strValList
        self.transport.write("%s\r\n"%cmdStr)
        # status immediately to see moving state
        # determine total time for move
        # just use focus distance as proxy (ignore)

    def connectionMade(self):
        print("M2 connection made, starting status polling")
        loop = task.LoopingCall(self.getStatus)
        loop.start(statusRefreshRate)

    def getStatus(self):
        self.transport.write("status\r\n")

    def dataReceived(self, replyStr):
        """Parse replyString (as returned from the M2 tcp/ip server) and set values

        this is the status string State=DONE Ori=12500.0, -0.0, -0.0, -0.0, 0.0 Lamps=off Galil=off
        """
        # lowerify everything
        # print("M2 reply: ", replyStr)
        try:
            replyStr = replyStr.strip().lower()
            if replyStr == "ok":
                # ok returned from a move, do nothing
                return
            else:
                # must be a status to parse
                for statusBit in replyStr.split():
                    key, val = statusBit.split("=")
                    if key == "state":
                        if val == "error":
                            print("Error from M2: %s"%replyStr)
                        else:
                            val = val.title()
                            self.state = val
                    elif key == "ori":
                        key = "orientation"
                        self.orientation = [float(x) for x in val.split(",")]
                        assert len(self.orientation) == 5
                    elif key == "galil":
                        assert val in validGalilStates
                        self.galil = val
        except:
            print("Error trying to parse M2 response: %s"%replyStr)
            traceback.print_exc(file=sys.stdout)

class M2Fact(DeviceClientFactory):
    def buildProtocol(self, addr):
        return M2Device()



