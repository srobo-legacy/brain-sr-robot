import logging
import threading
import serial

SERIAL_BAUD = 115200

# Strings here so that they print nicely
INPUT = "INPUT"
OUTPUT = "OUTPUT"
INPUT_PULLUP = "INPUT_PULLUP"

COMMAND_RETRIES = 10

logger = logging.getLogger( "sr.ruggeduino" )

class IgnoredRuggeduino(object):
    def __init__(self, path, serialnum):
        self.path = path
        self.serialnum = serialnum

    def __repr__(self):
        return "IgnoredRuggeduino( serialnum = \"{0}\" )".format( self.serialnum )

class RuggeduinoCmdBase(object):
    '''Base class for talking to a Ruggeduino that supports the SR command protocol'''
    def __init__(self, path):
        '''Initiates communication with the Ruggeduino using Serial communication with the specified path'''
        self.serial = serial.Serial(path, SERIAL_BAUD, timeout=0.1)

        # Lock that must be acquired for use of the serial device
        self.lock = threading.Lock()

    def close(self):
        '''Closes the serial communication with the Ruggeduino'''
        self.serial.close()

    def command(self, data):
        '''Send a command to the Ruggeduino and return the response.

        Writes the command data as bytes to the serial connection, then
        reads a line of returned data. In the even that the read does not
        contain anything useful (ie has zero size or doesn't end with a
        newline character) then retry up to COMMAND_RETRIES times.

        Returns the response from the device.'''

        # The lock must have been acquired to talk to the device
        assert self.lock.locked(), "Must acquire lock to talk to ruggeduino"

        command = bytes(data)
        for i in range(COMMAND_RETRIES):
            self.serial.write(command)
            res = self.serial.readline()
            if len(res) > 0 and res[-1] == "\n":
                return res
        raise Exception("Communications with Ruggeduino failed for "
                      + "command '{0}'.".format(command))

    def firmware_version_read(self):
        '''Returns the firmware version from the device'''

        with self.lock:
            return self.command('v')

class Ruggeduino(RuggeduinoCmdBase):
    '''Class for talking to a Ruggeduino flashed with the SR firmware'''
    def __init__(self, path, serialnum = None):
        '''Initialises communication with the Ruggeduino and checks that it has SR firmware'''
        RuggeduinoCmdBase.__init__(self, path)
        self.serialnum = serialnum

        if not self._is_srduino():
            logger.warning( "Ruggeduino is not running the SR firmware" )

    def _is_srduino(self):
        '''Returns whether the board is flashed with the SR firmware'''
        v = self.firmware_version_read()

        if v.split(":")[0] == "SRduino":
            return True
        else:
            return False

    def _encode_pin(self, pin):
        '''Returns an encoded pin number in ascii'''
        return chr(ord('a') + pin)

    def pin_mode(self, pin, mode):
        '''Set the mode of a pin'''
        MODES = {INPUT: 'i',
                 OUTPUT: 'o',
                 INPUT_PULLUP: 'p'}
        with self.lock:
            self.command(MODES[mode] + self._encode_pin(pin))

    def digital_read(self, pin):
        '''Returns the state of a digital input pin'''
        with self.lock:
            response = self.command('r' + self._encode_pin(pin))
            return True if response[0] == 'h' else False

    def digital_write(self, pin, level):
        '''Writes to an output pin'''
        with self.lock:
            self.command(('h' if level else 'l') + self._encode_pin(pin))

    def analogue_read(self, pin):
        '''Returns the value from an analogue input pin'''
        with self.lock:
            response = self.command('a' + self._encode_pin(pin))
        return (int(response)/1023.0)*5.0

    def __repr__(self):
        return "Ruggeduino( serialnum = \"{0}\" )".format( self.serialnum )
