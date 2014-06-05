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

CT_SET_POSITION     = 0x01
CT_SET_MAX_SPEED    = 0x02
CT_SET_ACCEL        = 0x03
CT_SET_MOTOR_STATE  = 0x04

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

        if time.time() - wait_ack_time > 0.02:
            return False, 'Error no ACK!'

def set_position_with_keyboard(motor=0, move_degrees=1):
    absolute = 0
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

commands = []
command_index = 0
run_command = False

try:
    text_before_cursor = "command: "
    text_offset = len(text_before_cursor)
    cursor_position = [7, text_offset]
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

            elif key == 10: # enter
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
                is_absolute = 1
                set_position_packet = struct.pack("<BBBh", CT_SET_POSITION, pargs.motor, is_absolute, pargs.position)
                send_packet(set_position_packet)
                result, msg = wait_ack()
            elif pargs.enable is not None:
                set_motor_state_packet = struct.pack("<BBB", CT_SET_MOTOR_STATE, pargs.motor, pargs.enable)
                send_packet(set_motor_state_packet)
                result, msg = wait_ack()
            elif pargs.keyboard:
                while 1:
                    stdscr.move(7, 0)
                    stdscr.clrtoeol()
                    stdscr.addstr(7, 0, "%s%s" % (text_before_cursor, text))
                    stdscr.move(cursor_position[0], cursor_position[1])
                    key = stdscr.getch()
                    msg = ""
                    if key != -1:
                        if key == curses.KEY_UP:
                            result, msg = set_position_with_keyboard(ELEVATION_STEPPER, move_degrees=1)
                            command_description = "up"
                        elif key == curses.KEY_DOWN:
                            result, msg = set_position_with_keyboard(ELEVATION_STEPPER, move_degrees=-1)
                            command_description = "down"
                        elif key == curses.KEY_LEFT:
                            result, msg = set_position_with_keyboard(AZIMUTH_STEPPER, move_degrees=1)
                            command_description = "left"
                        elif key == curses.KEY_RIGHT:
                            result, msg = set_position_with_keyboard(AZIMUTH_STEPPER, move_degrees=-1)
                            command_description = "right"
                        elif key == 27 or key == ord('q'):
                            break

                        if msg:
                            msg = "| %s" % msg
                            stdscr.move(9, 0)
                            stdscr.clrtoeol()
                            stdscr.addstr(9, text_offset, command_description)
                            stdscr.addstr(9, 30, msg)


            if msg:
                msg = "| %s" % msg
                stdscr.addstr(9, 30, msg)

            run_command = False

finally:
    curses.nocbreak()
    stdscr.keypad(0)
    curses.echo()
    curses.endwin()
