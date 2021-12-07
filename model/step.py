#!/usr/cf/env python
# coding: utf-8
"""
@File   : test step.py
@Author : Steven.Shen
@Date   : 2021/9/2
@Desc   : 
"""
import re
from datetime import datetime
from PyQt5.QtCore import Qt
import model.product
import conf.globalvar as gv
import model.test
import conf.logconf as lg
import ui.mainform


def _parse_var(value):
    for a in re.findall(r'<(.*?)>', value):
        varVal = gv.get_globalVal(a)
        if varVal is None:
            raise Exception(f'Variable:{a} not found in globalVal!!')
        else:
            value = re.compile(f'<{a}>').sub(varVal, value, count=1)
    return value


class Step:
    suite_index = 0
    index = 0  # 当前测试step序列号
    tResult = False  # 测试项测试结果
    # isTest = True  # 是否测试,不测试的跳过
    start_time = None  # 测试项的开始时
    finish_time = None
    start_time_json = None
    __error_code = None
    __error_details = None
    testValue = None  # 测试得到的值
    __elapsedTime = None  # 测试步骤耗时
    globalVar: str = ''

    suite_name: str = ''
    ItemName: str = None  # 当前测试step名字
    ErrorCode: str = None  # 测试错误码
    RetryTimes: str = None  # 测试失败retry次数
    TimeOut: int = None  # 测试步骤超时时间
    SubStr1: str = None  # 截取字符串 如截取abc中的b SubStr1=a，SubStr2=cf
    SubStr2: str = None
    IfElse: str = None  # 测试步骤结果是否做为if条件，决定else步骤是否执行
    For: str = None  # 循环测试for(6)开始6次循环，END FOR结束
    Mode: str = None  # 机种，根据机种决定哪些用例不跑，哪些用例需要跑
    ComdOrParam: str = None  # 发送的测试命令
    ExpectStr: str = None  # 期待的提示符，用来判断反馈是不是结束了
    CheckStr1: str = None  # 检查反馈是否包含CheckStr1
    CheckStr2: str = None  # 检查反馈是否包含CheckStr2
    Limit_max: str = None  # 最小限值
    Limit_min: str = None  # 最大限值
    ErrorDetails: str = None  # 测试错误码详细描述
    Unit: str = None  # 测试值单位
    MES_var: str = None  # 上传MES信息的变量名字
    ByPassFail: str = None  # 手动人为控制测试结果 1=pass，0||空=fail
    FTC: str = None  # 失败继续 fail to continue。1=继续，0||空=不继续
    TestKeyword: str = None  # 测试步骤对应的关键字，执行对应关键字下的代码段
    Spec: str = None  # 测试定义的Spec
    Json: str = None  # 测试结果是否生成Json数据上传给客户
    EeroName: str = None  # 客户定义的测试步骤名字
    param1: str = None

    def __init__(self, dict_=None):
        self.__test_command = ''
        self.__test_spec = ''
        self.__retry_times = 0
        self.__isTest = True
        if dict_ is not None:
            self.__dict__.update(dict_)

    @property
    def isTest(self):
        if str(self.IfElse).lower() == 'else':
            self.__isTest = not gv.IfCond
        if not model.IsNullOrEmpty(self.Mode) and gv.dut_mode.lower() not in self.Mode.lower():
            self.__isTest = False
        return self.__isTest

    @isTest.setter
    def isTest(self, value):
        self.__isTest = value

    @property
    def _retry_times(self):
        if model.IsNullOrEmpty(self.RetryTimes):
            self.__retry_times = 0
        else:
            self.__retry_times = int(self.RetryTimes)
        return self.__retry_times

    @property
    def _test_command(self):
        return self.__test_command

    @_test_command.setter
    def _test_command(self, value):
        self.__test_command = _parse_var(value)

    @property
    def _test_spec(self):
        return self.__test_spec

    @_test_spec.setter
    def _test_spec(self, value):
        self.__test_spec = _parse_var(value)

    def run(self, testSuite, suiteItem: model.product.SuiteItem = None):
        self.suite_name = testSuite.SeqName
        self.suite_index = testSuite.index
        info = ''
        test_result = False
        self.start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        try:
            if self.isTest:
                ui.mainform.my_signals.update_treeWidgetItem_backColor.emit(Qt.yellow, self.suite_index, self.index,
                                                                            False)
                lg.logger.debug(f"<a name='testStep:{self.suite_name}-{self.ItemName}'>Start {self.ItemName},"
                                f"Keyword:{self.TestKeyword},Retry:{self.RetryTimes},Timeout:{self.TimeOut}s,"
                                f"SubStr:{self.SubStr1}*{self.SubStr2},MesVer:{self.MES_var},FTC:{self.FTC}</a>")
                self._test_command = self.ComdOrParam
                self._test_spec = self.Spec
            else:
                if not gv.IsCycle:
                    ui.mainform.my_signals.update_treeWidgetItem_backColor.emit(Qt.gray, self.suite_index, self.index,
                                                                                False)
                self.tResult = True
                return self.tResult

            for retry in range(self._retry_times, -1, -1):
                test_result, info = model.test.test(self, testSuite)
                if test_result:
                    break
            ui.mainform.my_signals.update_treeWidgetItem_backColor.emit(Qt.green if test_result else Qt.red,
                                                                        self.suite_index, self.index, False)
            self._print_result(test_result)
            self.tResult = self._process_if_bypass(test_result)
            self._set_errorCode_details(self.tResult, info)
            self._record_first_fail(self.tResult)
            self._process_json(suiteItem, test_result)
            self._process_mesVer()
        except Exception as e:
            lg.logger.exception(f"run Exception！！{e}")
            ui.mainform.my_signals.update_treeWidgetItem_backColor.emit(Qt.darkRed, self.suite_index, self.index, False)
            self.tResult = False
            return self.tResult
        else:
            return self.tResult
        finally:
            self._clear()

    def _set_errorCode_details(self, result=False, info=''):
        if not result:
            if not model.IsNullOrEmpty(self.__error_code) and not model.IsNullOrEmpty(self.__error_details):
                return
            if model.IsNullOrEmpty(self.ErrorCode):
                self.__error_code = self.EeroName
                self.__error_details = self.EeroName
            elif ':' in self.ErrorCode:
                error_list = self.ErrorCode.split()
                if len(error_list) > 1 and info == 'TooHigh':
                    self.__error_code = error_list[1].split(':')[0].strip()
                    self.__error_details = error_list[1].split(':')[1].strip()
                else:
                    self.__error_code = error_list[0].split(':')[0].strip()
                    self.__error_details = error_list[0].split(':')[1].strip()
            else:
                self.__error_code = self.ErrorCode
                self.__error_details = self.ErrorCode

    def _process_mesVer(self):
        if not model.IsNullOrEmpty(self.MES_var) and self.testValue is not None and str(
                self.testValue).lower() != 'true':
            setattr(gv.mesPhases, self.MES_var, self.testValue)

    def _if_statement(self, test_result: bool):
        if self.IfElse.lower() == 'if':
            gv.IfCond = test_result
            if not test_result:
                ui.mainform.my_signals.update_treeWidgetItem_backColor.emit('#FF99CC', self.suite_index, self.index,
                                                                            False)
                lg.logger.info(f"if statement fail needs to continue, setting the test result to true")
                test_result = True
        elif self.IfElse.lower() == 'else':
            pass
        else:
            gv.IfCond = True
        return test_result

    def _record_first_fail(self, tResult):
        if not tResult:
            gv.failCount += 1
        else:
            return
        if gv.failCount == 1 and model.IsNullOrEmpty(gv.error_code_first_fail):
            gv.error_code_first_fail = self.__error_code
            gv.error_details_first_fail = self.__error_details
            gv.mesPhases.first_fail = self.suite_name

    def _process_ByPassFail(self, step_result):
        if (self.ByPassFail.upper() == 'P' or self.ByPassFail.upper() == '1') and not step_result:
            ui.mainform.my_signals.update_treeWidgetItem_backColor.emit(Qt.darkGreen, self.suite_index, self.index,
                                                                        False)
            lg.logger.warning(f"Let this step:{self.ItemName} bypass.")
            return True
        elif (self.ByPassFail.upper() == 'F' or self.ByPassFail.upper() == '0') and step_result:
            ui.mainform.my_signals.update_treeWidgetItem_backColor.emit(Qt.darkRed, self.suite_index, self.index, False)
            lg.logger.warning(f"Let this step:{self.ItemName} by fail.")
            return False
        else:
            return step_result

    def _clear(self):
        self.tResult = False
        self.__error_code = None
        self.__error_details = None
        if not gv.IsDebug:
            self.isTest = True
        self.testValue = None
        self.__elapsedTime = None
        self.start_time = None
        self.finish_time = None
        self._test_command = ''
        self._test_spec = ''

    def _process_if_bypass(self, test_result: bool):
        result_if = self._if_statement(test_result)
        by_result = self._process_ByPassFail(result_if)
        return by_result

    def _print_result(self, tResult):
        self.__elapsedTime = (
                datetime.now() - datetime.strptime(self.start_time, '%Y-%m-%d %H:%M:%S.%f')).microseconds
        if self.TestKeyword == 'Wait' and self.TestKeyword == 'ThreadSleep':
            return
        if tResult:
            lg.logger.info(
                f"{self.ItemName} {'pass' if tResult else 'fail'}!! ElapsedTime:{self.__elapsedTime}us,"
                f"Symptom:{self.__error_code}:{self.__error_details},"
                f"Spec:{self.Spec},Min:{self.Limit_min},Value:{self.testValue},Max:{self.Limit_max}")
        else:
            lg.logger.error(
                f"{self.ItemName} {'pass' if tResult else 'fail'}!! ElapsedTime:{self.__elapsedTime}us,"
                f"Symptom:{self.__error_code}:{self.__error_details},"
                f"Spec:{self.Spec},Min:{self.Limit_min},Value:{self.testValue},Max:{self.Limit_max}")
        ui.mainform.my_signals.update_tableWidget.emit(
            [gv.SN, self.ItemName, self._test_spec, self.Limit_min, self.testValue,
             self.Limit_max, self.__elapsedTime, self.start_time, 'Pass' if tResult else 'Fail'])

    def _collect_result(self):
        if not model.IsNullOrEmpty(self.Limit_max) or not model.IsNullOrEmpty(self.Limit_min):
            gv.csv_list_header.extend([self.EeroName, f"{self.EeroName}_LIMIT_MIN", f"{self.EeroName}_LIMIT_MAX"])
            gv.csv_list_result.extend([self.testValue, self.Limit_min, self.Limit_max])
        elif not model.IsNullOrEmpty(self.Spec):
            gv.csv_list_header.extend([self.EeroName, f"{self.EeroName}_SPEC"])
            gv.csv_list_result.extend([self.testValue, self.Spec])
        else:
            gv.csv_list_header.append(self.EeroName)
            gv.csv_list_result.append(self.tResult)

    def _copy_to(self, obj: model.product.StepItem):
        if self.EeroName.endswith('_'):
            obj.test_name = self.EeroName + str(gv.ForTestCycle)
        else:
            obj.test_name = self.EeroName
        obj.status = 'passed' if self.tResult else 'failed'
        obj.test_value = self.testValue
        obj.units = self.Unit
        obj.error_code = self.__error_code
        obj.start_time = self.start_time_json
        self.finish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        obj.finish_time = self.finish_time
        obj.lower_limit = self.Limit_min
        obj.upper_limit = self.Limit_max
        if not model.IsNullOrEmpty(self.Spec) and '<' not in self.Spec \
                and '>' not in self.Spec and model.IsNullOrEmpty(self.Limit_min):
            obj.lower_limit = self.Spec
        if gv.stationObj.tests is not None:
            gv.stationObj.tests.append(obj)
        self._collect_result()

    def _process_json(self, suiteItem: model.product.SuiteItem, test_result):

        if self.Json is not None and self.Json.lower() == 'y':
            if self.IfElse.lower() == 'if' and not test_result:
                return
            else:
                self._JsonAndCsv(suiteItem, test_result)
        elif not test_result or self.ByPassFail.lower() == 'f' or self.ByPassFail.lower() == '0':
            self._JsonAndCsv(suiteItem, test_result)

    def _JsonAndCsv(self, suiteItem: model.product.SuiteItem, test_result):
        obj = model.product.StepItem()
        if self.ByPassFail.lower() == 'f' or self.ByPassFail.lower() == '0':
            self.tResult = False
        elif self.ByPassFail.lower() == 'p' or self.ByPassFail.lower() == '1':
            self.tResult = True
        else:
            self.tResult = test_result

        if self.testValue is None:
            self.testValue = str(test_result)

        self._copy_to(obj)
        if suiteItem is not None:
            suiteItem.phase_items.append(obj)


if __name__ == "__main__":
    pass
