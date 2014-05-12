import sys
import time
import argparse
import struct

import serial

import network_parser as hdlc;

parser = argparse.ArgumentParser(description="Cubehub antenna tracker controller", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--port", type=str, default="/dev/tty.usbmodem621", help="usb serial port device eg. /dev/ttyUSB0")
args = parser.parse_args()

s = serial.Serial(args.port, 115200, timeout=0.01);
#time.sleep(2.) # Arduino resets automatically if port is opened

s.flushInput()
s.flushOutput()

parser = hdlc.NetworkParserChecksummed()

# packet types
TC_ACK = 0x00

CT_SET_CONFIG = 0x01
CT_SET_POSITION = 0x02

CT_GET_CONFIG = 0x03
TC_CONFIG = 0x30

# motor defines
ELEVATION_STEPPER = 0
AZIMUTH_STEPPER = 1

def send_packet(data):
    data = hdlc.add_checksum(data)
    data = hdlc.escape_delimit(data)
    print 'out: %s' % (data.encode('hex'))
    s.write(data)

def wait_ack():
    wait_ack_time = time.time()

    while 1:
        data = s.read(20)
        if data:
            #print 'raw in      : %s' % (data.encode('hex'))
            #print 'raw in ascii: %s' % (data)
            parser.put(data)

        for packet in parser:
            print 'in: %s' % (packet.encode('hex'))
            header, status, line = struct.unpack("<BBH", packet[:4])
            if header == TC_ACK:
                print 'ACK status %u, line %u' % (status, line)
                return True

        if time.time() - wait_ack_time > 0.1:
            print 'Error no ACK!'
            return False

class ArgumentException(Exception):
    pass

class ArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        ''' do exit in case of error, just show help again '''
        self.print_usage()
        raise ArgumentException

p = ArgumentParser(prog="", add_help=False)
p.add_argument("--motor", "-m", type=int, required=True, choices = [0,1], help="select which motor to control {0 - elevation, 1 - azimuth}")
p.add_argument("--position", "-p", metavar="DEGREE", type=int, help="sets motor position in degrees")
p.print_help()

while 1:
    arguments = raw_input('command: ')

    try:
        pargs = p.parse_args(arguments.split())
    except ArgumentException:
        continue

    if pargs.position:
        set_position_packet = struct.pack("<BBh", CT_SET_POSITION, pargs.motor, pargs.position)

        send_packet(set_position_packet)
        wait_ack()

