import logging
import threading
import serial

SERIAL_BAUD = 1000000

CMD_RESET = chr(0)
CMD_VERSION = chr(1)
CMD_SPEED0 = chr(2)
CMD_SPEED1 = chr(3)
CMD_BOOTLOADER = chr(4)

SPEED_BRAKE = chr(2)

# The maximum value that the motor board will accept
PWM_MAX = 100

# The USB model string:
USB_MODEL = "MCV4B"

# The expected firmware version string
EXPECTED_FW_VER = "MCV4B:3\n"

logger = logging.getLogger( "sr.motor" )

class IncorrectFirmware(Exception):
    '''Exception for when incorrect firmware is found within a motor controller'''
    def __init__(self, serialnum, actual_fw):
        self.serialnum = serialnum
        self.actual_fw = actual_fw
        msg = "Found wrong firmware version in motor controller '{0}'.".format(serialnum) \
            + " Expecting '{0}', got '{1}'.".format(repr(EXPECTED_FW_VER), repr(actual_fw))
        super(IncorrectFirmware, self).__init__(msg)

class FirmwareReadFail(Exception):
    '''Exception for when reading the firmware of a motor controller fails'''
    def __init__(self, serialnum):
        self.serialnum = serialnum
        msg = "Failed to read firmware version from motor controller '{0}'.".format(serialnum) \
            + " Please ensure that it is powered properly."
        super(FirmwareReadFail, self).__init__(msg)

class Motor(object):
    '''Class to interface with a motor board, supports context management'''
    def __init__(self, path, busnum, devnum,
                 serialnum = None, check_fwver = True):
        ''' Creates an interface to a motor board

        Initiates a connection to a motor board via Serial communication

        Paramters
        ---------
        path : str
            The path to the serial device to commuicate with the motor board
        busnum : int
            Unused parameter
        devnum : int
            Unused parameter
        serialnum : , optional
            The serial number of the motor board (the default is None)
        check_fwver : bool, optional
            Whether or not to check the firmware of the motor board is as expected, throws IncorrectFirmware if set to True and firmware is not expected (the default is True, does check the firmware version)
        '''
        self.serialnum = serialnum
        self.serial = serial.Serial(path, SERIAL_BAUD, timeout=0.1)
        self.lock = threading.Lock()

        with self.lock:
            self.serial.write(CMD_RESET)

        fw = self._get_fwver()
        if check_fwver and fw != EXPECTED_FW_VER:
            self.close()
            raise IncorrectFirmware(self.serialnum, fw)

        self.m0 = MotorChannel(self.serial, self.lock, 0)
        self.m1 = MotorChannel(self.serial, self.lock, 1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceba):
        self.close()

    def close(self):
        '''Closes the serial communication with the motor'''
        self.serial.close()

    def _get_fwver(self):
        '''Attempts to get the firmware version of the motor, throws FirmwareReadFail exception if unsuccessful'''
        for x in range(10):
            # We make repeat attempts at reading the firmware version
            # because the motor controller may have only just been powered-up.

            with self.lock:
                self.serial.write(CMD_VERSION)
                r = self.serial.readline()

            if len(r) > 0 and r[-1] == "\n":
                "Successfully read the firmware version"
                return r

        raise FirmwareReadFail(self.serialnum)

    def __repr__(self):
        return "Motor( serialnum = \"{0}\" )".format( self.serialnum )

    def _jump_to_bootloader(self):
        '''Jumps to the bootloader'''
        MAGIC = "Entering bootloader\n"

        # Up the timeout to ensure bootloader response is received
        self.serial.timeout = 0.5

        with self.lock:
            self.serial.write(CMD_BOOTLOADER)

        # Check the command has been received
        r = self.serial.read( len(MAGIC) )

        if r != MAGIC:
            # There's not much we can do about this at the moment
            logger.warning("Incorrect bootloader entry string received")

        # Get rid of any junk that comes from the motor board
        # (we seem to get a null character coming through)
        self.serial.read()

class MotorChannel(object):
    '''Class to interface with a motor channel of a motor board'''
    def __init__(self, serial, lock, channel):
        '''Interface to a motor upon a motor board

        Description

        Paramters
        --------
        serial : Serial object
            The serial interface to the motor board
        lock : Lock object
            Threading lock object to block should another thread be using the interface
        channel : int
            The motor from the motor board to communicate with
        '''
        self.serial = serial
        self.lock = lock
        self.channel = channel

        # Private shadow of use_brake
        self._use_brake = True

        # There is currently no method for reading the power from a motor board
        self._power = 0

    def _encode_speed(self, speed):
        '''Encodes the speed (int)'''
        return chr(speed + 128)

    @property
    def power(self):
        '''Gets the power of the motor'''
        return self._power

    @power.setter
    def power(self, value):
        '''Sets the power of the motor'''
        value = int(value)
        self._power = value

        # Limit the value to within the valid range
        if value > PWM_MAX:
            value = PWM_MAX
        elif value < -PWM_MAX:
            value = -PWM_MAX

        with self.lock:
            if self.channel == 0:
                self.serial.write(CMD_SPEED0)
            else:
                self.serial.write(CMD_SPEED1)

            if value == 0 and self.use_brake:
                self.serial.write(SPEED_BRAKE)
            else:
                self.serial.write(self._encode_speed(value))

    @property
    def use_brake(self):
        '''Returns whether the brake is used when power of the motor is 0'''
        return self._use_brake

    @use_brake.setter
    def use_brake(self, value):
        '''Sets whether the brake is used when power of the motor is 0'''
        self._use_brake = value

        if self.power == 0:
            "Implement the new braking setting"
            self.power = 0
