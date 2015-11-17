import usb1
import struct

class Battery(object):
    def __init__(self, handle):
        self.handle = handle

    @property
    def voltage(self):
        """Voltage in Volts"""
        return round(self._get_vi()[0] / 1000.0, 2)

    @property
    def current(self):
        """Current in Amps"""
        return round(self._get_vi()[1] / 1000.0, 2)

    def _get_vi(self):
    	""" Measured in mA and mV"""
    	result = self.handle.controlRead(0x80, 64, 0, Power.CMD_READ_batt, 8)
    	current, voltage = struct.unpack("ii", result)
    	return voltage, current

class Outputs(object):
    def __init__(self, handle):
        self.handle = handle

    def __setitem__(self, index, value):
    	if index > 5 or index < 0:
    		raise Exception("Setting out-of-range rail address")

    	if value:
    		val = True
    	else:
    		val = False

    	cmd = Power.CMD_WRITE_output0 + index
    	self.handle.controlWrite(0, 64, val, cmd, 0)


class Power:
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
    	if status:
    		val = True
    	else:
    		val = False

    	self.handle.controlWrite(0, 64, val, Power.CMD_WRITE_runled, 0)

    def set_error_led(self, status):
    	if status:
    		val = True
    	else:
    		val = False

    	self.handle.controlWrite(0, 64, val, Power.CMD_WRITE_errorled, 0)

    def read_button(self):
    	result = self.handle.controlRead(0x80, 64, 0, Power.CMD_READ_button, 4)
    	status, = struct.unpack("i", result)
    	if status == 0:
    		return False
    	else:
    		return True
    
    def buzz_piezo(self, duration, frequency):
        data = struct.pack("HH", frequency, duration)
        self.handle.controlWrite(0, 64, 0, Power.CMD_WRITE_piezo, data)

    def enqueue_beeps(self, beeps):
        data = ""
        for duration, frequency in beeps:
            data += struct.pack("HH", frequency, duration)
        self.handle.controlWrite(0, 64, 0, Power.CMD_WRITE_piezo, data)

    @staticmethod
    def note_to_freq(notestr):
	notes = { 
	    'c': 261, 'd': 294, 'e': 329,
	    'f': 349, 'g': 392, 'a': 440,
	    'b': 493, 'uc': 523
	}

        try:
            return notes[notestr]
        except KeyError:
            raise ValueError('{} is not a recognised note.'.format(notestr))

    def beep(self, duration, note=None, frequency=None):
        """Emit one or more beeps from the power board.

        This function supports three types of beeping:

        1) Single beep, described with a note string: beep(100, note="a")

        2) Single beep, described with a frequency:  beep(100, frequency=440)

        3) Multiple beeps, described with a sequence of (duration, note/frequency)
           tuples: beep( ((100,"a"), (200,"b"), (300, 440)) )"""

        if not hasattr(duration, "__iter__"):
            "We have been provided with a single beep to emit"
            if None not in (note,frequency):
                "A note and a frequency have been specified at the same time"
                raise ValueError("Note and frequency specified for beep")

            if note is not None:
                beeps = ((duration, note),)
            elif frequency is not None:
                beeps = ((duration, frequency),)
            else:
                beeps = ((duration, 440),)

        elif note is not None or frequency is not None:
            "note arguments provided along with frequency arguments"
            raise ValueError("Invalid argument combination: Beep list provided with note and frequency arguments.")

        else:
            "We have a list of beeps"
            beeps = duration

        output_beeps = []

        for duration, freq_desc in beeps:
            "Convert all 'notes' into frequencies"

            if isinstance(freq_desc, str):
                freq = self.note_to_freq(freq_desc)
            else:
                freq = int(freq_desc)

            output_beeps.append( (int(duration), freq) )

        self.enqueue_beeps(output_beeps)
