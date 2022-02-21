#!/usr/bin/env python
# coding: utf-8
"""
@File   : globalvar.py
@Author : Steven.Shen
@Date   : 2021/9/8
@Desc   : 全局变量
"""
import os
import sys
from datetime import datetime
from os.path import dirname, abspath, join
from threading import Thread, Event
import conf
import model.product
import set
import platform

win = platform.system() == 'Windows'
linux = platform.system() == 'Linux'
current_path = set.current_path
config_yaml_path = join(current_path, 'conf', 'config.yaml')
logging_yaml = join(current_path, 'conf', 'logging.yaml')
cf = conf.read_config(config_yaml_path, conf.config.Configs)  # load test global variable
tableWidgetHeader = ["SN", "ItemName", "Spec", "LSL", "Value", "USL", "ElapsedTime", "StartTime", "Result"]
SN = ''
dut_ip = ''
DUTMesIP = ''
MesMac = 'FF:FF:FF:FF:FF'
WorkOrder = '1'
dut_model = 'unknown'
error_code_first_fail = ''
error_details_first_fail = ''
test_software_ver = cf.station.test_software_version

logFolderPath = ''
critical_log = ''
errors_log = ''
txtLogPath = ''
jsonOfResult = ''
csv_list_header = []
csv_list_result = []

dut_comm = None
FixSerialPort: None

IsDebug = False
startFlag = False
pauseFlag = False
IsCycle = False
finalTestResult = False
setIpFlag = False
SingleStepTest = False
IfCond = True
failCount = 0

ForTotalCycle = 0
ForTestCycle = 1
ForStartSuiteNo = 0
ForStartStepNo = 0
ForFlag = False

OutPutPath = rf'{current_path}\OutPut'
DataPath = rf'{current_path}\Data'
scriptFolder = rf'{current_path}\scripts'
excel_file_path = rf'{scriptFolder}\{cf.station.testcase}'
test_script_json = rf'{scriptFolder}\{cf.station.station_name}.json'
CSVFilePath = ''
mes_shop_floor = ''
mes_result = ''
shop_floor_url = ''
database_setting = rf'{current_path}\conf\setting.db'
database_result = rf'{current_path}\OutPut\result.db'
continue_fail_count = 0
total_pass_count = 0
total_fail_count = 0
total_abort_count = 0

mesPhases: model.product.MesInfo
stationObj: model.product.JsonResult
testThread: Thread
event = Event()

PassNumOfCycleTest = 0
FailNumOfCycleTest = 0
SuiteNo = -1
StepNo = -1
startTimeJsonFlag = True
startTimeJson = datetime.now()


def set_globalVal(name, value):
    globals()[name] = value


def get_globalVal(name, defValue=None):
    try:
        return globals()[name]
    except KeyError:
        return defValue


if __name__ == '__main__':
    pass
