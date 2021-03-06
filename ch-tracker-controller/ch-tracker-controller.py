import sys
import time
import datetime
import argparse
import struct
import curses
import curses.textpad as textpad

import serial

import network_parser as hdlc;
import tracker

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

CT_SET_POSITION     = 0x01
CT_SET_MAX_SPEED    = 0x02
CT_SET_ACCEL        = 0x03
CT_SET_MOTOR_STATE  = 0x04

# motor defines
ELEVATION_STEPPER = 0
AZIMUTH_STEPPER = 1

ec1_tle = { "name": "ESTCUBE 1", \
            "tle1": "1 39161U 13021C   14067.20001811  .00002923  00000-0  49920-3 0  8912", \
            "tle2": "2 39161  98.1033 148.8368 0010183   4.6175 355.5121 14.69656997 44765"}

tallinn = ("59.4000", "24.8170", "0")

tracker = tracker.Tracker(satellite=ec1_tle, groundstation=tallinn)

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

        if time.time() - wait_ack_time > 0.02:
            return False, 'Error no ACK!'

def set_position(motor=0, absolute=True, move_degrees=1.1):
    move_degrees = move_degrees * 10 # scale with 10 to maintain floating point precision
    set_position_packet = struct.pack("<BBBh", CT_SET_POSITION, motor, absolute, move_degrees)
    send_packet(set_position_packet)
    result, msg = wait_ack()
    return result, msg

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
p.add_argument("-e", dest='enable', type=int, choices = [0,1], help="sets motor state {0 - off, 1 - on}")
p.add_argument("-k", dest='keyboard', help="use arrow keys to control azimuth and elevation", action="store_true")
p.add_argument("-t", dest='track', help="track automatically using TLE", action="store_true")

commands = []
command_index = 0
run_command = False

command_line_nr = 9

try:
    text_before_cursor = "command: "
    text_offset = len(text_before_cursor)
    cursor_position = [command_line_nr, text_offset]
    stdscr.addstr(0, 0, p.format_help())
    text = ''

    while 1:
        stdscr.move(command_line_nr, 0)
        stdscr.clrtoeol()
        stdscr.addstr(command_line_nr, 0, "%s%s" % (text_before_cursor, text))
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

            elif key == 10: # enter
                stdscr.move(command_line_nr + 1, 0)
                stdscr.insertln()
                stdscr.addstr(command_line_nr + 2, text_offset, text)
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
                stdscr.addstr(command_line_nr + 2, 30, p._error_message)
                continue

            msg = ""
            if pargs.position is not None:
                result, msg = set_position(pargs.motor, absolute=True, move_degrees=pargs.position)

            elif pargs.enable is not None:
                set_motor_state_packet = struct.pack("<BBB", CT_SET_MOTOR_STATE, pargs.motor, pargs.enable)
                send_packet(set_motor_state_packet)
                result, msg = wait_ack()

            elif pargs.track:
                stdscr.nodelay(1)
                start = time.time()
                while 1:
                    #d = datetime.datetime(2014, 06, 06, 17, 43, 30)
                    #t = time.mktime(d.timetuple()) + time.time() - start
                    #tracker.set_epoch(t)

                    tracker.set_epoch(time.time())
                    az = tracker.azimuth()
                    elev = tracker.elevation()

                    stdscr.move(command_line_nr + 2, 0)
                    stdscr.clrtoeol()
                    stdscr.addstr(command_line_nr + 2, text_offset, "azimuth %0.2f, elevation %0.2f, range %0.0f km" % (az, elev, tracker.range()/1000))

                    if az <= 180:
                        az = az
                    elif az > 180:
                        az = -(360 - az)

                    result, msg = set_position(AZIMUTH_STEPPER, absolute=True, move_degrees=az)

                    if elev > 0:
                        result, msg = set_position(ELEVATION_STEPPER, absolute=True, move_degrees=elev)

                    key = stdscr.getch()
                    if key == 27 or key == ord('q'):
                        break

                stdscr.nodelay(0)

            elif pargs.keyboard:
                while 1:
                    stdscr.move(command_line_nr, 0)
                    stdscr.clrtoeol()
                    stdscr.addstr(command_line_nr, 0, "%s%s" % (text_before_cursor, text))
                    stdscr.move(cursor_position[0], cursor_position[1])
                    key = stdscr.getch()
                    msg = ""
                    if key != -1:
                        if key == curses.KEY_UP:
                            result, msg = set_position(ELEVATION_STEPPER, absolute=False, move_degrees=1)
                            command_description = "up"
                        elif key == curses.KEY_DOWN:
                            result, msg = set_position(ELEVATION_STEPPER, absolute=False, move_degrees=-1)
                            command_description = "down"
                        elif key == curses.KEY_LEFT:
                            result, msg = set_position(AZIMUTH_STEPPER, absolute=False, move_degrees=1)
                            command_description = "left"
                        elif key == curses.KEY_RIGHT:
                            result, msg = set_position(AZIMUTH_STEPPER, absolute=False, move_degrees=-1)
                            command_description = "right"
                        elif key == 27 or key == ord('q'):
                            break

                        if msg:
                            msg = "| %s" % msg
                            stdscr.move(command_line_nr + 2, 0)
                            stdscr.clrtoeol()
                            stdscr.addstr(command_line_nr + 2, text_offset, command_description)
                            stdscr.addstr(command_line_nr + 2, 30, msg)

            if msg:
                msg = "| %s" % msg
                stdscr.addstr(command_line_nr + 2, 30, msg)

            run_command = False

finally:
    curses.nocbreak()
    stdscr.keypad(0)
    curses.echo()
    curses.endwin()
