
import sys
import time
import datetime
from math import *

import ephem

# taken from: http://celestrak.com/NORAD/elements/cubesat.txt
ec1_tle = { "name": "ESTCUBE 1", \
            "tle1": "1 39161U 13021C   14067.20001811  .00002923  00000-0  49920-3 0  8912", \
            "tle2": "2 39161  98.1033 148.8368 0010183   4.6175 355.5121 14.69656997 44765"}

tallinn = ("59.4000", "24.8170", "0")

class Tracker():
    # http://stackoverflow.com/questions/15954978/ecef-from-azimuth-elevation-range-and-observer-lat-lon-alt

    def __init__(self, satellite, groundstation=("59.4000", "24.8170", "0")):

        self.groundstation = ephem.Observer()
        self.groundstation.lat = groundstation[0]
        self.groundstation.lon = groundstation[1]
        self.groundstation.elevation = int(groundstation[2])

        self.satellite = ephem.readtle(satellite["name"], satellite["tle1"], satellite["tle2"])

    def set_epoch(self, epoch=time.time()):
        ''' sets epoch when parameters are observed '''

        self.groundstation.date = datetime.datetime.utcfromtimestamp(epoch)
        self.satellite.compute(self.groundstation)

    def azimuth(self):
        ''' returns satellite azimuth in degrees '''
        return degrees(self.satellite.az)

    def elevation(self):
        ''' returns satellite elevation in degrees '''
        return degrees(self.satellite.alt)

    def latitude(self):
        ''' returns satellite latitude in degrees '''
        return degrees(self.satellite.sublat)

    def longitude(self):
        ''' returns satellite longitude in degrees '''
        return degrees(self.satellite.sublong)

    def range(self):
        ''' returns satellite range in meters '''
        return self.satellite.range

    def ecef_coordinates(self):
        ''' returns satellite earth centered cartesian coordinates
            https://en.wikipedia.org/wiki/ECEF
        '''
        x, y, z = self._aer2ecef(self.azimuth(), self.elevation(), self.range(), float(self.groundstation.lat), float(self.groundstation.lon), self.groundstation.elevation)
        return x, y, z

    def _aer2ecef(self, azimuthDeg, elevationDeg, slantRange, obs_lat, obs_long, obs_alt):

        #site ecef in meters
        sitex, sitey, sitez = llh2ecef(obs_lat,obs_long,obs_alt)

        #some needed calculations
        slat = sin(radians(obs_lat))
        slon = sin(radians(obs_long))
        clat = cos(radians(obs_lat))
        clon = cos(radians(obs_long))

        azRad = radians(azimuthDeg)
        elRad = radians(elevationDeg)

        # az,el,range to sez convertion
        south  = -slantRange * cos(elRad) * cos(azRad)
        east   =  slantRange * cos(elRad) * sin(azRad)
        zenith =  slantRange * sin(elRad)

        x = ( slat * clon * south) + (-slon * east) + (clat * clon * zenith) + sitex
        y = ( slat * slon * south) + ( clon * east) + (clat * slon * zenith) + sitey
        z = (-clat *        south) + ( slat * zenith) + sitez

        return x, y, z



if __name__ == "__main__":
    tracker = Tracker(satellite=ec1_tle, groundstation=tallinn)

    while 1:
        tracker.set_epoch(time.time())
        print "az   : %0.1f" % tracker.azimuth()
        print "ele  : %0.1f" % tracker.elevation()
        print "range: %0.0f km" % (tracker.range()/1000)

        time.sleep(0.5)

