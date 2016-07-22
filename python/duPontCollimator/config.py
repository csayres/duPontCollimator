from __future__ import division, absolute_import
import collections
import numpy

userPort = 5099
tcsHost = "c100tcs"
tcsPort = 4242
m2Host = "vinchuca"
m2Port = 52001
statusRefreshRate = 1 # seconds
minFocusMove = 5 # microns
minTipTilt = 1 # arcseconds
minTranslation = 10 # microns
focusInterval = 60 # seconds
focusPerDegC = 70 # um per degree C
focusPerDegElevation = 0 # um per degree elevation

baseOrientation = collections.OrderedDict((
    ("tip", 45.),
    ("tilt", 6.),
    ("X", 200.),
    ("Y", 0.),
))


def getFocus(focusZeroPoint, trussTempZeroPoint, currentTrussTemp, currentElevation):
    dtemp = trussTempZeroPoint - currentTrussTemp
    return focusZeroPoint + dtemp * focusPerDegC + currentElevation * focusPerDegElevation

def getCollimation(ha, dec):
    """Return the desired M2
    collimation tiltx, tilty, transx, transy
    for a given ha(deg), dec(deg)

    tip = rotation about x (star moves in y)
    tilt = rotation about y (star moves in x)

    tip and tilt are right hand rotations

    Hi,
    Here is a first pass at a full flexure model

                    CY         CX         CTP         CTL
                       microns                 arcsec
         1        -2.1      -300.8        1.14       6.45
    sin(dec+29) 1413        -132.1       29.03     -13.56
    cos(dec+29)  386.7       182.3        9.86      -4.28
    sin(ha)      -49.3      -589.6       -0.46       4.84
    cos(ha)     -487.1       141.1      -10.21      -1.09

    rms error    107         63          4           3

    -Povilas

    # new model with updated CY

    a cross term in y helps the fit and some systematics

            vec          cy          cx         ctp         ctl

             ONE      -272.9      -300.8       1.143       6.453
              sd         679      -132.1       29.03      -13.56
              cd       407.8       182.3       9.868      -4.282
              sh      -39.71      -589.6     -0.4648        4.84
              ch      -334.7       141.1      -10.21      -1.095
            sdch       833.6
            cdch       153.1

    rms                  58          63          4            3.

    """
    haRad = numpy.radians(ha)
    decRad = numpy.radians(dec+29)

    sinDec = numpy.sin(decRad)
    cosDec = numpy.cos(decRad)
    sinHA = numpy.sin(haRad)
    cosHA = numpy.cos(haRad)
    sinDecCosHA = numpy.sin(decRad)*numpy.cos(haRad)
    cosDecSinHA = numpy.cos(decRad)*numpy.sin(haRad)

    Y = -272.9 + 679*sinDec + 407.8*cosDec + -39.71*sinHA + -334.7*cosHA + 833.6*sinDecCosHA + 153.1*cosDecSinHA
    #Y = -2.141 + 1413*sinDec + 386.7*cosDec + -49.3*sinHA + -487.1*cosHA
    X = -300.8 + -132.1*sinDec + 182.3*cosDec + -589.6*sinHA + 141.1*cosHA
    tip = 1.14 + 29.03*sinDec + 9.86*cosDec + -0.46*sinHA + -10.21*cosHA
    tilt = 6.45 + -13.56*sinDec + -4.28*cosDec + 4.84*sinHA + -1.09*cosHA

    return collections.OrderedDict((
        ("tip", baseOrientation["tip"] - tip),
        ("tilt", baseOrientation["tilt"] - tilt),
        ("X", baseOrientation["X"] - X),
        ("Y", baseOrientation["Y"] - Y),
    ))
