import sys
import time
import argparse
import struct
import curses
import curses.textpad as textpad

import serial

import network_parser as hdlc;

parser = argparse.ArgumentParser(description="Cubehub antenna tracker controller", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--port", type=str, default="/dev/tty.usbmodem621", help="usb serial port device eg. /dev/ttyUSB0")
args = parser.parse_args()

stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
stdscr.keypad(1)

s = serial.Serial(args.port, 115200, timeout=0.01);
time.sleep(2.) # Arduino resets automatically if port is opened

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
    s.write(data)

def wait_ack():
    wait_ack_time = time.time()

    while 1:
        data = s.read(20)
        if data:
            parser.put(data)

        for packet in parser:
            header, status, line = struct.unpack("<BBH", packet[:4])
            if header == TC_ACK:
                return True, 'ACK status %u, line %u' % (status, line)

        if time.time() - wait_ack_time > 0.1:
            return False, 'Error no ACK!'

class ArgumentException(Exception):
    pass

class ArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        ''' do exit in case of error, just show help again '''
        #self.print_usage()
        self._error_message = message
        raise ArgumentException

p = ArgumentParser(prog="", add_help=False)
p.add_argument("-m", dest='motor', type=int, choices = [0,1], help="select which motor to control {0 - elevation, 1 - azimuth}")
p.add_argument("-p", dest='position', metavar="DEGREE", type=int, help="sets motor position in degrees")
#p.print_help()


commands = []
command_index = 0
run_command = False

text_before_cursor = "command: "
text_offset = len(text_before_cursor)
cursor_position = [7, text_offset]
try:
    stdscr.addstr(0, 0, p.format_help())
    text = ''

    while 1:
        stdscr.move(7, 0)
        stdscr.clrtoeol()
        stdscr.addstr(7, 0, "%s%s" % (text_before_cursor, text))
        stdscr.move(cursor_position[0], cursor_position[1])

        key = stdscr.getch()
        if key != -1:
            if key <= 126 and key != 10:
                text = text[:cursor_position[1]-text_offset] + chr(key) + text[cursor_position[1]-text_offset:]
                cursor_position[1] += 1

            elif key == 127 or key == 8: # delete
                if cursor_position[1] != text_offset:
                    text = text[:cursor_position[1]-text_offset-1] + text[cursor_position[1]-text_offset:]
                    cursor_position[1] -= 1
                    if cursor_position[1] < text_offset:
                        cursor_position[1] = text_offset

            elif key == 10:
                stdscr.move(8, 0)
                stdscr.insertln()
                stdscr.addstr(9, text_offset, text)
                commands.insert(0, text)
                command_index = -1
                cursor_position[1] = text_offset
                run_command = True

            elif key == curses.KEY_UP:
                if len(commands):
                    command_index +=1
                    if command_index >= len(commands):
                        command_index = len(commands) - 1
                    text = commands[command_index]

            elif key == curses.KEY_DOWN:
                if len(commands):
                    command_index -= 1
                    if command_index < 0:
                        command_index = 0
                    text = commands[command_index]

            elif key == curses.KEY_LEFT:
                cursor_position[1] -= 1
                if cursor_position[1] < text_offset:
                    cursor_position[1] = text_offset

            elif key == curses.KEY_RIGHT:
                cursor_position[1] += 1
                if cursor_position[1] > text_offset + len(text):
                    cursor_position[1] = text_offset + len(text)


        if run_command:
            try:
                pargs = p.parse_args(text.split())
                text = ''
            except ArgumentException:
                stdscr.addstr(9, 30, p._error_message)
                continue

            msg = ""
            if pargs.position is not None:
                set_position_packet = struct.pack("<BBh", CT_SET_POSITION, pargs.motor, pargs.position)
                send_packet(set_position_packet)
                result, msg = wait_ack()

            if msg:
                msg = "| %s" % msg
                stdscr.addstr(9, 30, msg)

            run_command = False

finally:
    curses.nocbreak()
    stdscr.keypad(0)
    curses.echo()
    curses.endwin()
