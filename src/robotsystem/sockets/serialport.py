#!/usr/bin/env python
# coding: utf-8
"""
@File   : serialport.py
@Author : Steven.Shen
@Date   : 2021/9/6
@Desc   : 
"""
import re
import time
from serial import Serial, EIGHTBITS, STOPBITS_ONE, PARITY_NONE
from robotsystem.model.basicfunc import IsNullOrEmpty
from robotsystem.sockets.communication import CommAbstract
import robotsystem.conf.logprint as lg


class SerialPort(CommAbstract):

    def __init__(self, port, baudRate=115200, write_timeout=1, timeout=0.5):
        self.ser = Serial(port, baudrate=baudRate, write_timeout=write_timeout, timeout=timeout, bytesize=EIGHTBITS,
                          stopbits=STOPBITS_ONE, parity=PARITY_NONE)

    def open(self, *args):
        if not self.ser.isOpen():
            self.ser.open()

    def close(self):

        self.ser.close()
        lg.logger.debug(f"{self.ser.port} serialPort close {'success' if not self.ser.is_open else 'fail'} !!")

    def read(self):
        self.ser.read()

    def write(self, date: str):
        # date_bytes = date.encode('utf-8')
        self.ser.write(date.encode('utf-8'))

    def SendCommand(self, command, exceptStr, timeout=10, newline=True):

        # result = False
        strRecAll = ''
        start_time = time.time()
        try:
            self.ser.timeout = timeout
            if newline and not IsNullOrEmpty(command):
                command += "\n"
            else:
                pass
            time.sleep(0.01)
            lg.logger.debug(f"{self.ser.port}_SendComd-->{command}")
            self.ser.reset_output_buffer()
            self.ser.reset_input_buffer()
            self.write(command)
            self.ser.flush()
            strRecAll = self.ser.read_until(exceptStr.encode('utf-8')).decode('utf-8')
            lg.logger.debug(strRecAll)
            if re.search(exceptStr, strRecAll):
                lg.logger.info(f'wait until {exceptStr} success in {round(time.time() - start_time, 3)}s')
                result = True
            else:
                lg.logger.error(f'wait until {exceptStr} timeout in {round(time.time() - start_time, 3)}s')
                result = False
            return result, strRecAll
        except Exception as e:
            lg.logger.exception(e)
            return False, strRecAll


if __name__ == "__main__":
    com = SerialPort('COM7', 115200, 1, 1)
    com.SendCommand('', 'luxshare SW Version :', 100)
    com.SendCommand('\n', 'root@OpenWrt:/#', 3)
    com.SendCommand('luxshare_tool --get-mac-env', 'root@OpenWrt:/#')
