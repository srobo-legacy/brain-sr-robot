import usb1
import struct

class Battery(object):
    '''Interfaces with the battery to get current and voltage readings'''
    def __init__(self, handle):
        ''' Creates an interface to the battery via the serial handle provided'''
        self.handle = handle

    @property
    def voltage(self):
        '''Gets the voltage in V'''
        return round(self._get_vi()[0] / 1000.0, 2)

    @property
    def current(self):
        '''Gets the current in A'''
        return round(self._get_vi()[1] / 1000.0, 2)

    def _get_vi(self):
        '''Returns the voltage (mV) and current (mA)'''
    	result = self.handle.controlRead(0x80, 64, 0, Power.CMD_READ_batt, 8)
    	current, voltage = struct.unpack("ii", result)
    	return voltage, current

class Outputs(object):
    '''Interface to control the 6 outputs of the power board'''
    def __init__(self, handle):
        '''Creates an interface to the outputs via the serial handle provided'''
        self.handle = handle

    def __setitem__(self, index, value):
        '''Sets the power of the specified output on or off'''
    	if index > 5 or index < 0:
    		raise Exception("Setting out-of-range rail address")

    	if value:
    		val = True
    	else:
    		val = False

    	cmd = Power.CMD_WRITE_output0 + index
    	self.handle.controlWrite(0, 64, val, cmd, 0)


class Power:
    '''Class to interface with the power board, supports context management'''
    CMD_WRITE_output0 = 0
    CMD_WRITE_output1 = 1
    CMD_WRITE_output2 = 2
    CMD_WRITE_output3 = 3
    CMD_WRITE_output4 = 4
    CMD_WRITE_output5 = 5
    CMD_WRITE_runled = 6
    CMD_WRITE_errorled = 7
    CMD_WRITE_piezo = 8
    CMD_READ_output0 = 0
    CMD_READ_output1 = 1
    CMD_READ_output2 = 2
    CMD_READ_output3 = 3
    CMD_READ_output4 = 4
    CMD_READ_output5 = 5
    CMD_READ_5vrail = 6
    CMD_READ_batt = 7
    CMD_READ_button = 8

    def __init__(self, path, busnum, devnum, serialnum = None):
        '''Creates an interface to the power board

        Initiates a connection to the power board  

        Parameters
        ----------
        path : str
            Unused parameter
        busnum : int
            Bus number to find connection
        devnum : int
            Device Address to find connection
        serialnum : , optional
            The serial number of the power board (the default is None)
        '''
        self.serialnum = serialnum

    	self.ctx = usb1.USBContext()
        self.handle = None
        for dev in self.ctx.getDeviceList():
            if dev.getBusNumber() == busnum and dev.getDeviceAddress() == devnum:
                self.handle = dev.open()

        if self.handle is None:
            raise Exception("Failed to find power board even though it was enumerated")

        self.battery = Battery(self.handle)
        self.output = Outputs(self.handle)

    def __repr__(self):
        return "Power( serialnum = \"{0}\" )".format( self.serialnum )

    def set_run_led(self, status):
        '''Turns the run LED on or off'''
    	if status:
    		val = True
    	else:
    		val = False

    	self.handle.controlWrite(0, 64, val, Power.CMD_WRITE_runled, 0)

    def set_error_led(self, status):
        '''Turns the error LED on or off'''
    	if status:
    		val = True
    	else:
    		val = False

    	self.handle.controlWrite(0, 64, val, Power.CMD_WRITE_errorled, 0)

    def read_button(self):
        '''Returns whether the button is currently being pressed or not'''
    	result = self.handle.controlRead(0x80, 64, 0, Power.CMD_READ_button, 4)
    	status, = struct.unpack("i", result)
    	if status == 0:
    		return False
    	else:
    		return True
    
    def buzz_piezo(self, duration, frequency):
        '''Buzzes the piezo at the specified frequency for the specified duration'''
        data = struct.pack("HH", frequency, duration)
        self.handle.controlWrite(0, 64, 0, Power.CMD_WRITE_piezo, data)

    def beep(self, duration, note=None, frequency=None):
        '''Buzzes the pieze at the specified note or frequency for the specified duration'''
	notes = { 
	    'c': 261, 'd': 294, 'e': 329,
	    'f': 349, 'g': 392, 'a': 440,
	    'b': 493, 'uc': 523
	}
        if note is not None:
	    note_frequency = notes.get(note.lower())
	    if note_frequency is not None:
                self.buzz_piezo(duration, note_frequency)
            else:
                raise ValueError('{} is not a recognised note.'.format(note))
        elif frequency is not None:
            self.buzz_piezo(duration, frequency)
        else:
            raise ValueError('`note` must be either a recognised note character or `frequency` an integer frequency.')
