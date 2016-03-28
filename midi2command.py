#!/usr/bin/env python
#
# midi2command.py
#
"""
Kill all Processing processes when the kill MIDI message is received, and restart them.
"""

import logging
import shlex
import subprocess
import sys
import time
import os

import psutil
import rtmidi
from rtmidi.midiutil import open_midiport
from rtmidi.midiconstants import *

MIDI_BUS_CONFIGURATION_EMERGENCY_CONTROL   = "Bus 1"
MIDI_BUS_CONFIGURATION_GUITAR_WING         = "Livid Guitar Wing"
MIDI_BUS_CONFIGURATION_ABLETON_IN_VOICE_FX = "Bus 2"
MIDI_BUS_CONFIGURATION_ABLETON_OUT         = "Bus 3"
MIDI_BUS_CONFIGURATION_ABLETON_IN_GTR      = "Bus 5 - GTR"
MIDI_BUS_CONFIGURATION_AUDIO_INTERFACE_OUT = "Fast Track Ultra 8R"

MIDI_REINIT_CHANNEL            = 7
MIDI_REINIT_PITCH              = 46
STROBOT_REINIT_CHANNEL         = 7
STROBOT_REINIT_PITCH           = 47
STROBOT_PATH                   = "/Applications/Strobot/Strobot.app/Contents/MacOS/Strobot"

STATUS_CC                      = 0xB0
STATUS_NOTE_ON                 = 0x90
STATUS_NOTE_OFF                = 0x80
STATUS_PC                      = 0xC0

OUTPUT_CHANNEL_KEMPER_AMP      = 3        #For reference, the VoiceLive is configured to listen on Channel 2
OUTPUT_CHANNEL_ABLETON_VOICEFX = 5

ABLETON_VOICE_FX_CTRL_CHANNEL  = 0
ABLETON_GTR_CTRL_CHANNEL       = 1

REINIT_CALL                    = False

log = logging.getLogger('midi2command')


class Command(object):
    def __init__(self, name='', description='', status=0xB0, channel=None,
            data=None, command=None):
        self.name = name
        self.description = description
        self.status = status
        self.channel = channel
        self.command = command

        if data is None or isinstance(data, int):
            self.data = data
        elif hasattr(data, 'split'):
            self.data = map(int, data.split())
        else:
            raise TypeError("Could not parse 'data' field.")


class MidiInputHandler_emergencyControl_Strobot(object):
    def __init__(self, inputPort):
        self.port = inputPort
        self._wallclock = time.time()

    def __call__(self, event, data=None):
        event, deltatime = event
        if event[0] < 0xF0:
            channel = (event[0] & 0xF)
            status = event[0] & 0xF0
        else:
            status = event[0]
            channel = None

        data1 = data2 = None
        num_bytes = len(event)
        if num_bytes >= 2:
            data1 = event[1]
        if num_bytes >= 3:
            data2 = event[2]
        
        # Add 1 to channel (Ch 1 is coded ass Ch 0)
        if channel + 1 == STROBOT_REINIT_CHANNEL and data1 == STROBOT_REINIT_PITCH and data2 != 0:
            self.execute_strobot_reinit_script()


    def execute_strobot_reinit_script(self):
        log.debug("--- EXECUTING STROBOT REINITIALISATION SCRIPT ! ---")
        PROCNAME1 = "Strobot"
        
        for proc in psutil.process_iter():
            if PROCNAME1 in str(proc.name):
                log.debug("Found the process corresponding to Strobot : " + str(proc.name) + " /// PID = " + str(proc.pid))
                proc.kill()

        time.sleep(2)      # Wait 2 seconds before restarting the main process
        #Reopen Strobot
        p1 = subprocess.Popen(STROBOT_PATH, shell=True).pid

    def close(self):
        pass

class MidiInputHandler_emergencyControl_MIDI(object):
    def __init__(self, inputPort, abletonOut):
        self.port = inputPort
        self._wallclock = time.time()
        self.midiout_abletonOut = abletonOut
        self.midiport_guitarWing_available = False
        self.midiport_abletonInGtr_available = False
        self.midiport_audioItf_available = False
        self.reinitialize_midiinputs()

    def __call__(self, event, data=None):
        event, deltatime = event
        if event[0] < 0xF0:
            channel = (event[0] & 0xF)
            status = event[0] & 0xF0
        else:
            status = event[0]
            channel = None

        data1 = data2 = None
        num_bytes = len(event)
        if num_bytes >= 2:
            data1 = event[1]
        if num_bytes >= 3:
            data2 = event[2]
        
        # Add 1 to channel (Ch 1 is coded ass Ch 0)
        if channel + 1 == MIDI_REINIT_CHANNEL and data1 == MIDI_REINIT_PITCH and data2 != 0:
            log.info("Reinitialize the necessary MIDI inputs/outputs")
            global REINIT_CALL
            REINIT_CALL = True

        if channel + 1 == STROBOT_REINIT_CHANNEL and data1 == STROBOT_REINIT_PITCH and data2 != 0:
            self.execute_strobot_reinit_script()


    def execute_strobot_reinit_script(self):
        log.debug("--- EXECUTING STROBOT REINITIALISATION SCRIPT ! ---")
        PROCNAME1 = "Strobot"
        
        for proc in psutil.process_iter():
            if PROCNAME1 in str(proc.name):
                log.debug("Found the process corresponding to Strobot : " + str(proc.name) + " /// PID = " + str(proc.pid))
                proc.kill()

        time.sleep(2)      # Wait 2 seconds before restarting the main process
        #Reopen Strobot
        p1 = subprocess.Popen(STROBOT_PATH, shell=True).pid

    def reinitialize_midiinputs(self):

        # If the ports are already open, close them before reopening them
        if self.midiport_guitarWing_available:
            self.midiin_guitarWing.close_port()
            # del self.midiin_guitarWing
        if self.midiport_audioItf_available:
            self.midiout_audioItf.close_port()
            # del self.midiout_audioItf
        self.midiport_guitarWing_available = False
        self.midiport_audioItf_available = False

        global MIDI_BUS_CONFIGURATION_EMERGENCY_CONTROL
        global MIDI_BUS_CONFIGURATION_GUITAR_WING
        global MIDI_BUS_CONFIGURATION_ABLETON_IN_VOICE_FX
        global MIDI_BUS_CONFIGURATION_ABLETON_OUT
        global MIDI_BUS_CONFIGURATION_ABLETON_IN_GTR
        global MIDI_BUS_CONFIGURATION_AUDIO_INTERFACE_OUT
        #Try to initialize the MIDI ports which might not be available all the time
        try:
            self.midiin_guitarWing, self.port_name_guitarWing     = open_midiport(MIDI_BUS_CONFIGURATION_GUITAR_WING, type_ = "input", interactive=False)
            self.midiport_guitarWing_available = True
        except (ValueError):
            log.info("Input Guitar Wing MIDI port unavailable")

        if self.midiport_abletonInGtr_available == False:
            try:
                self.midiin_abletonInGtr, self.port_name_abletonInGtr = open_midiport(MIDI_BUS_CONFIGURATION_ABLETON_IN_GTR, type_ = "input", interactive=False)
                self.midiport_abletonInGtr_available = True
            except (ValueError):
                log.info("Input Ableton Gtr MIDI port unavailable")

        try:
            self.midiout_audioItf, self.port_name_audioItf        = open_midiport(MIDI_BUS_CONFIGURATION_AUDIO_INTERFACE_OUT, type_ = "output", interactive=False)
            self.midiport_audioItf_available = True
        except (ValueError):
            log.info("Output Audio interface MIDI port unavailable")

        if self.midiport_guitarWing_available:
            self.midiin_guitarWing.set_callback(MidiInputHandler_guitarWing(self.midiin_guitarWing, self.midiout_abletonOut))
            log.info(" *** Guitar Wing callback is attached")
        else:
            log.info(" ###### Unable to attach the Guitar Wing callback, send a MIDI reinit command once the Guitar Wing is connected")

        if self.midiport_abletonInGtr_available and self.midiport_audioItf_available:
            self.midiin_abletonInGtr.set_callback(MidiInputHandler_abletonGtr(self.midiin_abletonInGtr, self.midiout_audioItf))
            log.info(" *** Guitar Amp control callback is attached")
        else:
            log.info(" ###### Unable to attach the Guitar Amp control callback, send a MIDI reinit command once the Audio interface is connected")

    def close(self):
        if hasattr(self, "midiin_guitarWing"):
            self.midiin_guitarWing.close_port()
            del self.midiin_guitarWing
        if hasattr(self, "midiout_audioItf"):
            self.midiout_audioItf.close_port()
            del self.midiout_audioItf
        if hasattr(self, "midiout_abletonOut"):
            self.midiout_abletonOut.close_port()
            del self.midiout_abletonOut
        if hasattr(self, "midiin_abletonInGtr"):
            self.midiin_abletonInGtr.close_port()
            del self.midiin_abletonInGtr


class MidiInputHandler_guitarWing(object):
    def __init__(self, portIn, portOut):
        self.portIn = portIn
        self.portOut = portOut
        self._wallclock = time.time()
        
        #Pitches for messages coming from the Guitar Wing
        self.PITCH_WING_BIG_ROUND_BUTTON_1 = 36
        self.PITCH_WING_BIG_ROUND_BUTTON_2 = 37
        self.PITCH_WING_BIG_ROUND_BUTTON_3 = 38
        self.PITCH_WING_BIG_ROUND_BUTTON_4 = 39
        self.PITCH_WING_ARROW_NEXT         = 40
        self.PITCH_WING_ARROW_PREVIOUS     = 41
        self.PITCH_WING_SMALL_RECTANGLE_1  = 42
        self.PITCH_WING_SMALL_RECTANGLE_2  = 43
        self.PITCH_WING_SMALL_RECTANGLE_3  = 44
        self.PITCH_WING_SMALL_RECTANGLE_4  = 45
        self.PITCH_WING_SMALL_SWITCH_1     = 46
        self.PITCH_WING_SMALL_SWITCH_2     = 47
        self.PITCH_WING_SMALL_SWITCH_3     = 48
        self.PITCH_WING_SMALL_SWITCH_4     = 49
        self.PITCH_TOGGLE                  = 4
        self.CC_SMALL_FADER_1              = 1
        self.CC_SMALL_FADER_2              = 2
        self.CC_BIG_FADER                  = 3

    def __call__(self, event, data=None):
        event, deltatime = event

        if event[0] < 0xF0:
            channel = (event[0] & 0xF)
            status = event[0] & 0xF0
        else:
            status = event[0]
            channel = None

        data1 = data2 = None
        num_bytes = len(event)
        if num_bytes >= 2:
            data1 = event[1]
        if num_bytes >= 3:
            data2 = event[2]

        if status == STATUS_NOTE_ON:
            if   data1 == self.PITCH_WING_BIG_ROUND_BUTTON_1:
                self.sendMidiOut_On_GuitarWing_BigRoundButton1()
            elif data1 == self.PITCH_WING_BIG_ROUND_BUTTON_2: 
                self.sendMidiOut_On_GuitarWing_BigRoundButton2()
            elif data1 == self.PITCH_WING_BIG_ROUND_BUTTON_3: 
                self.sendMidiOut_On_GuitarWing_BigRoundButton3()
            elif data1 == self.PITCH_WING_BIG_ROUND_BUTTON_4: 
                self.sendMidiOut_On_GuitarWing_BigRoundButton4()
            elif data1 == self.PITCH_WING_SMALL_RECTANGLE_1:  
                self.sendMidiOut_On_GuitarWing_SmallRectangle1()
            elif data1 == self.PITCH_WING_SMALL_RECTANGLE_2:  
                self.sendMidiOut_On_GuitarWing_SmallRectangle2()
            elif data1 == self.PITCH_WING_SMALL_RECTANGLE_3:  
                self.sendMidiOut_On_GuitarWing_SmallRectangle3()
            elif data1 == self.PITCH_WING_SMALL_RECTANGLE_4:  
                self.sendMidiOut_On_GuitarWing_SmallRectangle4()
            elif data1 == self.PITCH_TOGGLE:                  
                self.sendMidiOut_On_GuitarWing_Toggle()

        elif status == STATUS_NOTE_OFF:
            if   data1 == self.PITCH_WING_BIG_ROUND_BUTTON_1: 
                self.sendMidiOut_Off_GuitarWing_BigRoundButton1()
            elif data1 == self.PITCH_WING_BIG_ROUND_BUTTON_2: 
                self.sendMidiOut_Off_GuitarWing_BigRoundButton2()
            elif data1 == self.PITCH_WING_BIG_ROUND_BUTTON_3: 
                self.sendMidiOut_Off_GuitarWing_BigRoundButton3()
            elif data1 == self.PITCH_WING_BIG_ROUND_BUTTON_4: 
                self.sendMidiOut_Off_GuitarWing_BigRoundButton4()
            elif data1 == self.PITCH_TOGGLE:                  
                self.sendMidiOut_Off_GuitarWing_Toggle()

        elif status == STATUS_CC:
            if data1 == self.CC_BIG_FADER:
                self.sendMidiOut_CC_BigFader(data2)

    def sendMidiOut_On_GuitarWing_BigRoundButton1(self):
        self.sendControllerChange(4, 13, 127)

    def sendMidiOut_On_GuitarWing_BigRoundButton2(self):
        self.sendControllerChange(0, 16, 127)
        self.sendNoteOn(0, 44, 127)

    def sendMidiOut_On_GuitarWing_BigRoundButton3(self):
        self.sendControllerChange(0, 16, 110)
        self.sendNoteOn(0, 44, 127)

    def sendMidiOut_On_GuitarWing_BigRoundButton4(self):
        self.sendControllerChange(0, 52, 76)

    def sendMidiOut_On_GuitarWing_SmallRectangle1(self):
        self.sendControllerChange(0, 16, 0)

    def sendMidiOut_On_GuitarWing_SmallRectangle2(self):
        self.sendControllerChange(0, 16, 45)

    def sendMidiOut_On_GuitarWing_SmallRectangle3(self):
        self.sendControllerChange(0, 16, 64)

    def sendMidiOut_On_GuitarWing_SmallRectangle4(self):
        self.sendControllerChange(0, 16, 110)

    def sendMidiOut_On_GuitarWing_Toggle(self):
        pass

    def sendMidiOut_Off_GuitarWing_BigRoundButton1(self):
        self.sendControllerChange(4, 13, 0)

    def sendMidiOut_Off_GuitarWing_BigRoundButton2(self):
        self.sendNoteOn(0, 44, 127)

    def sendMidiOut_Off_GuitarWing_BigRoundButton3(self):
        self.sendNoteOn(0, 44, 127)

    def sendMidiOut_Off_GuitarWing_BigRoundButton4(self):
        self.sendControllerChange(0, 52, 0)

    def sendMidiOut_Off_GuitarWing_SmallRectangle1(self):
        pass

    def sendMidiOut_Off_GuitarWing_SmallRectangle2(self):
        pass

    def sendMidiOut_Off_GuitarWing_SmallRectangle3(self):
        pass

    def sendMidiOut_Off_GuitarWing_SmallRectangle4(self):
        pass

    def sendMidiOut_Off_GuitarWing_Toggle(self):
        pass

    def sendMidiOut_CC_BigFader(self, value):
        self.sendControllerChange(0, 56, int(value * 127.0/100.0))



    def sendControllerChange(self, channel, number, value):
        cc = [STATUS_CC + channel, number, value]
        self.portOut.send_message(cc)

    def sendNoteOn(self, channel, pitch, velocity):
        note_on = [STATUS_NOTE_ON + channel, pitch, velocity]
        self.portOut.send_message(note_on)

    def sendNoteOff(self, channel, pitch, velocity):
        note_off = [STATUS_NOTE_OFF + channel, pitch, velocity]
        self.portOut.send_message(note_off)


class MidiInputHandler_abletonVoiceFx(object):
    def __init__(self, portIn, portOut):
        self.portIn = portIn            #VoiceFX
        self.portOut = portOut          #Back to Ableton
        self._wallclock = time.time()
        self.currentAmpPreset = -1

    def __call__(self, event, data=None):
        event, deltatime = event
        
        if event[0] < 0xF0:
            channel = (event[0] & 0xF)
            status = event[0] & 0xF0
        else:
            status = event[0]
            channel = None

        data1 = data2 = None
        num_bytes = len(event)
        if num_bytes >= 2:
            data1 = event[1]
        if num_bytes >= 3:
            data2 = event[2]

        if status == STATUS_NOTE_ON:
            if   channel == ABLETON_VOICE_FX_CTRL_CHANNEL:
                if data1 == 35:
                    # Special action: disable the RMX Spiral
                    self.sendControllerChange(0,20,0)
                else:
                    self.sendControllerChange(OUTPUT_CHANNEL_ABLETON_VOICEFX, data1, data2)

        elif status == STATUS_NOTE_OFF:
            if channel == ABLETON_VOICE_FX_CTRL_CHANNEL:
                self.sendControllerChange(OUTPUT_CHANNEL_ABLETON_VOICEFX, data1, 0)

    def sendControllerChange(self, channel, number, value):
        cc = [STATUS_CC + channel, number, value]
        self.portOut.send_message(cc)

    def close(self):
        pass

class MidiInputHandler_abletonGtr(object):
    def __init__(self, portIn, portOut):
        self.portIn = portIn            #Gtr
        self.portOut = portOut          #To the Kemper
        self._wallclock = time.time()
        self.currentAmpPreset = -1

    def __call__(self, event, data=None):
        event, deltatime = event
        
        if event[0] < 0xF0:
            channel = (event[0] & 0xF)
            status = event[0] & 0xF0
        else:
            status = event[0]
            channel = None

        data1 = data2 = None
        num_bytes = len(event)
        if num_bytes >= 2:
            data1 = event[1]
        if num_bytes >= 3:
            data2 = event[2]
        
        if status == STATUS_NOTE_ON:
            if channel == ABLETON_GTR_CTRL_CHANNEL:
                if data1 != self.currentAmpPreset:
                    self.sendProgramChange_audioItf(OUTPUT_CHANNEL_KEMPER_AMP, max(data1 - 1,0))
                self.currentAmpPreset = data1

    def sendProgramChange_audioItf(self, channel, number):
        pc  = [STATUS_PC + channel, number]
        self.portOut.send_message(pc)



def main(args=None):
    """
    Main program function.
    No argument is to be passed to the program, and no user input is expected
    The program must be autonomous, and is executed at Minimouk's startup

    """

    logging.basicConfig(format="%(name)s: %(levelname)s - %(message)s", level=logging.DEBUG)
    
    midiport_emergencyControl_available = False
    midiport_abletonInVoiceFx_available = False
    midiport_abletonOut_available = False
    

    try:
        midiin_emergencyControl, port_name_emergencyControl = open_midiport(MIDI_BUS_CONFIGURATION_EMERGENCY_CONTROL, type_ = "input", interactive=False)
        midiport_emergencyControl_available = True
    except (ValueError):
        log.info("Emergency Control MIDI port unavailable")

    try:
        midiin_abletonInVoiceFx, port_name_abletonInVoiceFx = open_midiport(MIDI_BUS_CONFIGURATION_ABLETON_IN_VOICE_FX, type_ = "input", interactive=False)
        midiport_abletonInVoiceFx_available = True
    except (ValueError):
        log.info("Ableton Voice FX MIDI port unavailable")

    try:
        midiout_abletonOut, port_name_abletonOut            = open_midiport(MIDI_BUS_CONFIGURATION_ABLETON_OUT, type_ = "output", interactive=False)
        midiport_abletonOut_available = True
    except (ValueError):
        log.info("MIDI back to Ableton MIDI port unavailable")

    handler_emergencyControl_Strobot = None
    handler_emergencyControl_MIDI    = None
    handler_abletonVoiceFx           = None

    # These three callbacks should always be available - if not, the computer is not configured properly
    log.debug("Attaching available MIDI input callback handlers.")
    if midiport_emergencyControl_available:
        handler_emergencyControl_Strobot = MidiInputHandler_emergencyControl_Strobot(midiin_emergencyControl)
        midiin_emergencyControl.set_callback(handler_emergencyControl_Strobot)
        log.info(" *** Emergency control (Strobot) callback is attached")

    if midiport_emergencyControl_available:
        handler_emergencyControl_MIDI = MidiInputHandler_emergencyControl_MIDI(midiin_emergencyControl, midiout_abletonOut)
        midiin_emergencyControl.set_callback(handler_emergencyControl_MIDI)
        log.info(" *** Emergency control (MIDI) callback is attached")

    if midiport_abletonInVoiceFx_available and midiport_abletonOut_available:
        handler_abletonVoiceFx   = MidiInputHandler_abletonVoiceFx(midiin_abletonInVoiceFx, midiout_abletonOut)
        midiin_abletonInVoiceFx.set_callback(handler_abletonVoiceFx)
        log.info(" *** Ableton VoiceFX callback is attached")

    try:
        # If requested, recreate the MIDI emergency control object
        global REINIT_CALL
        while True:

            if REINIT_CALL:

                if midiport_emergencyControl_available:
                    handler_emergencyControl_MIDI.close()
                    handler_emergencyControl_Strobot.close()
                    handler_abletonVoiceFx.close()
                    midiout_abletonOut.close_port()

                    try:
                        midiout_abletonOut, port_name_abletonOut            = open_midiport(MIDI_BUS_CONFIGURATION_ABLETON_OUT, type_ = "output", interactive=False)
                        midiport_abletonOut_available = True
                    except (ValueError):
                        log.info("MIDI back to Ableton MIDI port unavailable")

                    if midiport_emergencyControl_available:
                        handler_emergencyControl_Strobot = MidiInputHandler_emergencyControl_Strobot(midiin_emergencyControl)
                        midiin_emergencyControl.set_callback(handler_emergencyControl_Strobot)
                        log.info(" *** Emergency control (Strobot) callback is attached")

                    if midiport_abletonInVoiceFx_available and midiport_abletonOut_available:
                        handler_abletonVoiceFx   = MidiInputHandler_abletonVoiceFx(midiin_abletonInVoiceFx, midiout_abletonOut)
                        midiin_abletonInVoiceFx.set_callback(handler_abletonVoiceFx)
                        log.info(" *** Ableton VoiceFX callback is attached")

                    if midiport_emergencyControl_available and midiport_abletonOut_available:
                        handler_emergencyControl_MIDI = MidiInputHandler_emergencyControl_MIDI(midiin_emergencyControl, midiout_abletonOut)
                        midiin_emergencyControl.set_callback(handler_emergencyControl_MIDI)
                        log.info(" *** Emergency control (MIDI) callback is attached")

                REINIT_CALL = False
            time.sleep(1)


    except KeyboardInterrupt:
        log.debug('Shutting down program')
    finally:
        if handler_emergencyControl_MIDI != None:
            handler_emergencyControl_MIDI.close()        
        midiin_emergencyControl.close_port()
        midiin_abletonInVoiceFx.close_port()
        midiout_abletonOut.close_port()
        del midiin_emergencyControl
        del midiin_abletonInVoiceFx
        del midiout_abletonOut

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)