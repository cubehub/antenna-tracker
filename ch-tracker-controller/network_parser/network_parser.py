"""
# parse incoming network-data

# handles stream framing and escaping.
# http://en.wikipedia.org/wiki/High-Level_Data_Link_Control
# paragraph: Asynchronous framing

usage:

import network_parser

# 000303320037017D
p1 = "\x00\x03\x03\x32\x00\x37\x01\x7D"
p2 = network_parser.add_checksum(p1)
p3 = network_parser.escape_delimit(p2)

print "original   :", network_parser._repr(p1)
print "checksummed:", network_parser._repr(p2)
print "escapedelim:", network_parser._repr(p3)

#np = network_parser.NetworkParser()
#np.add("")

"""

import logging
log = logging.getLogger(__name__)

def escape_delimit(s):
    """
    escapes bytes 0x7e, 0x7d, 0x11 (XON), 0x13 (XOFF)
    0x7e and 0x7d will be escaped to 0x7d 0x5e and 0x7d 0x5d
    0x11 and 0x13 will be escaped to 0x7d 0x31 and 0x7d 0x33

    0x7e - packet start/end
    0x7d - escape character. escapes the following byte by inverting bit 5.

    example:
         40 09 00 be ef 05 7d    06 01 02 03 04 05
    becomes:
      7e 40 09 00 be ef 05 7d 5d 06 01 02 03 04 05 7e
    """
    r = []
    r.append(chr(0x7e))
    for c in s:
        cc = ord(c)
        if cc == 0x7d or cc == 0x7e or cc == 0x11 or cc == 0x13:
            r.append(chr(0x7d))
            r.append(chr(cc ^ 32))
        else:
            r.append(c)
    r.append(chr(0x7e))
    return "".join(r)


def de_escape(s):
    """
    example:
      7e 40 09 00 be ef 05 7d 5d 06 7d 1e 03 04 05 7e
    becomes:
      7e 40 09 00 be ef 05    7d 06    3e 03 04 05 7e
    """
    r = []
    next_byte_inverted = False
    for c in s:
        if ord(c) == 0x7d:
            next_byte_inverted = True
        else:
            if next_byte_inverted:
                next_byte_inverted = False
                c = chr(ord(c) ^ 32) # xor bit 5
            r.append(c)
    return "".join(r)

def de_escape_delimit(s):
    if ord(s[0]) == 0x7e and ord(s[-1]) == 0x7e:
        return de_escape(s[1:-1])
    return None


def de_checksum(s):
    """
    return s with checksum stripped if cheksum ok.
    return empty string otherwise.
    """
    if len(s) < 2: return ""
    checksum = ord(s[-1])
    s = s[:-1]
    localchecksum = sum([ord(c) for c in s]) & 255
    if localchecksum != checksum: return ""
    return s


def add_checksum(s):
    """
    return s with checksum char appended
    """
    return s + chr(sum([ord(c) for c in s]) & 255)

def crc16(s):
    """
    Compute ITU-T CRC16
    """
    crc = 0
    for b in s:
        b = ord(b)
        crc = crc ^ (b << 8)
        for i in range(0, 8):
            if crc & 0x8000 == 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc = crc & 0xffff
    return crc

def add_crc16(s):
    """
    Returns input with CRC16.
    """
    crc = crc16(s)
    return s + chr(crc & 0xFF) + chr((crc >> 8) & 0xFF)

def crc_checked(s):
    """
    Checks CRC and returns packet without CRC if check passed. None otherwise.
    """
    if len(s) > 2:
        crc = crc16(s[:-2])
        crc_packet = ord(s[-1]) << 8 | ord(s[-2])
        if crc == crc_packet:
            return s[:-2]
    return None

def _repr(s):
    """ return hexadecimal representation of a string
    '-/=+!!!!@@' -> '2D2F3D2B 21212121 4040'
    """
    return "".join(["%02X" % ord(c) for c in s]).rstrip()
    #return "".join(["%02X" % ord(c) + " "*(i%4==3) for i, c in enumerate(s)]).rstrip()


# TODO: de-escape and packet-partitioning at the same time

class NetworkParserChecksummed(object):
    def __init__(self):
        self.buf       = ""
        self.delimiter = chr(0x7e)

    def put(self, data):
        self.buf += data

    def __iter__(self):
        return self

    def next(self):
        t = self._get_deframed_packet()
        return t

    def _get_deframed_packet(self):
        """
        find packets in the stream.
        return checksum-passed delimited/deframed packet contents.
        """
        #print "in parser:", len(self.buf)
        while True:
            self.delete = self.buf.find( self.delimiter )
            if self.delete == -1: raise StopIteration

            t = self.buf[:self.delete]
            self.buf = self.buf[self.delete+1:]

            # do not return empty packets. delimiter-stream generates no events.
            if not t: continue

            s  = de_escape(t)
            s2 = de_checksum(s)
            if not s2:
                log.info("packet checksum error. raw stream (without start/end 0x7e) (len %i payloadlen %i):\n'%s'" % (len(t), len(s), _repr(t)))
                #print "packet checksum error. raw stream without packet start/end 0x7e (len %i):\n'%s'" % (len(s), _repr(s))
                #print "netparse %3i: %s" % (len(self.buf), _repr(self.buf))
                continue

            return s2

class NetworkParserCRC(NetworkParserChecksummed):

    def __init__(self):
        super(NetworkParserCRC, self).__init__()

    def _get_deframed_packet(self):
        while True:
            self.delete = self.buf.find( self.delimiter )
            if self.delete == -1: raise StopIteration

            t = self.buf[:self.delete]
            self.buf = self.buf[self.delete+1:]

            # do not return empty packets. delimiter-stream generates no events.
            if not t: continue

            s  = de_escape(t)
            s2 = crc_checked(s)
            if not s2:
                log.info("packet crc error. raw stream (len %i payloadlen %i):'%s'" % (len(t), len(s), _repr(t)))
                continue

            return s2



