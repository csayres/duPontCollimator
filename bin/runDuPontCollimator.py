#!/usr/bin/env python
from twisted.internet import reactor

import duPontCollimator.tcsDevice

# note: must add the packageDirectory/python to the PYTHONPATH env var
duPontCollimator.tcsDevice.connectTCS()

reactor.run()