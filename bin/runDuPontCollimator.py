from twisted.internet import reactor, defer
from twisted.internet.endpoints import TCP4ClientEndpoint

from duPontCollimator import config, tcsDevice, m2Device

tcsDev = None
m2Dev = None

def tcsConnected(protocol):
    # called when connected
    global tcsDev
    tcsDev = protocol # a TCSDevice

def m2Connected(protocol):
    # called when connected
    global m2Dev
    m2Dev = protocol # a M2Device

def bothConnected(result):
    for (success, value) in result:
        if not success:
            print("Connection failure: %s"%value.getErrorMessage())
            reactor.stop()
            break
    else:
        print("Both connections ok...starting server")

# begin connection to tcs
point = TCP4ClientEndpoint(reactor, config.tcsHost, config.tcsPort)
dTCS = point.connect(tcsDevice.TCSFact())
dTCS.addCallback(tcsConnected)

# begin connection to M2
point = TCP4ClientEndpoint(reactor, config.m2Host, config.m2Port)
dM2 = point.connect(m2Device.M2Fact())
dM2.addCallback(m2Connected)

# when both are connected
# construct the server
dl = defer.DeferredList([dM2, dTCS])
dl.addCallback(bothConnected)

reactor.run()