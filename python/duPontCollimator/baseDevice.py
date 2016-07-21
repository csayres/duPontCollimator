from __future__ import division, absolute_import

from twisted.internet.protocol import Protocol, ClientFactory

#http://twistedmatrix.com/documents/12.1.0/core/howto/clients.html

class BaseDevice(Protocol):

    def dataReceived(self, data):
        # this is called everytime a line of data
        # is received from the device
        raise NotImplementedError("subclasses must override")

    def connectionMade(self):
        # this is called when the connection is established
        print("Connection Made")

    def writeToDevice(self, devString):
        # write a string to the device
        self.transport.write(devString)


class DeviceClientFactory(ClientFactory):
    def startedConnecting(self, connector):
        print('%s started to connect.'%self)

    def buildProtocol(self, addr):
        # print('%s connected.'%self)
        #return BaseDeviceProtocol()
        raise NotImplementedError("subclasses must override, returns a Protocol instance")

    def clientConnectionLost(self, connector, reason):
        print('%s cost connection.  Reason:' %self, reason)

    def clientConnectionFailed(self, connector, reason):
        print('%s connection failed. Reason:' %self, reason)
