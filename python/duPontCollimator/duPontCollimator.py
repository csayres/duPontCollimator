from __future__ import division, absolute_import

    def updateCollimation(self, cmd=None, force=False, target=False):
        """Update collimation based on info in obj, inst, weath blocks, for all mirrors present

        @param[in] cmd  command (twistedActor.BaseCmd) associated with this request;
            state will be updated upon completion; None if no command is associated
        """
        cmd = expandUserCmd(cmd)
            # print "updateCollimation"
        if not self.collimationModel.doCollimate and not force:
            cmd.setState(cmd.Failed, "collimation is disabled")
            return
        self.collimateTimer.cancel() # incase one is pending
        # query for current telescope coords
        statusCmd = self.tcsDev.getStatus()
        # when status returns determine current coords
        def moveMirror(statusCmd):
            if statusCmd.isDone:
                # ha = self.tcsDev.status.statusFieldDict["ha"].value
                # dec = self.tcsDev.status.statusFieldDict["dec"].value
                if target:
                    # get target coords
                    # st and ra in degrees
                    st = self.tcsDev.status.statusFieldDict["st"].value
                    ra = self.tcsDev.status.statusFieldDict["inpra"].value
                    ha = st - ra
                    dec = self.tcsDev.status.statusFieldDict["inpdc"].value
                    self.writeToUsers("i", "collimate for target ha=%.2f, dec=%.2f"%(ha, dec))
                else:
                    # get current coords
                    ha, dec = self.tcsDev.status.statusFieldDict["pos"].value
                    self.writeToUsers("i", "collimate for current ha=%.2f, dec=%.2f"%(ha, dec))
                # self.writeToUsers("i", "pos collimate for ha=%.2f, dec=%.2f"%(pos[0], pos[1]))
                newOrient = self.collimationModel.getOrientation(ha, dec, temp=None)
                currentOrient = self.secDev.status.orientation
                # check if mirror move is wanted based on tolerances
                dtiltX = numpy.abs(newOrient[0]-currentOrient[1])
                dtiltY = numpy.abs(newOrient[1]-currentOrient[2])
                dtransX = numpy.abs(newOrient[2]-currentOrient[3])
                dtransY = numpy.abs(newOrient[3]-currentOrient[4])
                if numpy.max([dtiltX, dtiltY]) > self.collimationModel.minTilt or numpy.max([dtransX, dtransY]) > self.collimationModel.minTrans:
                    self.writeToUsers("i", "collimation update: TiltX=%.2f, TiltY=%.2f, TransX=%.2f, TransY=%.2f"%tuple(newOrient), cmd=cmd)
                    focus = self.secDev.status.secFocus
                    newOrient = [focus] + list(newOrient)
                    self.secDev.move(newOrient, userCmd=cmd)
                else:
                    # collimation not wanted
                    self.writeToUsers("i", "collimation update too small")
                    cmd.setState(cmd.Done)
        statusCmd.addCallback(moveMirror)
