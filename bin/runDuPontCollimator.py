#!/usr/bin/env python
from twisted.internet import reactor

# note: must add the packageDirectory/python to the PYTHONPATH env var
reactor.connectTCP(host, port, EchoClientFactory())