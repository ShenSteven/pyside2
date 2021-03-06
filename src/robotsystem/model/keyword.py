#!/usr/bin/env python
# coding: utf-8
"""
@File   : keyword.py
@Author : Steven.Shen
@Date   : 2021/11/9
@Desc   : 
"""
import logging
import re

from robotsystem.peak.FBL_PLIN_USB import Bootloader
from robotsystem.sockets.serialport import SerialPort
from robotsystem.sockets.telnet import TelnetComm
import robotsystem.conf.globalvar as gv
import robotsystem.conf.logprint as lg
import subprocess
import time
import psutil
from .basicfunc import IsNullOrEmpty
from inspect import currentframe


def CompareLimit(limitMin, limitMax, value, is_round=False):
    if IsNullOrEmpty(limitMin) and IsNullOrEmpty(limitMax):
        return True, ''
    if IsNullOrEmpty(value):
        return False, ''
    temp = round(float(value)) if is_round else float(value)
    if IsNullOrEmpty(limitMin) and not IsNullOrEmpty(limitMax):  # 只需比较最大值
        lg.logger.debug("compare Limit_max...")
        return temp <= float(limitMax), ''
    if not IsNullOrEmpty(limitMin) and IsNullOrEmpty(limitMax):  # 只需比较最小值
        lg.logger.debug("compare Limit_min...")
        return temp >= float(limitMin), ''
    if not IsNullOrEmpty(limitMin) and not IsNullOrEmpty(limitMax):  # 比较最小最大值
        lg.logger.debug("compare Limit_min and Limit_max...")
        if float(limitMin) <= temp <= float(limitMax):
            return True, ''
        else:
            if temp < float(limitMin):
                return False, 'TooLow'
            else:
                return False, 'TooHigh'


def ping(host, timeout=1):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host test_name is valid.
    """
    param = '-n' if gv.win else '-cf'
    command = f'ping {param} 1 {host}'
    try:
        ret = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding=("gbk" if gv.win else "utf8"), timeout=timeout)
        if ret.returncode == 0 and 'TTL=' in ret.stdout:
            lg.logger.debug(ret.stdout)
            return True
        else:
            lg.logger.error(f"error:{ret.stdout},{ret.stderr}")
            return False
    except subprocess.TimeoutExpired:
        lg.logger.debug(f'ping {host} Timeout.')
        return False
    except Exception as e:
        lg.logger.exception(e)
        return False


def run_cmd(command, timeout=1):
    """send command, command executed successfully return true,otherwise false"""
    try:
        ret = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding=("gbk" if gv.win else "utf8"), timeout=timeout)
        if ret.returncode == 0:  # 表示命令下发成功，不对命令内容结果做判断
            lg.logger.debug(ret.stdout)
            return True
        else:
            lg.logger.error(f"error:{ret.stderr}")
            return False
    except Exception as e:
        lg.logger.exception(e)
        return False


def kill_process(process_name, killall=True):
    try:
        for pid in psutil.pids():
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                if p.name() == process_name:
                    p.kill()
                    lg.logger.debug(f"kill pid-{pid},test_name-{p.name()}")
                    time.sleep(1)
                    if not killall:
                        break
        return True
    except Exception as e:
        lg.logger.exception(e)
        return False


def process_exists(process_name):
    pids = psutil.pids()
    ps = [psutil.Process(pid) for pid in pids]
    process_names = [p.name for p in ps]
    if process_name in process_names:
        return True
    else:
        return False


def start_process(full_path, process_name):
    """if process exists, return , otherwise start it and check"""
    try:
        if not process_exists(process_name):
            run_cmd(full_path)
            time.sleep(3)
            return process_exists(process_name)
        else:
            return True
    except Exception as e:
        lg.logger.exception(e)
        return False


def restart_process(full_path, process_name):
    """kill and start"""
    try:
        if kill_process(process_name):
            return start_process(full_path, process_name)
    except Exception as e:
        lg.logger.exception(e)
        return False


def register(name, email, **kwargs):
    print('test_name:%s, age:%s, others:%s', (name, email, kwargs))


def subStr(SubStr1, SubStr2, revStr):
    values = re.findall(f'{SubStr1}(.*?){SubStr2}', revStr)
    if len(values) == 1:
        testValue = values[0]
        lg.logger.debug(f'get TestValue:{testValue}')
        return testValue
    else:
        raise Exception(f'get TestValue exception:{values}')


def testKeyword(item, testSuite):
    # time.sleep(0.02)
    # invoke_return = QMetaObject.invokeMethod(
    #     ui.mainform.MainForm.main_form,
    #     'showMessageBox',
    #     Qt.BlockingQueuedConnection,
    #     QtCore.Q_RETURN_ARG(QMessageBox.StandardButton),
    #     QtCore.Q_ARG(str, 'ERROR!'),
    #     QtCore.Q_ARG(str, 'Text to msgBox'),
    #     QtCore.Q_ARG(int, 2))
    # lg.logger.debug(f"invoke_return:{invoke_return}")
    # if invoke_return == QMessageBox.Yes or invoke_return == QMessageBox.Ok:
    #     lg.logger.debug("yes ok")
    # else:
    #     lg.logger.debug('no')

    # lg.logger.debug(f'isTest:{item.isTest},testName:{item.StepName}')
    # return True, ''
    rReturn = False
    compInfo = ''
    # gv.main_form.testSequences[item.suite_index].globalVar = item.globalVar
    if gv.cf.dut.test_mode == 'debug' or gv.IsDebug and item.Keyword in gv.cf.dut.debug_skip:
        lg.logger.debug('This is debug mode.Skip this step.')
        return True, ''

    try:

        if item.Keyword == 'Waiting':
            lg.logger.debug(f'waiting {item.TimeOut}s')
            time.sleep(item.TimeOut)
            rReturn = True

        elif item.Keyword == 'SetVar':
            item.testValue = item.command
            rReturn = True
            time.sleep(0.1)

        elif item.Keyword == 'KillProcess':
            rReturn = kill_process(item.ComdOrParam)

        elif item.Keyword == 'StartProcess':
            rReturn = start_process(item.ComdOrParam, item.ExpectStr)

        elif item.Keyword == 'RestartProcess':
            rReturn = restart_process(item.ComdOrParam, item.ExpectStr)

        elif item.Keyword == 'PingDUT':
            run_cmd('arp -d')
            rReturn = ping(item.ComdOrParam)

        elif item.Keyword == 'TelnetLogin':
            if not isinstance(gv.dut_comm, TelnetComm):
                gv.dut_comm = TelnetComm(gv.dut_ip, gv.cf.dut.prompt)
            rReturn = gv.dut_comm.open(gv.cf.dut.prompt)

        elif item.Keyword == 'TelnetAndSendCmd':
            temp = TelnetComm(item.param1, gv.cf.dut.prompt)
            if temp.open(gv.cf.dut.prompt) and \
                    temp.SendCommand(item.command, item.ExpectStr, item.TimeOut)[0]:
                return True

        elif item.Keyword == 'SerialPortOpen':
            if not isinstance(gv.dut_comm, SerialPort):
                if not IsNullOrEmpty(item.command):
                    gv.dut_comm = SerialPort(item.command, int(item.ExpectStr))
            rReturn = gv.dut_comm.open()

        elif item.Keyword == 'CloseDUTCOMM':
            if gv.dut_comm is not None:
                gv.dut_comm.close()
                rReturn = True

        elif item.Keyword == 'PLINInitConnect':
            gv.PLin = Bootloader()
            if gv.PLin.connect():
                time.sleep(0.5)
                rReturn = gv.PLin.runSchedule()
                time.sleep(0.5)

        elif item.Keyword == 'PLINDisConnect':
            rReturn = gv.PLin.DoLinDisconnect()

        elif item.Keyword == 'PLINSingleFrame':
            rReturn, revStr = gv.PLin.SingleFrame(item.ID, item._NAD, item.PCI_LEN, item.command, item.Timeout)
            if rReturn and re.search(item.CheckStr1, revStr):
                if not IsNullOrEmpty(item.SubStr1) or not IsNullOrEmpty(item.SubStr2):
                    item.testValue = subStr(item.SubStr1, item.SubStr2, revStr)

        elif item.Keyword == 'PLINMultiFrame':
            rReturn, revStr = gv.PLin.MultiFrame(item.ID, item._NAD, item.PCI_LEN, item.command, item.Timeout)
            if rReturn and re.search(item.CheckStr1, revStr):
                if not IsNullOrEmpty(item.SubStr1) or not IsNullOrEmpty(item.SubStr2):
                    item.testValue = subStr(item.SubStr1, item.SubStr2, revStr)

        elif item.Keyword == 'TransferData':
            s19datas = gv.PLin.get_data(f"{gv.current_dir}\\flash\\{item.command}")
            lg.logger.Debug(s19datas)
            rReturn = gv.PLin.TransferData(item.ID, item._NAD, s19datas, item.TimeOut, item._PCI_LEN)

        elif item.Keyword == 'CalcKey':
            item.testValue = gv.PLin.CalKey(item.command)
            lg.logger.Debug(f"send key is {item.testValue}.")
            rReturn = True

        elif item.Keyword == 'GetCRC':
            item.testValue = Bootloader.get_crc_apps19(f"{gv.current_dir}\\flash\\{gv.cf.station.station_name}")
            rReturn = not IsNullOrEmpty(item.testValue)

        else:
            rReturn, revStr = gv.dut_comm.SendCommand(item.ComdOrParam, item.ExpectStr, item.TimeOut)
            if rReturn and re.search(item.CheckStr1, revStr) and re.search(item.CheckStr2, revStr):
                if not IsNullOrEmpty(item.SubStr1) or not IsNullOrEmpty(item.SubStr2):
                    item.testValue = subStr(item.SubStr1, item.SubStr2, revStr)
                    # assert
                    if not IsNullOrEmpty(item.Spec) and IsNullOrEmpty(item.USL) and IsNullOrEmpty(item.LSL):
                        rReturn = True if item.testValue in item.Spec else False
                    if not IsNullOrEmpty(item.USL) or not IsNullOrEmpty(item.LSL):
                        rReturn, compInfo = CompareLimit(item.LSL, item.USL, item.testValue)
                    else:
                        lg.logger.Warn(f"assert is unknown,Spec:{item.Spec},LSL:{item.LSL}USL:{item.USL}.")
                else:
                    return True
            else:
                rReturn = False
    except Exception as e:
        lg.logger.exception(f'{currentframe().f_code.co_name}:{e}')
        rReturn = False
        return rReturn, compInfo
    else:
        lg.logger.debug("else pass..............")
        return rReturn, compInfo
    finally:
        pass
        # if item.Keyword == "SetIpaddrEnv" and rReturn:
        #     SetIpFlag = True
        lg.logger.debug("finally1 ..............")
        if (item.StepName.startswith("GetDAQResistor") or
                item.StepName.startswith("GetDAQTemp") or
                item.Keyword == "NiDAQmxVolt" or
                item.Keyword == "NiDAQmxCur"):
            gv.ArrayListDaq.append("N/A" if IsNullOrEmpty(item.testValue) else item.testValue)
            lg.logger.Debug(f"DQA add {item.testValue}")
        lg.logger.debug("finally2 ..............")


if __name__ == "__main__":
    pass
