#!/usr/bin/env python3

""" Codeplug/Firmware upgrade tool for Retevis RT73 (aka Kydera CDR-300UV)

This program is designed to allow you to use your radio (create/modify/save codeplug data)
as well as to upgrade the firmware (as supplied by the manufacturer)

The main purpose is to allow you to enjoy your radio without the need for manufacturer-produced, 
buggy, windows-only software.

Encryption settings are (intentionally) not supported, as these are not permitted for amateur radio use.

Any feedback welcome!

73, David, M0DMP

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.
This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "David Pye"
__contact__ = "davidmpye@gmail.com"
__copyright__ = "Copyright 2020-2021"
__deprecated__ = False
__email__ = "davidmpye@gmail.com"
__license__ = "GPLv3"
__maintainer__ = "David Pye"
__status__ = "Beta"
__version__ = "0.0.2"

__contributions__ = "Dave MM7DBT - Ham Contacts, Ham Groups"

import struct
import sys
from enum import Enum
import csv
import json
import serial
import argparse
import platform
import math

if platform.system() == "Windows":
    import ctypes
    ctypes.windll.kernel32.SetConsoleTitleW("Retevis RT73 Codeplug/Firmware Tool by David M0DMP")
    

###Exit Code Status
###Code 0 - Success
###Code 1 - No response from radio (can't connect)
###Code 2 - Unknown response from radio
###Code 3 - Codeplug too large >255 pages
###Code 4 - Codeplug size was incorrect when compiled
###Code 5 - Firmware Failed - Possibly still updated succesfully though
###Code 6 - Ham Contacts Bytes argument invalid - Not 16 or 128
###Code 7 - Ham Contacts block to large - Too many contacts
###Code 8 - Ham Groups block too large - Too many groups
###Code 9 - COM Port In Use


#Record sizes (bytes)
channel_record_size = 32 
zone_record_size = 32 
contact_record_size = 16 
message_record_size = 40
rx_group_record_size = 210
scan_list_record_size = 216 #10 bytes for name and + 4 bytes per zone/channel pair (allowed 50 per group) 

channel_count_address = 0x1391
channel_count_len = 2

contact_count_address = 0x1393
contact_count_len = 2

zone_count_address = 0x138F
zone_count_len = 2

#Fixed addresses of blocks
contact_start_address = 0x1B400
rx_group_start_address = 0xE6BF
scan_list_start_address = 0x13CF

# Messages are stored in two blocks!
#Block 1 contains 15 messages, and starts at offset:
message_block_1_start_addr = 0x0000FAE
message_block_1_count = 15
#Block 2 contains 85 messages, and starts before block1, at offset:
message_block_2_start_addr = 0x000012B
message_block_2_count = 85

aprs_dmr_channel_start_address = 0x0000E4B

#List of the CTCSS tones used
CTCSS_Tones = [ 62.5, 67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 
        123.0, 127.3, 131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9, 171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 
        189.9, 192.8, 196.6, 199.5, 203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1 ]

#List of the DCS tones used - the CPS UI displays an N (normal) or I (Inverted) at the end, depending on whether normal or inverted mode is selected.
DCS_Codes = [
    17, 23, 25, 26, 31, 32, 36, 43, 47, 50, 51, 53, 54, 65, 71, 72, 73, 74, 114, 
    115, 116, 122, 125, 131, 132, 134, 143, 145, 152, 155, 156, 162, 165, 172, 174, 205, 212, 223, 
    225, 226, 243, 244, 245, 246, 251, 252, 255, 261, 263, 265, 266, 271, 274, 306, 311, 315, 325, 
    331, 332, 343, 346, 351, 356, 364, 365, 371, 411, 412, 413, 423, 431, 432, 445, 446, 452, 454, 
    455, 462, 464, 465, 466, 503, 506, 516, 523, 526, 532, 546, 565, 606, 612, 624, 627, 631, 632, 
    645, 646, 654, 662, 664, 703, 712, 723, 731, 732, 734, 743, 754 ]

Button_IDs = {
    0x00: "UNDEFINED",
    0x01: "HI_LO_POWER",
    0x02: "BACKLIGHT_TOGGLE",
    0x03: "KEYLOCK_TOGGLE",
    0x04: "VOX",
    0x05: "ZONE_SWITCH",
    0x06: "SCAN",
    0x07: "SCAN_MODE_TOGGLE",
    0x08: "RPTR_TALKAROUND",
    0x09: "EMERGENCY_ALARM",
    0x0A: "ENCRYPTION_TOGGLE",
    0x0B: "CONTACTS",
    0x0C: "SMS",
    0x0D: "RADIO_REVIVE",
    0x0E: "RADIO_DETECTION",
    0x0F: "RADIO_KILL",
    0x10: "REMOTE_MONITOR",
    0x11: "MONITOR",
    0x12: "PERMANENT_MONITOR",
    0x13: "TONEBURST_1750HZ",
    0x31: "DTMF_TOGGLE",
    0x34: "ROAM_TOGGLE",
    0x1B: "GPS_TOGGLE",
    0x28: "MENU",
    0x37: "UP",
    0x38: "DOWN",
    0x39: "BACK",
    0x3A: "DQT_QT",
    0x3B: "A_B_TOGGLE",
    0x3C: "VOL",
    0x3D: "VFO",
    0x3E: "MANDATORY_MONITOR",  #aka promiscuous mode
    0x3F: "DUAL_WATCH_TOGGLE" 
}

class Parser:
    def __init__(self):
        pass
    def fromBytes(self, definitions, bytes):
        data = {}

        for key in definitions:
            definition = definitions[key]
            if definition[0] == "Bitmask":
                b = bytes[definition[1]] & definition[2]
                #Look up the enum name and return it
                try:
                    val = definition[3][b]
                except:
                    print("Unable to find key " + str(definitions[key]) + " for val " + hex(b) + " - codeplug likely corrupted")
                    val = ""

            elif definition[0] == "String":
                val = bytes[definition[1]:definition[1] + definition[2]].decode('ascii').rstrip("\x00")
            elif definition[0] == "Number":
                val = int.from_bytes(bytes[definition[1]: definition[1] + definition[2]], byteorder='little')
            elif definition[0] == "MaskNum":
                val = bytes[definition[1]] & definition[2]
                # If any lambda encode function defined, perform it.
                if len(definition) >3 : 
                    val = definition[3](val)

            data[key] = val

        return data

    def toBytes(self, data, definitions, item):
        for key in definitions:
            definition = definitions[key]
            if definition[0] == "Bitmask":
                for k, v in definition[3].items():
                    if v == item[key]:
                        data[definition[1]] |= k
            elif definition[0] == "String":
                encoded_str = item[key].encode('ascii')
                for p in range(len(item[key])):
                    data[definition[1] + p] = encoded_str[p]
            elif definition[0] == "Number":
                data[definition[1]:definition[1]+definition[2]] = item[key].to_bytes(length = definition[2], byteorder='little')
            elif definition[0] == "MaskNum":
                # Do the reverse lambda function
                if len(definition) >3:
                    data[definition[1]] |= (int(definition[4](item[key])) & definition[2])
                else:
                    data[definition[1]] |= (int(item[key]) & definition[2])

#Device info
dev_info = {}
dev_info["Factory Number"] = [ "String", 0x00, 16]
dev_info["Serial Number"] = [ "String", 0x10, 16]
dev_info["Model Number"] = [ "String", 0x20, 16]
dev_info["FW Version"] = [ "String", 0x30, 31]
dev_info["Frequency range"] = [ "String", 0x50, 16]
dev_info["Update date"] = [ "String", 0x60, 16]
dev_info["Firmware ID"] = [ "String", 0x70, 16]

#Basic parameters
basic_parameters = {}
basic_parameters["Radio name"] = [ "String", 0x80, 10]
basic_parameters["DMR ID"] = [ "Number", 0x90, 3]

basic_parameters["Language"] = [ "Bitmask", 0x95, 0x10, {0x00: "Chinese", 0x10: "English"}]
basic_parameters["TimeoutTimer"] = [ "Number", 0x134F, 1]
basic_parameters["Busy channel lockout"] = [ "Bitmask", 0xA6, 0x80, {0x00: "Off", 0x80: "On"}]
basic_parameters["VOX"] = [ "Bitmask", 0xA6, 0x40, {0x00: "Off", 0x40: "On"}]
basic_parameters["VOX sensitivity"] = [ "MaskNum", 0xA6, 0x0F, lambda x:x+1, lambda x: x-1]
basic_parameters["Scan mode"] = ["Bitmask", 0x137D, 0x03, { 0x00: "CO", 0x01: "TO", 0x02: "SE" }]
basic_parameters["End tone types"] = ["Bitmask", 0x1381, 0x03, { 0x00: "55Hz", 0x01: "120'", 0x02: "180", 0x03: "240" }]
basic_parameters["Squelch A level"] = [ "MaskNum", 0x93, 0x0F]
basic_parameters["Squelch B level"] = [ "MaskNum", 0x93, 0xF0, lambda x:x>>4, lambda x: x<<4]

basic_parameters["Backlight"] = [ "Bitmask", 0x95, 0x28, {0x00: "Off", 0x08: "On", 0x20: "Auto" }]
basic_parameters["Keylock"] = [ "Bitmask", 0x95, 0x44, {0x00: "Off", 0x04: "Auto", 0x40: "Manual", 0x44: "Manual & Auto" }]
basic_parameters["Roaming"] = [ "Bitmask", 0x137B, 0x01, {0x00: "Off", 0x01: "On"}]
basic_parameters["Roaming mode"] = [ "Bitmask", 0x1375, 0x03, {0x00: "Auto", 0x01: "Manual", 0x02: "Strong RSSI Priority"}]
basic_parameters["RSSI set"] = [ "MaskNum", 0x1376, 0xFF, lambda x: -90 - x , lambda x: -1*x - 90 ]
basic_parameters["Connect check timer"] = [ "MaskNum", 0x1377, 0xFF ]
basic_parameters["Repeater check timer"] = [ "MaskNum", 0x1378, 0xFF ]
basic_parameters["Connect timer"] = [ "MaskNum", 0x1379, 0x09, lambda x: x + 1 , lambda x: x - 1 ]
basic_parameters["Record set"] = [ "Bitmask", 0x1380, 0x03, {0x00: "None", 0x01: "TX", 0x02: "RX", 0x03: "TX/RX"}]

#Common menu settings
common_menu_parameters = {}
common_menu_parameters["Contact list"] = [ "Bitmask", 0xAE, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["New contact"] = [ "Bitmask", 0xAE, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Manual dial"] = [ "Bitmask", 0xAE, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Ham contacts"] = [ "Bitmask", 0xAE, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["Ham groups"] = [ "Bitmask", 0xAE, 0x10, {0x00: "Off", 0x10: "On"}]

common_menu_parameters["Radio check"] = [ "Bitmask", 0xBA, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Call alert"] = [ "Bitmask", 0xBA, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Radio monitor"] = [ "Bitmask", 0xBA, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Radio disable"] = [ "Bitmask", 0xBA, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["Radio enable"] = [ "Bitmask", 0xBA, 0x10, {0x00: "Off", 0x10: "On"}]

common_menu_parameters["SMS write"] = [ "Bitmask", 0xAF, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["SMS quick msg"] = [ "Bitmask", 0xAF, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["SMS inbox"] = [ "Bitmask", 0xAF, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["SMS outbox"] = [ "Bitmask", 0xAF, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["SMS drafts"] = [ "Bitmask", 0xAF, 0x10, {0x00: "Off", 0x10: "On"}]

common_menu_parameters["Call log outgoing"] = [ "Bitmask", 0xB0, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Call log received"] = [ "Bitmask", 0xB0, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Call log missed"] = [ "Bitmask", 0xB0, 0x04, {0x00: "Off", 0x04: "On"}]

common_menu_parameters["Scan on/off"] = [ "Bitmask", 0xB1, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Scan list"] = [ "Bitmask", 0xB1, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Scan mode"] = [ "Bitmask", 0xB1, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Roam on/off"] = [ "Bitmask", 0xB1, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["Scan running on/off"] = [ "Bitmask", 0x10, 0x10, {0x00: "Off", 0x10: "On"}]

common_menu_parameters["Zone list on/off"] = [ "Bitmask", 0xB2, 0x01, {0x00: "Off", 0x01: "On"}]

common_menu_parameters["Language"] = [ "Bitmask", 0xB3, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Keylock"] = [ "Bitmask", 0xB3, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Backlight"] = [ "Bitmask", 0xB3, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["LEDs"] = [ "Bitmask", 0xB3, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["Display mode"] = [ "Bitmask", 0xB3, 0x10, {0x00: "Off", 0x10: "On"}]
common_menu_parameters["Vox"] = [ "Bitmask", 0xB3, 0x20, {0x00: "Off", 0x20: "On"}]
common_menu_parameters["Channel sw"] = [ "Bitmask", 0xB3, 0x40, {0x00: "Off", 0x40: "On"}]
common_menu_parameters["Factory reset"] = [ "Bitmask", 0xB3, 0x80, {0x00: "Off", 0x80: "On"}]

common_menu_parameters["Local repeat"] = [ "Bitmask", 0xBC, 0x01, {0x00: "Off", 0x01: "On"}]

common_menu_parameters["ToT"] = [ "Bitmask", 0xB5, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Power set"] = [ "Bitmask", 0xB5, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Repeat set"] = [ "Bitmask", 0xB5, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Sleep mode"] = [ "Bitmask", 0xB5, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["Squelch level"] = [ "Bitmask", 0xB5, 0x10, {0x00: "Off", 0x10: "On"}]
common_menu_parameters["Wide/Narrow band"] = [ "Bitmask", 0xB5, 0x20, {0x00: "Off", 0x20: "On"}]
common_menu_parameters["Busy channel lockout"] = [ "Bitmask", 0xB5, 0x40, {0x00: "Off", 0x40: "On"}]
common_menu_parameters["Signalling"] = [ "Bitmask", 0xB5, 0x80, {0x00: "Off", 0x80: "On"}]

common_menu_parameters["End tone types"] = [ "Bitmask", 0xBD, 0x01, {0x00: "Off", 0x01: "On"}]

common_menu_parameters["Enc level"] = [ "Bitmask", 0xB4, 0x01, {0x00: "Off", 0x01: "On"}]

common_menu_parameters["Profiles"] = [ "Bitmask", 0xB6, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Keytone"] = [ "Bitmask", 0xB6, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Power tone"] = [ "Bitmask", 0xB6, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Msg tone"] = [ "Bitmask", 0xB6, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["Private call tone"] = [ "Bitmask", 0xB6, 0x10, {0x00: "Off", 0x10: "On"}]
common_menu_parameters["Group call tone"] = [ "Bitmask", 0xB6, 0x20, {0x00: "Off", 0x20: "On"}]
common_menu_parameters["Call tone"] = [ "Bitmask", 0xB6, 0x40, {0x00: "Off", 0x40: "On"}]
common_menu_parameters["Power on tone"] = [ "Bitmask", 0xB6, 0x80, {0x00: "Off", 0x80: "On"}]


common_menu_parameters["GPS"] = [ "Bitmask", 0xB7, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Torch"] = [ "Bitmask", 0xB7, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["FM radio"] = [ "Bitmask", 0xB7, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Time"] = [ "Bitmask", 0xB7, 0x08, {0x00: "Off", 0x08: "On"}]
common_menu_parameters["DTMF"] = [ "Bitmask", 0xB7, 0x10, {0x00: "Off", 0x10: "On"}]
common_menu_parameters["Speaker handmic"] = [ "Bitmask", 0xB7, 0x20, {0x00: "Off", 0x20: "On"}]
common_menu_parameters["APRS"] = [ "Bitmask", 0xB7, 0x40, {0x00: "Off", 0x40: "On"}]

common_menu_parameters["Record set"] = [ "Bitmask", 0xB8, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["Record list"] = [ "Bitmask", 0xB8, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Record clear"] = [ "Bitmask", 0xB8, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Record space"] = [ "Bitmask", 0xB8, 0x08, {0x00: "Off", 0x08: "On"}]

common_menu_parameters["Radio ID"] = [ "Bitmask", 0xB9, 0x01, {0x00: "Off", 0x01: "On"}]
common_menu_parameters["RX group list"] = [ "Bitmask", 0xB9, 0x02, {0x00: "Off", 0x02: "On"}]
common_menu_parameters["Channel contact"] = [ "Bitmask", 0xB9, 0x04, {0x00: "Off", 0x04: "On"}]
common_menu_parameters["Version"] = [ "Bitmask", 0xB9, 0x08, {0x00: "Off", 0x08: "On"}]

common_menu_parameters["VFO"] = [ "Bitmask", 0xBB, 0x01, {0x00: "Off", 0x01: "On"}]

#Prompt tone settings
prompt_tone_parameters = {}
prompt_tone_parameters["Profiles"] = [ "Bitmask", 0xA7, 0x01, {0x00: "Standard", 0x01: "Silent"}]
prompt_tone_parameters["SMS Prompt"] = [ "MaskNum", 0xA8, 0x0F ]
prompt_tone_parameters["Private call Tone"] = [ "MaskNum", 0xA9, 0x05 ]
prompt_tone_parameters["Group call Tone"] = [ "MaskNum", 0xAA, 0x05 ]
prompt_tone_parameters["Key tone"] = [ "Bitmask", 0xAB, 0x80, {0x00: "Off", 0x80: "On"}]
prompt_tone_parameters["Key tone vol"] = [ "MaskNum", 0xAB, 0x0F ]
prompt_tone_parameters["Low bat alert tone"] = [ "Bitmask", 0xAC, 0x80, {0x00: "Off", 0x80: "On"}]
prompt_tone_parameters["Low bat alert vol"] = [ "MaskNum", 0xAC, 0x0F ]
prompt_tone_parameters["Call hang up"] = [ "Bitmask", 0x12d8, 0x01, {0x00: "Silent", 0x01: "Prompt Tone"}]
prompt_tone_parameters["Boot ringtone"] = [ "Bitmask", 0x95, 0x02, {0x00: "Off", 0x02: "On"}]
prompt_tone_parameters["Roaming restart prompt"] = [ "MaskNum", 0x1383, 0x0F ]
prompt_tone_parameters["Repeater selected prompt"] = [ "MaskNum", 0x1383, 0x0F ]

#Indicators 
indicator_parameters = {}
indicator_parameters["All"] = ["Bitmask", 0xAD, 0x10, {0x10: "On", 0x00: "Off"}]
indicator_parameters["Tx"] = ["Bitmask", 0xAD, 0x08, {0x08: "On", 0x00: "Off"}]
indicator_parameters["Rx"] = ["Bitmask", 0xAD, 0x04, {0x04: "On", 0x00: "Off"}]
indicator_parameters["Scanning"] = ["Bitmask", 0xAD, 0x02, {0x02: "On", 0x00: "Off"}]
indicator_parameters["Low battery"] = ["Bitmask", 0xAD, 0x01, {0x01: "On", 0x00: "Off"}]

#Button presets
button_preset_parameters = {}
button_preset_parameters["LongPressDuration"] = ["Bitmask", 0xC1, 0xFF, {0x00: "0.5", 0x01: "1.0", 0x02: "1.5", 0x03: "2.0", 0x04: "2.5", 0x05: "3.0", 0x06: "3.5", 0x07: "4.0", 0x08: "4.5", 0x09: "5.0"}]
button_preset_parameters["P1 LongPress"] = [ "Bitmask", 0xC2, 0xFF, Button_IDs]
button_preset_parameters["P1 ShortPress"] = [ "Bitmask", 0xC3, 0xFF, Button_IDs]
button_preset_parameters["P2 LongPress"] = [ "Bitmask", 0xC4, 0xFF, Button_IDs]
button_preset_parameters["P2 ShortPress"] = [ "Bitmask", 0xC5, 0xFF, Button_IDs]
button_preset_parameters["P3 LongPress"] = [ "Bitmask", 0xC6, 0xFF, Button_IDs]
button_preset_parameters["P3 ShortPress"] = [ "Bitmask", 0xC7, 0xFF, Button_IDs]
button_preset_parameters["P4 LongPress"] = [ "Bitmask", 0xC8, 0xFF, Button_IDs]
button_preset_parameters["P4 ShortPress"] = [ "Bitmask", 0xC9, 0xFF, Button_IDs]
button_preset_parameters["P5 LongPress"] = [ "Bitmask", 0xCA, 0xFF, Button_IDs]
button_preset_parameters["P5 ShortPress"] = [ "Bitmask", 0xCB, 0xFF, Button_IDs]
button_preset_parameters["P6 LongPress"] = [ "Bitmask", 0xCC, 0xFF, Button_IDs]
button_preset_parameters["P6 ShortPress"] = [ "Bitmask", 0xCD, 0xFF, Button_IDs]
button_preset_parameters["P7 LongPress"] = [ "Bitmask", 0x1385, 0xFF, Button_IDs]
button_preset_parameters["P7 ShortPress"] = [ "Bitmask", 0x1386, 0xFF, Button_IDs]

#Mic gain
mic_gain_parameters = {}
mic_gain_parameters["Mic gain 1"] = ["Bitmask", 0xA4, 0x80, {0x80: "On", 0x00: "Off"}]
mic_gain_parameters["Mic gain 1 setting"] = [ "MaskNum", 0xA4, 0x07, lambda x: x*4 , lambda x: int(x/4) ]
mic_gain_parameters["Mic gain 2"] = ["Bitmask", 0xA5, 0x80, {0x80: "On", 0x00: "Off"}]
mic_gain_parameters["Mic gain 2 setting"] = [ "MaskNum", 0xA5, 0x1F ]

#DMR settings
dmr_parameters = {}
dmr_parameters["Remote monitor duration"] = [ "MaskNum", 0xFAC, 0xFF, lambda x: 10 + x*10, lambda x: (x/10) -1]
dmr_parameters["Remote monitor decode"] = [ "Bitmask", 0xFAD, 0x80, { 0x00: "Off", 0x80:"On" } ]
dmr_parameters["Remote kill decode"] = [ "Bitmask", 0xFAD, 0x40, { 0x00: "Off", 0x40:"On" } ]
dmr_parameters["Radio detection decode"] = [ "Bitmask", 0xFAD, 0x20, { 0x00: "Off", 0x20:"On" } ]
dmr_parameters["Radio revive decode"]= [ "Bitmask", 0xFAD, 0x10, { 0x00: "Off", 0x10:"On" } ]
dmr_parameters["Call alert"] = [ "Bitmask", 0xFAD, 0x08, { 0x00: "Off", 0x08:"On" } ]
dmr_parameters["Group call hang time"] = [ "MaskNum", 0x1350, 0x0F, lambda x: x*500, lambda x: int(x/500) ]
dmr_parameters["Private call hang time"] = [ "MaskNum", 0x1351, 0x0F, lambda x: x*500, lambda x: int(x/500) ]
dmr_parameters["Import delay"] = [ "MaskNum", 0x1370, 0xFF, lambda x: x*10, lambda x: x/10 ]
dmr_parameters["DTMF duration (on-time)"] = [ "MaskNum", 0x1371, 0xFF, lambda x: x*10, lambda x: int(x/10) ]
dmr_parameters["DTMF duration (off-time)"] = [ "MaskNum", 0x1372, 0xFF, lambda x: x*10, lambda x: int(x/10) ]
dmr_parameters["DTMF volume (local)"] = [ "MaskNum", 0x1373, 0x0F ] # Vol 0 - 12
dmr_parameters["DTMF On/off"] = [ "Bitmask", 0x1363, 0x01, { 0x00: "Off", 0x01:"On" } ]

#Now there's a separate APRS section - with analog and digital settings, I have no idea whether this is still respected or not....
dmr_parameters["GPS On/off"] = [ "Bitmask", 0x137A, 0x01, { 0x00: "Off", 0x01:"On" } ]
dmr_parameters["GPS Interval"] = [ "MaskNum", 0x1353, 0xFF] #10 sec increments from 0 to 6, then mins above that. eg 6 = 1 min, 7 = 2 min.
#If these are BOTH set of 0xFFFF, then the radio uses the current channel to send the APRS 'ping' to. 
#Undefined behaviour if current channel doesn't have a default contact set (the CPS software removes the 'current channel' option unless 
#all channels have a Default Contact specified
dmr_parameters["GPS Channel group ID"] = [ "Number", 0x1354, 2]
dmr_parameters["GPS Channel channel ID"] = [ "Number", 0x1356, 2]


#APRS settings
aprs_parameters = {}
aprs_parameters["Manual TX interval"] = ["Number", 0xE8B, 1 ]
#Seconds * 30
aprs_parameters["Auto TX interval"] = [ "MaskNum", 0xE8C, 0xFF, lambda x: x*30, lambda x: int(x/30) ]
aprs_parameters["Beacon"] = [ "Bitmask", 0xE8E, 0x01, { 0x00: "FIXED_LOCATION", 0x01: "GPS_LOCATION" } ]

#Fixed Location is stored in 4 bytes, int32: Translates to Degrees Minutes Seconds: 5606470 = (D)56 (M)06 (S)470
aprs_parameters["LatNS"] = [ "Bitmask", 0xE8F, 0x01, { 0x00: "North", 0x01: "South" } ]
aprs_parameters["Lat Degrees"] = ["Number", 0xE91, 4 ]

aprs_parameters["LongEW"] = [ "Bitmask", 0xE90, 0x01, { 0x00: "East", 0x01: "West" } ]
aprs_parameters["Long Degrees"] = ["Number", 0xE95, 4 ]

#TX Freq does use 4 bytes after FF FF FF (16777215), although typically used on 2 meters, setting the 4 bytes would allow frequencies at 70cm.
aprs_parameters["AX25 TX Freq"] = [ "Number", 0xE99, 4 ]
aprs_parameters["AX25 TX Power"] = [ "Bitmask", 0xEA1, 0x01, { 0x00: "LOW", 0x01 : "HIGH" } ]

aprs_parameters["AX25 QT/DQT"] = [ "Number", 0xE9D, 2 ]

aprs_parameters["AX25 APRS Tone"] = [ "Bitmask", 0xEA2, 0x01, { 0x00: "OFF", 0x01: "ON" } ]
#TX delay in 20ms increments
aprs_parameters["AX25 TX Delay"] = [ "MaskNum", 0xE9F, 0xFF, lambda x: x*20, lambda x: int(x/20) ]
#Prewave time in 10ms increments
aprs_parameters["AX25 Prewave time"] = [ "MaskNum", 0xEA0, 0xFF, lambda x: x*10, lambda x: int(x/10) ]

aprs_parameters["AX25 Your Callsign"] = [ "String", 0xEAB, 6 ]
aprs_parameters["AX25 Your SSID"] = [ "Number", 0xEA4, 1]
aprs_parameters["AX25 Dest Callsign"] = [ "String", 0xEA5, 6 ]
aprs_parameters["AX25 Dest SSID"] = [ "Number", 0xEA3, 1 ]

#This is an ascii character code for the desired symbol
aprs_parameters["AX25 APRS Symbol Table"] = [ "Number", 0xEB1, 1]
aprs_parameters["AX25 APRS Map Icon"] = [ "Number", 0xEB2, 1]

aprs_parameters["AX25 APRS Signal Path"] = [ "String", 0xEB3, 20 ]
aprs_parameters["AX25 Your Sending Text"] = [ "String", 0xEC7, 61 ] 


#These start at 0xE43, 8 bytes long x 8 records
#Addresses relative to start address.
#Parsed/compiled separately, and appended to the APRS parameter section above
aprs_dmr_record_parameters = {}
aprs_dmr_record_parameters["Zone ID"] = [ "Number", 0x00, 2 ] 
aprs_dmr_record_parameters["Channel ID"] = [ "Number", 0x02, 2 ] 
aprs_dmr_record_parameters["Call Type"] = [ "Bitmask", 0x07, 0x04, { 0x00: "PRIVATE", 0x04: "GROUP" } ]
aprs_dmr_record_parameters["PTT"] = [ "Bitmask", 0x07, 0x08, { 0x00: "OFF", 0x08: "ON" } ]
aprs_dmr_record_parameters["Report Slot"] = [ "Bitmask", 0x07, 0x03, { 0x00: "CURRENT", 0x01: "TS1", 0x02: "TS2" } ]
aprs_dmr_record_parameters["APRS TG"] = [ "Number", 0x04, 3 ] 


#Contacts
contact_parameters = {}
# NB These are relative to the zone record bytes, not the whole codeplug.
contact_parameters["ID"] = [ "Number", 0x00, 2 ]
contact_parameters["Name"] = [ "String", 0x03, 10 ]
contact_parameters["DMR ID"] = [ "Number", 0x0D, 3 ]
contact_parameters["Type"] = ["Bitmask", 0x02, 0xFF, {0x04: "Group", 0x05: "Private", 0x06: "All Call", 0x07: "No-Address Call", 0x08: "RawData", 0x09: "Define Data", 0x0A: "SPDATA"}]

# Scan list
scan_list_info = {}
# NB These are relative to the scan list record bytes, not the whole codeplug.
scan_list_info["Name"] = [ "String", 0x00, 10] 
scan_list_info["Talkback"] = [ "Bitmask", 0x0B, 0x20, { 0x00: "Off", 0x20: "On" } ]
scan_list_info["Scan TX Mode"] = [ "Bitmask", 0x0B, 0x0F, { 0x00: "Current Channel", 0x04: "Last Operated Channel", 0x08: "Appointed Channel" } ]
scan_list_info["Appointed channel group ID"] = [ "Number", 0x0C, 2]
scan_list_info["Appointed channel channel ID"] = [ "Number", 0x0E, 2 ]

# RX groups
# The paired lists of group/channel IDs are parsed separately.
rx_group_info={}
rx_group_info["Name"] = [ "String", 0x00, 10 ]

zone_info = {}
# NB These are relative to the zone record bytes, not the whole codeplug.
zone_info["ID"] = [ "Number", 0x00, 2]
zone_info["Name"] = [ "String", 0x03, 10 ]
# These two fields exist in the binary codeplug, but are generated at the time of writing it. There's no value in parsing them into/from JSON though.
#zone_info["channel offset"] = ["Number", 0x0D,2]  - It doesnt get JSON parsed but inserted into the codeplug builder - no of 32 byte slots to skip before we get to the channels
#zone_info["chan count"] = ["Number", 0x0F, 2] - calculated at upload time along with the channel offset

channel_info = {}
# NB These are relative to the zone record bytes, not the whole codeplug.
#Structure: Human readable name: Type, byte offset, length (mask if bitmask), ( enum values if bitmask)
channel_info["ID"] = ["Number", 0x00, 2 ]
channel_info["Type"] = ["Bitmask", 0x14, 0xC0, { 0x00: "ANALOG", 0x40: "DIGITAL", 0x80: "D_A_TX_A", 0xC0: "D_A_TX_D" } ]
channel_info["Name"] = ["String", 0x02, 10 ]
channel_info["Rx Freq"] = ["Number", 0x0C, 4 ]
channel_info["Tx Freq"] = ["Number", 0x10, 4 ]
channel_info["Tx Power"] = [ "Bitmask", 0x14, 0x20, { 0x00: "LOW", 0x20: "HIGH" }]
channel_info["Rx only"] = [ "Bitmask", 0x19, 0x10, { 0x00: "OFF", 0x10: "ON" }]
channel_info["Alarm"] = [ "Bitmask", 0x14, 0x08, { 0x00: "OFF", 0x08: "ON" }]
channel_info["Prompt"] = [ "Bitmask", 0x14, 0x08 , { 0x00: "OFF", 0x08: "ON" } ]
channel_info["PCT"] = [ "Bitmask", 0x14, 0x02, { 0x00: "PATCS", 0x02: "OACSU" }]
channel_info["TS Rx"] = [ "Bitmask", 0x14, 0x01, { 0x00: "TS1", 0x01: "TS2" } ]
channel_info["TS Tx"] = [ "Bitmask", 0x1D, 0x02, { 0x00: "TS1", 0x02: "TS2" } ]
channel_info["RX CC"] = ["MaskNum", 0x15, 0x0F]
channel_info["TX CC"] = ["MaskNum", 0x1D, 0xF0, lambda x: x>>4, lambda x: x<<4]
channel_info["MSG Type"] = [ "Bitmask", 0x15, 0x10, { 0x00: "UNCONFIRMED", 0x10: "CONFIRMED" }]
channel_info["TX Policy"] = [ "Bitmask", 0x15, 0xC0, { 0x00: "IMPOLITE", 0x40: "POLITE_TO_CC", 0x60: "POLITE_TO_ALL" }]
channel_info["Group call list"] = ["Number", 0x17, 1]
#Encryption
channel_info["Scan List ID"] = [ "Number", 0x18 , 1]
# I think that Default Contact ID also uses a few bits from 0x1F..... so ignoring this will only allow a default contact from the first 255 contacts 
# in the address book, so this needs fixing...
channel_info["Default Contact ID"] = ["Number", 0x1E, 1]
channel_info["EAS"] = [ "Bitmask", 0x19, 0x0F, { 0x00: "OFF", 0x01: "A1", 0x02: "A2", 0x03: "A3", 0x04: "A4" }]
channel_info["Bandwidth"] = [ "Bitmask", 0x14, 0x10, { 0x10: "25KHz", 0x00: "12.5KHz" } ]
# CTCSS/DCS details
channel_info["Tone Type Tx"] = [ "Bitmask", 0x1A, 0x0C, { 0x00: "OFF", 0x04: "CTCSS", 0x08: "DCS", 0x0C: "DCS Invert" }]
channel_info["Tone Tx"] = [ "Number",0x1C, 1 ]
channel_info["Tone Type Rx"] = [ "Bitmask", 0x1A, 0x03, { 0x00: "OFF", 0x01: "CTCSS", 0x02: "DCS", 0x03: "DCS Invert" }]
channel_info["Tone Rx"] = [ "Number",0x1B, 1 ]
# APRS setting
channel_info["APRS Channel"] = [ "MaskNum", 0x1F, 0xF0, lambda x: x>>4, lambda x: x<<4 ]

tson_info = {}
tson_info["TS Rx ON"] = [ "Bitmask", 0x1D, 0x01, { 0x00: "ON", 0x01: "OFF" } ]
tson_info["TS Tx ON"] = [ "Bitmask", 0x1D, 0x04, { 0x00: "ON", 0x04: "OFF" } ]

def decompileCodeplug(data):
    codeplug = {}
    debugMsg(3, "Decompiling codeplug")
    num_channels = int.from_bytes(data[channel_count_address: channel_count_address + channel_count_len],byteorder = 'little')
    num_zones = int.from_bytes(data[zone_count_address: zone_count_address + zone_count_len],byteorder = 'little')
    num_contacts = int.from_bytes(data[contact_count_address: contact_count_address + contact_count_len],byteorder = 'little')
    
    #Based on the above constants, we can work out where certain things will start within the codeplug.
    contact_block_size = num_contacts * contact_record_size

    debugMsg(2, "Contacts Block Size " + str(contact_block_size))
    #Pad contact block to a multiple of 1K if needed
    if contact_block_size %1024 != 0:
        contact_block_size += 1024 - (contact_block_size%1024)
        debugMsg(2, "Contacts Block Padded " + str(contact_block_size))

    #Pad contact block to an odd number of blocks - possible fix for number of contacts > 64
    if (contact_block_size//1024)%2 == 0:
        debugMsg(2, "Contacts Block Count Was Even - Adding another block")
        contact_block_size = contact_block_size + 1024

    debugMsg(2, "Contact Block Size " + str(contact_block_size))
    #The start address of the zone will start on a 1K byte (0x400 hex) boundary, after the contacts have ended.
    zone_start_address = contact_start_address + contact_block_size
    #Check it's on a 1K boundary, and if not, offset it so it is.
    if zone_start_address % 1024 != 0:
        zone_start_address += 1024 - zone_start_address%1024
    
    debugMsg(2, "Zones:" + str(num_zones) + ", start address " + hex(zone_start_address))
    debugMsg(2, "Channels:" + str(num_channels))
    debugMsg(2, "Contacts:" + str(num_contacts) + ", start address: " + hex(contact_start_address))

    # Start the parsing
    p = Parser()

    debugMsg(2, "Parsing Device info")
    codeplug["Device info"] = p.fromBytes(dev_info,data)
    debugMsg(2, "Parsing Basic parameters")
    codeplug["Basic parameters"] = p.fromBytes(basic_parameters, data)
    debugMsg(2, "Parsing Common menu parameters")
    codeplug["Common menu parameters"] = p.fromBytes(common_menu_parameters, data)
    debugMsg(2, "Parsing Prompt Tone")
    codeplug["Prompt Tone"] = p.fromBytes(prompt_tone_parameters, data)
    debugMsg(2, "Parsing Indicators")
    codeplug["Indicators"] = p.fromBytes(indicator_parameters, data)
    debugMsg(2, "Preset buttons")
    codeplug["Preset buttons"] = p.fromBytes(button_preset_parameters, data)
    debugMsg(2, "Parsing Mic gain")
    codeplug["Mic gain"] = p.fromBytes(mic_gain_parameters, data)
    debugMsg(2, "Parsing APRS settings")
    codeplug["APRS"] = p.fromBytes(aprs_parameters, data) 
    
    #codeplug["APRS"]["AX25 TX Freq"] = codeplug["APRS"]["AX25 TX Freq"] * 10


    if 159 <= codeplug["APRS"]["AX25 QT/DQT"] <= 267: #DCS Invert
        codeplug["APRS"]["AX25 QT/DQT"] = "D" + str(DCS_Codes[(codeplug["APRS"]["AX25 QT/DQT"]-160)]).zfill(3) + "I"
    elif 52 <= codeplug["APRS"]["AX25 QT/DQT"] <= 158: #DCS Normal
        codeplug["APRS"]["AX25 QT/DQT"] = "D" + str(DCS_Codes[(codeplug["APRS"]["AX25 QT/DQT"]-53)]).zfill(3) + "N"
    elif 1 <= codeplug["APRS"]["AX25 QT/DQT"] <= 51: #CTCSS
        codeplug["APRS"]["AX25 QT/DQT"] = str(CTCSS_Tones[codeplug["APRS"]["AX25 QT/DQT"]])
    else:
        codeplug["APRS"]["AX25 QT/DQT"] = "Off"

    debugMsg(2, "Parsing APRS DMR channels")
    codeplug["APRS"]["DMR channels"] = []
    for i in range(8):
        codeplug["APRS"]["DMR channels"].append(p.fromBytes( aprs_dmr_record_parameters, data [ aprs_dmr_channel_start_address + i * 8 : aprs_dmr_channel_start_address + (i+1) * 8 ] ))


    debugMsg(2, "Parsing DMR Service")
    codeplug["DMR Service"] = p.fromBytes(dmr_parameters, data)

    debugMsg(2, "Parsing Quick messages")
    # Quick messages - parsed manually as text items
    codeplug["Quick messages"] = []
    for i in range(message_block_1_count + message_block_2_count):
        if i < message_block_1_count:
            start_of_message = message_block_1_start_addr + i*message_record_size
        else:
            start_of_message = message_block_2_start_addr + (i-message_block_1_count)*message_record_size
        
        try:
            msg_str = data[start_of_message: start_of_message + message_record_size].decode('ascii').rstrip("\x00")
        except:
            debugMsg(1, "Skipped message number " + str(i) + " containing non-ascii text")
        if msg_str != "":
            debugMsg(3, "Adding message -" + msg_str)
            codeplug["Quick messages"].append(msg_str)

    #Encryption - #WONTDO
        
    debugMsg(2, "Parsing Contacts")
    debugMsg(4, "Contacts " + str(num_contacts))
    codeplug["Contacts"] = []
    for i in range(num_contacts):
        contact_data = data[contact_start_address + i*contact_record_size: contact_start_address + (i+1)*contact_record_size]
        parsed_contact = p.fromBytes(contact_parameters, contact_data)
        debugMsg(3, "Parsed contact - " + str(parsed_contact))
        
        codeplug["Contacts"].append(parsed_contact)
        
    #Digital alarm list - #TODO
    
    #Scan lists
    debugMsg(2, "Parsing Scan lists")
    codeplug["Scan lists"] = []
    for i in range(250):
        record_start_addr = scan_list_start_address + i*scan_list_record_size

        record = p.fromBytes(scan_list_info, data[record_start_addr : record_start_addr + scan_list_record_size])
        if record["Name"] != "":
            record["Selected channels"] = []
            for j in range(50):
                group = int.from_bytes(data[record_start_addr + 16 + j*4 : record_start_addr + 16 + (j*4) + 2], byteorder='little')
                channel = int.from_bytes(data[record_start_addr + 16 + (j*4) + 2 : record_start_addr + 16 + (j*4) + 4], byteorder='little')
                if group != 0 and channel != 0:
                    pair = {}
                    pair["Group"] = group
                    pair["Channel"] = channel
                    record["Selected channels"].append(pair)
            

            debugMsg(3, "Parsed scan list " + str(record))
            codeplug["Scan lists"].append(record)

    #Rx groups
    debugMsg(2, "Parsing Rx groups")
    codeplug["RX groups"] = []

    for i in range(250):
        record = p.fromBytes(rx_group_info, data[rx_group_start_address + i*rx_group_record_size: rx_group_start_address + (i+1) * rx_group_record_size])
        record["Contacts"] = []
        for j in range (100):
            id = int.from_bytes(data[rx_group_start_address + i*rx_group_record_size + 10 + j*2 : rx_group_start_address + i*rx_group_record_size + 10 + j*2 + 2], byteorder='little')
            if id != 0:
                record["Contacts"].append(id)
            
        # If it is empty, and has no name, ignore it.
        if record["Name"] != "" or len(record["Contacts"]) != 0:
            debugMsg(3, "Parsed rx group - " + str(record))
            codeplug["RX groups"].append(record)

    
    #Zones/channels
    debugMsg(2, "Parsing Zones")
    codeplug["Zones"] = []

    for i in range(num_zones):
        zone_data = data[zone_start_address + 32 * i:zone_start_address + 32 * (i+1)]
        parsed_zone = p.fromBytes(zone_info, zone_data)

        #This is the number of channels this zone contains
        num_channels = int.from_bytes(zone_data[0x0F:0x0F + 2], byteorder="little")
        #This is the number of bytes to offset from the start of the zone_start_address where these channels begin
        channels_offset = int.from_bytes(zone_data[0x0D:0x0D + 2], byteorder="little")

        debugMsg(3, "Zone " + parsed_zone["Name"] + " - channel offset address - " + hex(channels_offset))
        channels_offset = (channels_offset -1) * 32
        # Add an array for the channels
        parsed_zone["Channels"] = []

        #Parse the channels
        for i in range(num_channels):
            channel_data = data[zone_start_address + channels_offset + i*32: zone_start_address+channels_offset + (i+1)*32]
            channel = p.fromBytes(channel_info, channel_data)
            
            
            ##Time Slot "ON" check
            ##This fixes an issue with codeplugs written with this script being read with the CPS.
            ##Where all channels would have the timeslot set to ON, this is because there are 2 bits that need set high or low 
            ##to determing whether the timeslot is ON, plus the other 1 bit that determines the actual timeslot TS1 or TS2
            
            ##Here all that needs to be done is, read those 2 bits and parse whether its ON or an actual timeslot
            ##Override the timeslot to ON if needed. It cannot be ON if it's not simplex so force it to OFF.
            
            #Parse this separately, no need to store it in the JSON, just makes for a confusing parameter
            tempTSON_INFO = p.fromBytes(tson_info, channel_data)
            
            #If Rx and Tx frequencies are not the same, it's not simplex.. so can't have TS set to ON.. so override it to OFF
            if channel["Rx Freq"] != channel["Tx Freq"]:
                tempTSON_INFO["TS Rx ON"] = "OFF"
                tempTSON_INFO["TS Tx ON"] = "OFF"
            
            #If Rx is ON, override the TS parameter to ON
            if tempTSON_INFO["TS Rx ON"] == "ON":
                channel["TS Rx"] = "ON"
            
            #If Tx is ON, override the TS parameter to ON
            if tempTSON_INFO["TS Tx ON"] == "ON":
                channel["TS Tx"] = "ON"

            #If CTCSS or DCS are in use, swap out the parsed 'index value' with the correct value
            #TX tones
            if channel["Tone Type Tx"] == "CTCSS":
                channel["Tone Tx"] = CTCSS_Tones[channel["Tone Tx"]]
            elif channel["Tone Type Tx"] != "OFF": # It's DCS or DCS Invert
                channel["Tone Tx"] = DCS_Codes[channel["Tone Tx"]]

            #RX tones
            if channel["Tone Type Rx"] == "CTCSS":
                channel["Tone Rx"] = CTCSS_Tones[channel["Tone Rx"]]
            elif channel["Tone Type Rx"] != "OFF": # It's DCS or DCS Invert
                channel["Tone Rx"] = DCS_Codes[channel["Tone Rx"]]

            parsed_zone["Channels"].append(channel)
            debugMsg(3, "Parsed channel - " + str (channel))

        codeplug["Zones"].append(parsed_zone)

    #Jsonify it, and return it
    return json.dumps(codeplug, indent=2)

def compileCodeplug(data):
    codeplug = json.loads(data)
    
    num_contacts = len(codeplug["Contacts"])
    debugMsg(4, "Num Contacts " + str(num_contacts))
    num_zones = len(codeplug["Zones"])

    #Count the channels
    num_channels = 0
    for i in codeplug["Zones"]:
        num_channels += len(i["Channels"])

    contact_block_size = num_contacts * contact_record_size

    debugMsg(2, "Contacts Block Size " + str(contact_block_size))
    #Pad contact block to a multiple of 1K if needed
    if contact_block_size %1024 != 0:
        contact_block_size += 1024 - (contact_block_size%1024)
        debugMsg(2, "Contacts Block Padded " + str(contact_block_size))

    #Pad contact block to an odd number of blocks - possible fix for number of contacts > 64
    if (contact_block_size//1024)%2 == 0:
        debugMsg(2, "Contacts Block Count Was Even")
        contact_block_size = contact_block_size + 1024

    zone_start_address = contact_start_address + contact_block_size
    debugMsg(2, "Contact Start Address " + str(contact_start_address))
    debugMsg(2, "Zone Start Address " + str(zone_start_address))
    
    #The contacts start immediately after the zones.
    channel_start_address = zone_start_address + 32*num_zones
    debugMsg(2, "Channel Start Address " + str(channel_start_address))

    # Size the codeplug - it needs to be a whole number of 2048 blocks
    codeplug_size = channel_start_address + num_channels*channel_record_size
    if codeplug_size % 2048 != 0:
        codeplug_size += 2048 - (codeplug_size%2048)
    
    debugMsg(2, "Compiled codeplug of size " + str(codeplug_size))
    #Create the 'blank' codeplug
    template = bytearray(b"\x00" * codeplug_size)

    # Write in the counts
    template[zone_count_address:zone_count_address+2] = num_zones.to_bytes(length=2, byteorder='little')
    template[contact_count_address:contact_count_address+2] = num_contacts.to_bytes(length = 2, byteorder='little')
    template[channel_count_address:channel_count_address+2] = num_channels.to_bytes(length=2, byteorder='little')

    p = Parser()
    p.toBytes(template, dev_info, codeplug["Device info"])
    p.toBytes(template,basic_parameters, codeplug["Basic parameters"])
    p.toBytes(template, common_menu_parameters, codeplug["Common menu parameters"])
    p.toBytes(template,prompt_tone_parameters, codeplug["Prompt Tone"])
    p.toBytes(template,indicator_parameters, codeplug["Indicators"])
    p.toBytes(template,button_preset_parameters, codeplug["Preset buttons"])
    p.toBytes(template,mic_gain_parameters, codeplug["Mic gain"])
    p.toBytes(template,dmr_parameters, codeplug["DMR Service"])

    #codeplug["APRS"]["AX25 TX Freq"] = int(codeplug["APRS"]["AX25 TX Freq"] / 10)


    if codeplug["APRS"]["AX25 QT/DQT"] == "Off":
        codeplug["APRS"]["AX25 QT/DQT"] = 0
    elif codeplug["APRS"]["AX25 QT/DQT"].endswith("I"):
        codeplug["APRS"]["AX25 QT/DQT"] = DCS_Codes.index(int(str(codeplug["APRS"]["AX25 QT/DQT"]).replace('D', '').replace('I', '')))+160
    elif codeplug["APRS"]["AX25 QT/DQT"].endswith("N"):
        codeplug["APRS"]["AX25 QT/DQT"] = DCS_Codes.index(int(str(codeplug["APRS"]["AX25 QT/DQT"]).replace('D', '').replace('N', '')))+53
    else:
        codeplug["APRS"]["AX25 QT/DQT"] = CTCSS_Tones.index(codeplug["APRS"]["AX25 QT/DQT"])
        
    p.toBytes(template, aprs_parameters, codeplug["APRS"])

    #Copy the APRS DMR channels in to place.
    aprs_dmr_record_count = 0
    for record in codeplug["APRS"]["DMR channels"]:
        debugMsg(4, "Writing APRS DMR channel record " + str(aprs_dmr_record_count))
        debugMsg(5, "Record : " + str(record))
        aprs_dmr_record = bytearray(8)
        p.toBytes(aprs_dmr_record, aprs_dmr_record_parameters, record)
        template[aprs_dmr_channel_start_address + 8 * aprs_dmr_record_count: aprs_dmr_channel_start_address + 8 * (aprs_dmr_record_count + 1) ] = aprs_dmr_record
        aprs_dmr_record_count = aprs_dmr_record_count + 1

    #Write in the quick messages
    for i in range (len(codeplug["Quick messages"])):
        debugMsg(4, "Parsing message " + codeplug["Quick messages"][i])
        #Calculate whether this message will go into block 1 or block 2
        if i < message_block_1_count:
            start_address = message_block_1_start_addr + (i*message_record_size)
        else:
            start_address = message_block_2_start_addr + ((i-message_block_1_count)*message_record_size)

        # Encode (+ truncate) the message as needed
        encoded_str = codeplug["Quick messages"][i][0:message_record_size].encode('ascii')
        template[start_address: start_address + len(encoded_str)] = encoded_str
        
    # Write in the contacts
    count = 0
    for contact in codeplug["Contacts"]:
        contact_record = bytearray(contact_record_size)
        p.toBytes(contact_record, contact_parameters, contact)
        debugMsg(4, "Contact " + str(contact))
        template[contact_start_address + contact_record_size*count:contact_start_address + contact_record_size*(count+1) ] = contact_record
        count = count + 1 
            
    # Scan list
    count = 0
    for scan_list in codeplug["Scan lists"]:
        scan_list_record = bytearray(scan_list_record_size)
    
        p.toBytes(scan_list_record, scan_list_info, scan_list)

        for i in range(len (scan_list["Selected channels"])):
            scan_list_record[16 + i *4 : 16 + i *4 + 2] = scan_list["Selected channels"][i]["Group"].to_bytes(byteorder="little", length=2)
            scan_list_record[16 + i *4 + 2 : 16 + i *4 + 4] = scan_list["Selected channels"][i]["Channel"].to_bytes(byteorder="little", length=2)

        template[scan_list_start_address + (scan_list_record_size * count) : scan_list_start_address + (scan_list_record_size * (count+1))] = scan_list_record
        count = count + 1

    # RX groups go next
    count = 0
    for group in codeplug["RX groups"]:
        group_record = bytearray(rx_group_record_size)
        p.toBytes(group_record, rx_group_info, group)

        #Now, add the contacts
        for i in range(len(group["Contacts"])):
            group_record[10 + i *2 : 10 + (i+1)*2] = group["Contacts"][i].to_bytes(byteorder="little", length=2)
        #Insert it into the codeplug
        template[rx_group_start_address + rx_group_record_size *count : rx_group_start_address + rx_group_record_size *(count+1)] = group_record
        count = count + 1
    

    # Write the zones into place
    count = 0
    for i in codeplug["Zones"]:
        channel_offset = len(codeplug["Zones"]) + 1
        #Sum the channels up in all the previous zones (if any) to calculate the offset of this zone's channels within the zone/channel block
        for j in range(count):
            channel_offset += len(codeplug["Zones"][j]["Channels"])
            
        debugMsg(4, "Channel offset for " + i["Name"] + " was " + hex(channel_offset))
        zone_record = bytearray(zone_record_size)
            
        p.toBytes(zone_record,zone_info, i)
        # Update the offset field of the zone record so it points to the channel
        zone_record[0x0D:0x0D+2] = channel_offset.to_bytes(length=2, byteorder="little")
        #Populate the channel count with the number of channels within this zone
        zone_record[0x0F:0x0F+2] = len(i["Channels"]).to_bytes(length=2, byteorder="little")

        template[zone_start_address + (zone_record_size * count):zone_start_address + (zone_record_size * (count + 1)) ] = zone_record
        count = count + 1
    
    #Write the channels into place
    count = 0
    for i in codeplug["Zones"]:
        for channel in i["Channels"]:
            debugMsg(4, "Writing channel " + str(channel["ID"]) + " - " + channel["Name"] + " to address : " + hex(channel_start_address + (channel_record_size * count)))
            #Need to turn the CTCSS/DCS code values back into the enumerated constant.
            if channel["Tone Type Tx"] == "CTCSS":
                channel["Tone Tx"] = CTCSS_Tones.index(channel["Tone Tx"])
            elif channel["Tone Type Tx"] != "OFF": # It's DCS or DCS Invert
                channel["Tone Tx"] = DCS_Codes.index(channel["Tone Tx"])
            #RX tones
            if channel["Tone Type Rx"] == "CTCSS":
                channel["Tone Rx"] = CTCSS_Tones.index(channel["Tone Rx"])
            elif channel["Tone Type Rx"] != "OFF": # It's DCS or DCS Invert
                channel["Tone Rx"] = DCS_Codes.index(channel["Tone Rx"])
            
            ## Time Slot "ON" check
            ## Now when we read the JSON parameters, if timeslot is set to ON then we set the bits accordingly
            ## Again, if it's not simplex, force it to OFF
            
            tempTSON_INFO = {}
            tempTSON_INFO["TS Rx ON"] = "OFF"
            tempTSON_INFO["TS Tx ON"] = "OFF"
            
            # If Rx and Tx frequencies are not the same, it's not simplex.. so can't have TS set to ON.. so override it to OFF
            if channel["Rx Freq"] != channel["Tx Freq"]:
                tempTSON_INFO["TS Rx ON"] = "OFF"
                tempTSON_INFO["TS Tx ON"] = "OFF"

            # If Rx is ON, override the TS parameter to ON
            if channel["TS Rx"] == "ON":
                tempTSON_INFO["TS Rx ON"] = "ON"
            
            # If Tx is ON, override the TS parameter to ON
            if channel["TS Tx"] == "ON":
                tempTSON_INFO["TS Tx ON"] = "ON"
                
            channel_record = bytearray(channel_record_size)
            p.toBytes(channel_record,channel_info, channel)
            
            # Now parse it to bytes, after the rest of the channel record is parsed, should only change the 2 bits needed
            p.toBytes(channel_record,tson_info, tempTSON_INFO)
        
            template[channel_start_address + (channel_record_size * count) : channel_start_address + (channel_record_size * (count + 1))] = channel_record
            count = count + 1

    if len(template) != codeplug_size:
        print("Codeplug size has been altered - this is a bug")
        print("Should be " + str(codeplug_size) + ", was " + len(template))
        sys.exit(4)

    return template

def downloadCodeplug(serialdevice):
    plug = bytearray()
    with serial.Serial(serialdevice) as port:
        port.baudrate = 115200
        port.timeout = 10
        print("Establishing Connection To Radio...")

        if (port.isOpen() == False):
            port.Open()
    
        port.write("Flash Read ".encode('ascii'))
        port.write(b"\x00\x3c\x00\x00\x00\x00\x00\x39\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        response = port.read(103)
        if len(response) <= 1:
            print("Timeout: No Response...")
            sys.exit(1)
        else:
            print("Success: Begin Download...")
        
        if debug_level == 4:
            print("Message rx from plug download handshake:")
            print(response)
            for i in range(len(response)):
                print(hex(response[i]) + " ",end='')

        num_pages = response[18] + response[20]
        print("Expecting " + str(num_pages) + " Blocks")
        for i in range(num_pages):
            print("Reading Block " + str(i+1) + " of " + str(num_pages))
            port.write("Read".encode('ascii'))
            plug += port.read(2048)
    print("Download Complete...")
    return plug

def uploadCodeplug(serialdevice, data):
    #Pad the data to a multiple of 2048 bytes.
    size = len(data)

    if size % 2048 != 0:
        data += (b"\x00" * (2048 - (size%2048)))

    block_count = int (len(data) / 2048)
    if block_count > 0xFF:
        print("Codeplug Too Large!")
        sys.exit(4)

    response = bytearray("Flash Write".encode('ascii')) + b"\x00\x3c\x00\x00\x00\x00\x00\xFF\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    response[18] = block_count

    with serial.Serial(serialdevice) as port:
        port.baudrate = 115200
        port.timeout = 10
        print("Establishing Connection To Radio...")

    
        if (port.isOpen() == False):
            port.Open()
            
        port.write(response)
        bytes = port.read(93)
        if len(bytes) <= 1:
            print("Timeout: No Response...")
            sys.exit(1)
        else:
            print("Success: Begin Upload...")
        print("Writing " + str(block_count) + " Blocks")
    
        if bytes[2:7].decode('ascii') != "Write":
            print("Unexpected Response From Radio")
            sys.exit(2)
        for i in range(block_count):
            print("Writing Block " + str(i+1) + " of " + str(block_count))
            port.write(data[2048*i:2048*(i+1)])
            bytes = port.read(5)
            if bytes.decode('ascii') == "Write":
                pass
            elif i == block_count-1 and bytes.decode('ascii') == "Check":
                print("Upload Complete...")
            else:
                print("Unexpected Response From Radio")
                sys.exit(2)
    print("Upload Complete...")

def uploadHamContacts(serialdevice, csvfile, contactbytes):

    RADIO_ID = []
    CONTACT_INFO = []

    with open(csvfile, 'r', encoding="ascii", errors="surrogateescape") as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        for row in csv_reader:
            RADIO_ID.append(int(row['RADIO_ID']))
            if len(row['LAST_NAME']) > 0 and row['LAST_NAME'] != " ":
                CONTACT_INFO.append(row['CALLSIGN']+","+row['FIRST_NAME']+" "+row['LAST_NAME']+","+row['CITY']+","+row['STATE']+","+row['COUNTRY'])
            else:
                CONTACT_INFO.append(row['CALLSIGN']+","+row['FIRST_NAME']+","+row['CITY']+","+row['STATE']+","+row['COUNTRY'])
    
    contactcount = len(RADIO_ID)
    hamcontacts = bytearray(b"\x00" * contactbytes)

    for i in range(contactcount):
        hamcontacts[contactbytes*i:contactbytes*i+2] = RADIO_ID[i].to_bytes(length=3, byteorder='little')
        hamcontacts[contactbytes*i+3:] = CONTACT_INFO[i].encode('ascii', 'ignore')

        size = len(hamcontacts[contactbytes*i:contactbytes*i+contactbytes])
        if size % contactbytes != 0:
            hamcontacts[contactbytes*i:contactbytes*i+contactbytes] += (b"\x00" * (contactbytes - (size%contactbytes)))
            
    if len(hamcontacts) % 2048 != 0:
        hamcontacts[len(hamcontacts):] = (b"\x00" * (2048 - (len(hamcontacts)%2048)))

    print("Uploading " + str(contactcount) + " Contacts (" + str(contactbytes) + "bytes)")

    block_count = int (len(hamcontacts) / 2048)
    if block_count > 0x493E:
        print("Too Many Ham Contacts - 300,000 max")
        sys.exit(7)
    
    writecommand = b""
    writecommand += bytearray("Flash Write".encode('ascii')) 
    writecommand += b'\x81\x10\x00\x00\x00\x00'
    writecommand += bytearray(block_count.to_bytes(2, 'big')) #block count
    writecommand += b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x2B'
    writecommand += bytearray(contactbytes.to_bytes(1, 'little')) # 16 or 128
    writecommand += b'\x2B\x00'
    writecommand += bytearray(contactcount.to_bytes(3, 'big')) #contact count

    with serial.Serial(serialdevice) as port:
        port.baudrate = 115200
        port.timeout = 10
        print("Establishing Connection To Radio...")
        
        if (port.isOpen() == False):
            port.Open()
    
        port.write(writecommand)
        bytes = port.read(93)
        if len(bytes) <= 1:
            print("Timeout: Empty Response...")
            sys.exit(1)
        elif bytes[2:7].decode('ascii') == "Write":
            print("Success: Begin Upload...")
            print("Writing " + str(block_count) + " Blocks")
            for i in range(block_count):
                print("Writing Block " + str(i+1) + " of " + str(block_count))
                port.write(hamcontacts[2048*i:2048*(i+1)])
                bytes = port.read(5)
                if bytes[0:6].decode('ascii') == "Write":
                    pass
                elif bytes[0:6].decode('ascii') == "Check":
                    print("Upload Complete...")
                else:
                    print("Unexpected Response From Radio")
                    sys.exit(2)
        else:
            print("Unexpected Response From Radio")
            sys.exit(2)

def uploadHamGroups(serialdevice, csvfile):

    GROUP_ID = []
    GROUP_NAME = []

    with open(csvfile, 'r', encoding="ascii", errors="surrogateescape") as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        for row in csv_reader:
            GROUP_ID.append(int(row['GROUP_ID']))
            GROUP_NAME.append(row['GROUP_NAME'])
    
    groupcount = len(GROUP_ID)
    hamgroups = bytearray(b"\x00" * 16)

    for i in range(groupcount):
        hamgroups[16*i:16*i+2] = GROUP_ID[i].to_bytes(length=3, byteorder='little')
        hamgroups[16*i+3:] = GROUP_NAME[i].encode('ascii', 'ignore')

        size = len(hamgroups[16*i:16*i+16])
        if size % 16 != 0:
            hamgroups[16*i:16*i+16] += (b"\x00" * (16 - (size%16)))
            
    if len(hamgroups) % 2048 != 0:
        hamgroups[len(hamgroups):] = (b"\x00" * (2048 - (len(hamgroups)%2048)))

    print("Uploading " + str(groupcount) + " Ham Groups")

    block_count = int(len(hamgroups) / 2048)
    if block_count > 0xEB:
        print("Too Many Ham Groups - 30,000 max")
        sys.exit(8)
    
    writecommand = bytearray("Flash Write".encode('ascii')) 
    writecommand += b'\x82\x98\x00\x00\x00\x00'
    writecommand += bytearray(block_count.to_bytes(2, 'big')) #block count
    writecommand += b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x2B\x10\x2B\x00'
    writecommand += bytearray(groupcount.to_bytes(3, 'big')) #contact count

    with serial.Serial(serialdevice) as port:
        port.baudrate = 115200
        port.timeout = 10
        print("Establishing Connection To Radio...")
        
        if (port.isOpen() == False):
            port.Open()
    
        port.write(writecommand)
        bytes = port.read(93)
        if len(bytes) <= 1:
            print("Timeout: Empty Response...")
            sys.exit(1)
        elif bytes[2:7].decode('ascii') == "Write":
            print("Success: Begin Upload...")
            print("Writing " + str(block_count) + " Blocks")
            for i in range(block_count):
                print("Writing Block " + str(i+1) + " of " + str(block_count))
                port.write(hamgroups[2048*i:2048*(i+1)])
                bytes = port.read(5)
                if bytes[0:6].decode('ascii') == "Write":
                    pass
                elif bytes[0:6].decode('ascii') == "Check":
                    print("Upload Complete...")
                else:
                    print("Unexpected Response From Radio")
                    sys.exit(2)
        else:
            print("Unexpected Response From Radio")
            sys.exit(2)

def uploadFirmware(serialdevice, data):
    with serial.Serial(serialdevice) as port:
        port.baudrate = 115200
        port.timeout = 10
        
        if (port.isOpen() == False):
            port.Open()
            
        print("Starting Firmware Upload Process")

        size = len(data)
        if size % 2048 != 0:
            data += (b"\x00" * (2048 - (size%2048)))
            
        num_blocks = int(len(data) / 2048)
        
        port.write("Erase".encode('ascii'))
        port.write(b"\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00")
        port.write((num_blocks-1).to_bytes(length=2, byteorder='big'))
        
        
        bytes = port.read(33) #IAP Ver and Date ?
        bytes = port.read(8) #Should be "Erase ok"
        if len(bytes) <= 1:
            print("Timeout: Empty Response...")
            sys.exit(1)
        elif bytes.decode('ascii') == "Erase ok":
            print("Erase OK - Begin Writing")
        else:
            print("Unexpected Response From Radio")
            sys.exit(2)
        
        for i in range(num_blocks):
            block = data[2048*i:2048*(i+1)]
            print("Writing Block " +str(i+1) + " of " + str(num_blocks))
            
            port.write(block)

            bytes = port.read(3) #Check this says "kyd"
            if bytes.decode('ascii') == "kyd":
                pass
            else:
                print("Unexpected Response From Radio")
                sys.exit(2)
        bytes = port.read(13)
        if bytes[0:8].decode('ascii') == "Checksum":
            pass #Update Complete
        else:
            print("Unexpected Response From Radio - May be normal - Firmware upload is not perfect :)")
            sys.exit(5)
    print("Firmware Upload Complete")

def debugMsg(level, message):
    if level <= debug_level:
        print(message)

# Script begins here
debug_level = 0
default_serial_device = ""

if platform.system() == "Linux":
    default_serial_device = "/dev/ttyUSB0"
elif platform.system() == "Windows":
    default_serial_device = "COM1"

parser = argparse.ArgumentParser(
    description = "Retevis RT73 codeplug/firmware upgrade tool, GNU GPL v3 or later, (C) 2020-21 David Pye davidmpye@gmail.com"
)
parser.add_argument('action', type = str, choices=["upload", "download", "flash_fw", "download_bin", "upload_bin", "decompile_bin", "upload_hamcontacts", "upload_hamgroups"], help=
    "upload - Compile and upload a JSON-formatted file to the radio,"+
    "download - Download and convert the radio's codeplug to a JSON-formatted file,"+
    "flash_fw - Upgrade the radio's firmware (radio must be powered on while pressing P1 and be displaying a grey screen before upload),"+
    "upload_hamcontacts - Upload Ham Contacts to the radio, file must be in RadioID.net CSV format and specify type with --contactbytes {16 or 128}"+
    "upload_hamgroups - Upload Ham Groups to the radio, file must be in CSV format with headers 'GROUP_NAME' & 'GROUP_ID'")

parser.add_argument("filename", type=str, help="Filename to upload, or to save")

parser.add_argument('--contactbytes', default=0, type = int, choices=[16,128], help="Ham Contacts Bytes (16 or 128)")

parser.add_argument('--device', default = default_serial_device, help = "Specify device to use (default COM1 on Windows, default /dev/ttyUSB0 on Linux")
parser.add_argument('--debuglevel', default=[0], type = int, nargs = 1, help="Debug level (0 = default, 4 = max)")
args = parser.parse_args()

debug_level = args.debuglevel[0]

if args.action == "download":
    data = downloadCodeplug(args.device)
    json = decompileCodeplug(data)
    f = open(args.filename, 'w')
    f.write(json)
    f.close()
elif args.action == "upload":
    f = open(args.filename, 'r')
    input = f.read()
    data = compileCodeplug(input)
    f.close()
    uploadCodeplug(args.device, data)
elif args.action == "flash_fw":
    f = open(args.filename,'rb')
    fw = f.read()
    uploadFirmware(args.device, fw)
elif args.action == "download_bin":
    f = open(args.filename, 'wb')
    f.write(downloadCodeplug(args.device))
elif args.action == "upload_bin":
    f = open(args.filename, 'rb')
    data = f.read()
    uploadCodeplug(args.device, data)
elif args.action == "decompile_bin":
    f = open(args.filename, 'rb')
    input = f.read()
    data = decompileCodeplug(input)
    f.close()
    ff = open(args.filename[:-4]+".json", 'w')
    ff.write(data)
elif args.action == "upload_hamcontacts":
    if args.contactbytes == 0:
        print("Missing Argument '--contactbytes {16 or 128}")
        sys.exit(6)
    uploadHamContacts(args.device, args.filename, args.contactbytes)
elif args.action == "upload_hamgroups":
    uploadHamGroups(args.device, args.filename)
