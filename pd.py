##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022-2023 Arnix Chen <arnix2@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
import logging

# Constants defined for DFPlayer Mini's RX / TX data
RX = 0
TX = 1
# Constants defined for DFPlayer Mini's Transaction data field index
CMD_IDX = 3
PARA1_IDX = 5
PARA2_IDX =6

def zeroPadHex(x):
    zeroPadding = ''
    if (len(hex(x)[2:])<2):
        zeroPadding = '0'
    return '0x' + zeroPadding + hex(x)[2:].upper()

class Decoder(srd.Decoder):
    api_version = 3
    id = 'dfplayer_mini'
    name = 'DFPlayerMini'
    longname = 'DFPlayer Mini'
    desc = 'Procotol decoder for DFPlayer Mini'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = []
    tags = ['mp3/uart']
    annotations = (
        ('rx', 'DFPlayerMini RX Data'),
        ('tx', 'DFPlayerMini TX Data'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.cmd = [[], []]
        self.cmdInfo = ""
        self.ss_block = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, data):
        self.put(self.ss_block, self.es_block, self.out_ann, data)

    def parseCmd(self, rxtx, cmd, msb, lsb):

        cmdDict = {
            0x01: {RX:['Play Next track', None], TX:[]},
            0x02: {RX:['Play Previous track', None], TX:[]},
            0x03: {RX:['Playback track {} in root folder', 'msb+lsb'], TX:[]},
            0x04: {RX:['Increase volume', None], TX:[]},
            0x05: {RX:['Decrease volume', None], TX:[]},
            0x06: {RX:['Set volume to {}', 'lsb'], TX:[]},
            0x07: {RX:['Set EQ to {}', 'parselsb', {0:'Normal', 1:'Pop', 2:'Rock', 3:'Jazz', 4:'Classic', 5:'Bass'}], TX:[]},
            0x08: {RX:['Set Single REPEAT to track {}', 'msb+lsb'], TX:[]},
            0x09: {RX:['Specify {} to play', 'parselsb', {0:'USB Stick', 2:'SD Card', 4:'USB cable to PC'}], TX:[]},
            0x0A: {RX:['Set Sleep', None], TX:[]},
            0x0C: {RX:['Module Reset', None], TX:[]},
            0x0D: {RX:['Play', None], TX:[]},
            0x0E: {RX:['Pause', None], TX:[]},
            0x0F: {RX:['Play track {} from folder {}', 'lsb:msb'], TX:[]},
            0x10: {RX:['Audio amplification setting to {}', 'lsb'], TX:[]},
            0x11: {RX:['Set all repeat playback', 'lsb'], TX:[]},
            0x12: {RX:['Play track {} from MP3 folder', 'msb+lsb' ], TX:[]},
            0x13: {RX:['Play track {} from ADVERT folder', 'msb+lsb' ], TX:[]},
            0x15: {RX:['Stop advertisement and go back to interrupted music', None], TX:[]},
            0x16: {RX:['Stop', None], TX:[]},
            0x17: {RX:['Set folder {} to REPEAT playback', 'lsb'], TX:[]},
            0x18: {RX:['Set RANDOM playback', None], TX:[]},
            0x19: {RX:['Set REPEAT playback of current track', None], TX:[]},
            0x1A: {RX:['Set DAC: {}', 'parselsb', {0x00:'Turn ON', 0x01:'Turn OFF'}], TX:[]},
            0x3A: {RX:[], TX:['Storage {} is plugged in', 'parselab', {1:'USB Stick', 2:'SD Card', 4:'USB cable to PC'}]},
            0x3B: {RX:[], TX:['Storage {} is pulled out :', 'parselab', {1:'USB Stick', 2:'SD Card', 4:'USB cable to PC'}]},
            0x3C: {RX:[], TX:['USB Stick play track {} finished', 'msb+lsb']},
            0x3D: {RX:[], TX:['SD Card play track {} finished', 'msb+lsb']},
            0x3E: {RX:[], TX:['USB cable to PC playing track {} finished', 'msb+lsb']},
            0x3F: {RX:['Query current online storage', None], TX:['(PowerOn Report) Current online storage: {}', 'parselsb', { 0x0:'None', 0x01:'USB Stic', 0x02:'SD Card', 0x03:'USB Stick & SD Card', 0x04:'PC', 0x0F:'SD Card & USB Stick & PC'}]},
            0x40: {RX:[], TX:['Module returns error : {}', 'parselsb', {1:'Module Busy', 2:'Currently sleep mode', 3:'Serial rx error', 4:'Checksum incorrect', 5:'Track out of scope', 6:'Specified track is not found', 7:'Insertion error', 8:'SD card reading failed', 9:'Entered into sleep mode'}]},
            0x41: {RX:[], TX:['Module ACK', None]},
            0x42: {RX:['Query current status', None], TX:['Report current status: {}', 'parsemsb+lsb', {0:'' ,1:'USB Stick', 2:'SD Card', 3:'Module in sleep mode'}, {0:'Stopped', 1:'Playing', 2:'Paused'}]},
            0x43: {RX:['Query current volume', None], TX:['Current volume is {}', 'lsb']},
            0x44: {RX:['Query current EQ', None], TX:['Report current EQ', 'parselsb', {0:'Normal', 1:'Pop', 2:'Rock', 3:'Jazz', 4:'Classic', 5:'Bass'}]},
            0x47: {RX:['Query number of tracks in root of USB Stick', None], TX:['There are {} tracks in root of USB Stick', 'msb+lsb']},
            0x48: {RX:['Query number of tracks in root of SD Card', None], TX:['There are {} tracks in root of SD Card', 'msb+lsb']},
            0x4B: {RX:['Query current track in USB Stick', None], TX:['Current playing track in USB Stick: {}', 'msb+lsb']},
            0x4C: {RX:['Query current track in SD Card', None], TX:['Current playing track in SD Card: {}', 'msb+lsb']},
            0x4E: {RX:['Query number of tracks in folder {}', 'lsb'], TX:['There are {} tracks in folder', 'lsb']},
            0x4F: {RX:['Query number of folders in current storage', None], TX:['There are {} folders in current storage', 'lsb']},
        }

        try:
            info = cmdDict[cmd][rxtx]
        except:
            return ''

        newType = ''
        if (self.data_type == 'Tx'):
            newType = 'Rx'
        else:
            newType = 'Tx'
            
        if (len(info)<2):
            ## WRONG TRANSMISSION TYPE ASSIGNMENT!
            if (self.whenver_wrong_data_type_assign_was_found == 'Flip autamatically'):
                self.data_type = newType
                info = cmdDict[cmd][rxtx]
            else:
                return '['+ zeroPadHex(cmd) + '] ' + 'WRONG DATA TYPE ASSIGNED! This should be some kind of ' + newType + ' data'

        if ((info[1] == None) and (rxtx==1) and ((msb !=0) or (lsb!=0))):
            ## WRONG TRANSMISSION TYPE ASSIGNMENT!
            if (self.whenver_wrong_data_type_assign_was_found == 'Flip autamatically'):
                self.data_type = newType
                info = cmdDict[cmd][rxtx]
            else:
                return '['+ zeroPadHex(cmd) + '] ' + 'WRONG DATA TYPE ASSIGNED! This should be some kind of ' + newType + ' data'

        if (info[1] == None):
            message = info[0]
        else:
            if (info[1] == 'lsb'):
                message = info[0].format(lsb)
            elif (info[1] == 'msb+lsb'):
                message = info[0].format(msb * 256 + lsb)
            elif (info[1] == 'msb:lsb'):
                message = info[0].format(msb,lsb)
            elif (info[1] == 'lsb:msb'):
                message = info[0].format(lsb,msb)
            elif (info[1] == 'parsemsb+lsb'):
                if (info[2][msb] == ''):
                    message = info[0]
                else:
                    message = info[0].format(info[2][msb] + ' ' + info[3][lsb])
            elif (info[1] == 'parselsb'):
                message = info[0].format(info[2][lsb])
                
        return '['+ zeroPadHex(cmd) + '] ' + message

    def decode(self, ss, es, data):
        ptype, rxtx, pdata = data

        # For now, ignore all UART packets except the actual data packets.
        if ptype != 'DATA':
            return

        # We're only interested in the byte value (not individual bits).
        char = pdata[0]
        self.data_type = {0:'Rx', 1:'Tx'}[rxtx]
        if (char == 0x7E):
            self.cmd[rxtx].clear()
            self.cmd[rxtx].append(char)
            self.ss_block = ss
        else:
            self.cmd[rxtx].append(char)
            if (char == 0xEF):
                self.es_block = es

        if len(self.cmd[rxtx]) == 10:
            self.cmdInfo = self.parseCmd(rxtx, self.cmd[rxtx][CMD_IDX], self.cmd[rxtx][PARA1_IDX], self.cmd[rxtx][PARA2_IDX])
            self.putx([rxtx, [self.cmdInfo]])
