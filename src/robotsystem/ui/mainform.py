import copy
import logging
import os
import sys
import stat
import time
from datetime import datetime
from enum import Enum
from os.path import dirname, abspath, join
from threading import Thread
import robotsystem.ui.images
from PyQt5 import QtCore
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRegExp, QMetaObject
from PyQt5.QtGui import QIcon, QCursor, QBrush, QRegExpValidator
from PyQt5.QtWidgets import QMessageBox, QStyleFactory, QTreeWidgetItem, QMenu, QApplication, QAbstractItemView, \
    QHeaderView, QTableWidgetItem, QLabel, QWidget, QAction, QInputDialog, QLineEdit
import robotsystem.conf.globalvar as gv
import robotsystem.conf.logprint as lg
import robotsystem.model.product
import robotsystem.model.testcase
import robotsystem.model.loadseq
import robotsystem.model.sqlite
import robotsystem.model.testglobalvar
from robotsystem.model.basicfunc import IsNullOrEmpty
import robotsystem.sockets.serialport
from robotsystem.ui.reporting import upload_Json_to_client, upload_result_to_mes, CollectResultToCsv, saveTestResult
from inspect import currentframe


# pyrcc5 images.qrc -o images.py
# pyuic5 main.ui -o main_ui.py


class TestStatus(Enum):
    """测试状态枚举类"""
    PASS = 1
    FAIL = 2
    START = 3
    ABORT = 4


class MySignals(QObject):
    """自定义信号类"""
    loadseq = pyqtSignal(str)
    update_tableWidget = pyqtSignal((list,), (str,))
    updateLabel = pyqtSignal([QLabel, str, int, QBrush], [QLabel, str, int], [QLabel, str])
    timingSignal = pyqtSignal(bool)
    textEditClearSignal = pyqtSignal(str)
    lineEditEnableSignal = pyqtSignal(bool)
    setIconSignal = pyqtSignal(QAction, QIcon)
    updateStatusBarSignal = pyqtSignal(str)
    updateActionSignal = pyqtSignal([QAction, QIcon, str], [QAction, QIcon])
    saveTextEditSignal = pyqtSignal(str)
    # showMessageBox = pyqtSignal([str, str, int])


def init_create_dirs():
    if not IsNullOrEmpty(gv.cf.station.setTimeZone):
        os.system(f"tzutil /s \"{gv.cf.station.setTimeZone}\"")
    os.makedirs(gv.logFolderPath + r"\Json", exist_ok=True)
    os.makedirs(gv.OutPutPath, exist_ok=True)
    os.makedirs(gv.DataPath, exist_ok=True)
    os.makedirs(gv.cf.station.log_folder + r"\CsvData\Upload", exist_ok=True)


def update_label(label: QLabel, str_: str, font_size: int = 36, color: QBrush = None):
    def thread_update():
        label.setText(str_)
        if color is not None:
            label.setStyleSheet(f"background-color:{color.color().name()};font: {font_size}pt '宋体';")

    thread = Thread(target=thread_update)
    thread.start()


def updateAction(action_, icon: QIcon = None, text: str = None):
    def thread_update():
        if icon is not None:
            action_.setIcon(icon)
        if text is not None:
            action_.setText(text)

    thread = Thread(target=thread_update)
    thread.start()


def UpdateContinueFail(testResult: bool):
    if gv.IsDebug or gv.cf.dut.test_mode.lower() == 'debug':
        return
    if testResult:
        gv.continue_fail_count = 0
    else:
        gv.continue_fail_count += 1


def on_setIcon(action_, icon: QIcon):
    def thread_update():
        action_.setIcon(icon)

    thread = Thread(target=thread_update)
    thread.start()


def on_actionConfig():
    def actionOpenScript():
        os.startfile(rf'{gv.config_yaml_path}')

    thread = Thread(target=actionOpenScript)
    thread.start()


def on_actionLogFolder():
    def thread_update():
        if os.path.exists(gv.logFolderPath):
            os.startfile(gv.logFolderPath)

    thread = Thread(target=thread_update)
    thread.start()


def on_actionOpenLog():
    def thread_update():
        if os.path.exists(gv.txtLogPath):
            os.startfile(gv.txtLogPath)
        else:
            lg.logger.warning(f"no find test log")

    thread = Thread(target=thread_update)
    thread.start()


def on_actionCSVLog():
    def thread_update():
        if os.path.exists(gv.CSVFilePath):
            os.startfile(gv.CSVFilePath)
        else:
            lg.logger.warning(f"no find test log")

    thread = Thread(target=thread_update)
    thread.start()


def on_actionException():
    def thread_update():
        if os.path.exists(gv.critical_log):
            os.startfile(gv.critical_log)

    thread = Thread(target=thread_update)
    thread.start()


class MainForm(QWidget):
    my_signals = MySignals()
    main_form = None  # 单例模式

    def __init__(self):
        super().__init__()
        self.timer = None
        self.ui = loadUi(join(dirname(abspath(__file__)), 'main.ui'))
        self.ui.setWindowTitle(self.ui.windowTitle() + f' v{gv.version}')
        init_create_dirs()
        MainForm.main_form = self  # 单例模式
        self.sec = 1
        self.testcase: robotsystem.model.testcase.TestCase = robotsystem.model.testcase.TestCase(
            rf'{gv.excel_file_path}',
            f'{gv.cf.station.station_name}')
        self.testSequences = self.testcase.clone_suites
        self.init_textEditHandler()
        self.init_lab_factory(gv.cf.station.privileges)
        self.init_tableWidget()
        self.init_childLabel()
        self.init_label_info()
        self.init_status_bar()
        self.init_lineEdit()
        self.init_signals_connect()
        self.ShowTreeView(self.testSequences)
        gv.testThread = Thread(target=self.test_thread, daemon=True)
        gv.testThread.start()

    def init_textEditHandler(self):
        """create log handler for textEdit"""
        textEdit_handler = lg.QTextEditHandler(stream=self.ui.textEdit)
        textEdit_handler.formatter = lg.logger.handlers[0].formatter
        textEdit_handler.level = 10
        textEdit_handler.name = 'textEdit_handler'
        logging.getLogger('testlog').addHandler(textEdit_handler)

    def init_lineEdit(self):
        self.ui.lineEdit.setFocus()
        self.ui.lineEdit.setMaxLength(gv.cf.dut.sn_len)
        reg = QRegExp('^[A-Z0-9]{16,16}')  # 自定义文本验证器
        pValidator = QRegExpValidator(self.ui.lineEdit)
        pValidator.setRegExp(reg)
        if not gv.IsDebug:
            self.ui.lineEdit.setValidator(pValidator)

    def init_childLabel(self):
        self.ui.lb_failInfo = QLabel('Next:O-SFT /Current:O', self.ui.lb_status)
        self.ui.lb_failInfo.setStyleSheet(
            f"background-color:#f0f0f0;font: 11pt '宋体';")
        self.ui.lb_failInfo.setHidden(True)
        self.ui.lb_testTime = QLabel('TestTime:30s', self.ui.lb_errorCode)
        self.ui.lb_testTime.setStyleSheet(
            f"background-color:#f0f0f0;font: 11pt '宋体';")
        self.ui.lb_testTime.setHidden(True)

    def init_tableWidget(self):
        self.ui.tableWidget_2.setHorizontalHeaderLabels(['property', 'value'])
        self.ui.tableWidget.setHorizontalHeaderLabels(gv.tableWidgetHeader)
        self.ui.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.tableWidget.resizeColumnsToContents()
        self.ui.tableWidget.resizeRowsToContents()
        strHeaderQss = "QHeaderView::section { background:#CCCCCC; color:black;min-height:3em;}"
        self.ui.tableWidget.setStyleSheet(strHeaderQss)
        self.ui.tableWidget_2.setStyleSheet(strHeaderQss)

    def init_lab_factory(self, str_):
        if str_ == "lab":
            gv.IsDebug = True
            self.ui.actionPrivileges.setIcon(QIcon(':/images/lab-icon.png'))
        else:
            gv.IsDebug = False
            self.ui.actionPrivileges.setIcon(QIcon(':/images/factory.png'))
            self.ui.actionConvertExcelToJson.setEnabled(False)
            self.ui.actionSaveToScript.setEnabled(False)
            self.ui.actionReloadScript.setEnabled(False)
            self.ui.actionStart.setEnabled(False)
            self.ui.actionStop.setEnabled(False)
            self.ui.actionClearLog.setEnabled(False)

    def init_label_info(self):
        def GetAllIpv4Address(networkSegment):
            import psutil
            from socket import AddressFamily
            for name, info in psutil.net_if_addrs().items():
                for addr in info:
                    if AddressFamily.AF_INET == addr.family and str(addr.address).startswith(networkSegment):
                        return str(addr.address)

        self.ui.actionproduction.setText(gv.cf.dut.test_mode)
        self.ui.action192_168_1_101.setText(GetAllIpv4Address('10.90.'))

    def init_status_bar(self):
        with robotsystem.model.sqlite.Sqlite(gv.database_setting) as db:
            db.execute(f"SELECT VALUE  from COUNT WHERE NAME='continue_fail_count'")
            gv.continue_fail_count = db.cur.fetchone()[0]
            db.execute(f"SELECT VALUE  from COUNT WHERE NAME='total_pass_count'")
            gv.total_pass_count = db.cur.fetchone()[0]
            db.execute(f"SELECT VALUE  from COUNT WHERE NAME='total_fail_count'")
            gv.total_fail_count = db.cur.fetchone()[0]
            db.execute(f"SELECT VALUE  from COUNT WHERE NAME='total_abort_count'")
            gv.total_abort_count = db.cur.fetchone()[0]

        self.ui.lb_continuous_fail = QLabel(f'continuous_fail: {gv.continue_fail_count}')
        self.ui.lb_count_pass = QLabel(f'PASS: {gv.total_pass_count}')
        self.ui.lb_count_fail = QLabel(f'FAIL: {gv.total_fail_count}')
        self.ui.lb_count_abort = QLabel(f'ABORT: {gv.total_abort_count}')
        try:
            self.ui.lb_count_yield = QLabel('Yield: {:.2%}'.format(gv.total_pass_count / (
                    gv.total_pass_count + gv.total_fail_count + gv.total_abort_count)))
        except ZeroDivisionError:
            self.ui.lb_count_yield = QLabel('Yield: 0.00%')
        self.ui.statusbar.addPermanentWidget(self.ui.lb_continuous_fail, 3)
        self.ui.statusbar.addPermanentWidget(self.ui.lb_count_pass, 2)
        self.ui.statusbar.addPermanentWidget(self.ui.lb_count_fail, 2)
        self.ui.statusbar.addPermanentWidget(self.ui.lb_count_abort, 2)
        self.ui.statusbar.addPermanentWidget(self.ui.lb_count_yield, 16)

    def init_signals_connect(self):
        """connect signals to slots"""
        self.my_signals.timingSignal[bool].connect(self.timing)
        self.my_signals.updateLabel[QLabel, str, int, QBrush].connect(update_label)
        self.my_signals.updateLabel[QLabel, str, int].connect(update_label)
        self.my_signals.updateLabel[QLabel, str].connect(update_label)
        self.my_signals.update_tableWidget[list].connect(self.on_update_tableWidget)
        self.my_signals.update_tableWidget[str].connect(self.on_update_tableWidget)
        self.my_signals.textEditClearSignal[str].connect(self.on_textEditClear)
        self.my_signals.lineEditEnableSignal[bool].connect(self.lineEditEnable)
        self.my_signals.setIconSignal[QAction, QIcon].connect(on_setIcon)
        self.my_signals.updateActionSignal[QAction, QIcon].connect(updateAction)
        self.my_signals.updateActionSignal[QAction, QIcon, str].connect(updateAction)
        self.my_signals.updateStatusBarSignal[str].connect(self.updateStatusBar)
        self.my_signals.saveTextEditSignal[str].connect(self.on_actionSaveLog)
        # self.my_signals.showMessageBox[str, str, int].connect(self.showMessageBox)

        self.ui.actionCheckAll.triggered.connect(self.on_actionCheckAll)
        self.ui.actionUncheckAll.triggered.connect(self.on_actionUncheckAll)
        self.ui.actionStepping.triggered.connect(self.on_actionStepping)
        self.ui.actionLooping.triggered.connect(self.on_actionLooping)
        self.ui.actionEditStep.triggered.connect(self.on_actionEditStep)
        self.ui.actionExpandAll.triggered.connect(self.on_actionExpandAll)
        self.ui.actionCollapseAll.triggered.connect(self.on_actionCollapseAll)

        self.ui.actionOpen_TestCase.triggered.connect(self.on_actionOpen_TestCase)
        self.ui.actionConvertExcelToJson.triggered.connect(self.on_actionConvertExcelToJson)
        self.ui.actionOpenScript.triggered.connect(self.on_actionOpenScript)
        self.ui.actionSaveToScript.triggered.connect(self.on_actionSaveToScript)
        self.ui.actionReloadScript.triggered.connect(self.on_reloadSeqs)
        self.ui.actionConfig.triggered.connect(on_actionConfig)
        self.ui.actionPrivileges.triggered.connect(self.on_actionPrivileges)
        self.ui.actionStart.triggered.connect(self.on_actionStart)
        self.ui.actionStop.triggered.connect(self.on_actionStop)
        self.ui.actionOpenLog.triggered.connect(on_actionOpenLog)
        self.ui.actionClearLog.triggered.connect(self.on_actionClearLog)
        self.ui.actionLogFolder.triggered.connect(on_actionLogFolder)
        self.ui.actionSaveLog.triggered.connect(self.on_actionSaveLog)
        self.ui.actionCSVLog.triggered.connect(on_actionCSVLog)
        self.ui.actionException.triggered.connect(on_actionException)
        self.ui.actionEnable_lab.triggered.connect(self.on_actionEnable_lab)
        self.ui.actionDisable_factory.triggered.connect(self.on_actionDisable_factory)
        self.ui.actionAbout.triggered.connect(self.on_actionAbout)

        self.ui.lineEdit.textEdited.connect(self.on_textEdited)
        self.ui.lineEdit.returnPressed.connect(self.on_returnPressed)
        self.ui.treeWidget.customContextMenuRequested.connect(self.on_treeWidgetMenu)
        self.ui.treeWidget.itemChanged.connect(self.on_itemChanged)
        self.ui.treeWidget.itemPressed.connect(self.on_itemActivated)
        self.ui.tableWidget_2.itemChanged.connect(self.on_tableWidget2Edit)

    def init_treeWidget_color(self):
        self.ui.treeWidget.blockSignals(True)
        for i, item in enumerate(self.testSequences):
            self.ui.treeWidget.topLevelItem(i).setBackground(0, Qt.white)
            for j in range(len(self.testSequences[i].steps)):
                self.ui.treeWidget.topLevelItem(i).child(j).setBackground(0, Qt.white)
        self.ui.treeWidget.blockSignals(False)

    def on_itemActivated(self, item, column=0):
        if item.parent() is None:
            # lg.logger.critical('itemActivate')
            gv.SuiteNo = self.ui.treeWidget.indexOfTopLevelItem(item)
            gv.StepNo = 0
            self.ui.treeWidget.expandItem(item)
            self.ui.actionStepping.setEnabled(False)
            self.ui.actionEditStep.setEnabled(False)
            pp = item.data(column, Qt.DisplayRole).split(' ', 1)[1]
            anchor = f'testSuite:{pp}'
            self.ui.textEdit.scrollToAnchor(anchor)
        else:
            # lg.logger.critical('itemActivate')
            gv.SuiteNo = self.ui.treeWidget.indexOfTopLevelItem(item.parent())
            gv.StepNo = item.parent().indexOfChild(item)
            self.ui.actionStepping.setEnabled(True)
            self.ui.actionEditStep.setEnabled(True)
            pp = item.parent().data(column, Qt.DisplayRole).split(' ', 1)[1]
            cc = item.data(column, Qt.DisplayRole).split(' ', 1)[1]
            anchor = f'testStep:{pp}-{cc}'
            self.ui.textEdit.scrollToAnchor(anchor)

    def on_tableWidget_clear(self):
        for i in range(0, self.ui.tableWidget.rowCount()):
            self.ui.tableWidget.removeRow(0)

    def on_update_tableWidget(self, result_tuple):
        def thread_update_tableWidget():
            if isinstance(result_tuple, list):
                row_cnt = self.ui.tableWidget.rowCount()
                self.ui.tableWidget.insertRow(row_cnt)
                column_cnt = self.ui.tableWidget.columnCount()
                for column in range(column_cnt):
                    if IsNullOrEmpty(result_tuple[column]):
                        result_tuple[column] = '--'
                    item = QTableWidgetItem(str(result_tuple[column]))
                    if 'false' in str(result_tuple[-1]).lower() or 'fail' in str(result_tuple[-1]).lower():
                        item.setForeground(Qt.red)
                        # item.setFont(QFont('Times', 12, QFont.Black))
                    self.ui.tableWidget.setItem(row_cnt, column, item)
                    self.ui.tableWidget.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
                # self.ui.tableWidget.resizeColumnsToContents()
                self.ui.tableWidget.scrollToItem(self.ui.tableWidget.item(row_cnt - 1, 0),
                                                 hint=QAbstractItemView.EnsureVisible)
                # clear all rows if var is str
            elif isinstance(result_tuple, str):
                for i in range(0, self.ui.tableWidget.rowCount()):
                    self.ui.tableWidget.removeRow(0)
            QApplication.processEvents()

        thread = Thread(target=thread_update_tableWidget)
        thread.start()

    def on_reloadSeqs(self):
        def thread_convert_and_load_script():
            lg.logger.debug('start reload script...')
            if os.path.exists(gv.test_script_json):
                os.chmod(gv.test_script_json, stat.S_IWRITE)
                os.remove(gv.test_script_json)
            self.testcase = robotsystem.model.testcase.TestCase(gv.excel_file_path, gv.cf.station.station_name)
            self.testSequences = self.testcase.clone_suites

        thread = Thread(target=thread_convert_and_load_script)
        thread.start()
        thread.join()
        if self.testSequences is not None:
            self.ShowTreeView(self.testSequences, gv.IsDebug)
        lg.logger.debug('reload finish!')

    def on_itemChanged(self, item, column=0):
        if gv.startFlag:
            return
        if item.parent() is None:
            pNo = self.ui.treeWidget.indexOfTopLevelItem(item)
            isChecked = item.checkState(column) == Qt.Checked
            self.testcase.clone_suites[pNo].isTest = isChecked
            self.ui.treeWidget.blockSignals(True)
            for i in range(0, item.childCount()):
                item.child(i).setCheckState(column, Qt.Checked if isChecked else Qt.Unchecked)
                self.testcase.clone_suites[pNo].steps[i].isTest = isChecked
            self.ui.treeWidget.blockSignals(False)
        else:
            ParentIsTest = []
            pNo = self.ui.treeWidget.indexOfTopLevelItem(item.parent())
            cNO = item.parent().indexOfChild(item)
            self.testcase.clone_suites[pNo].steps[cNO].isTest = item.checkState(column) == Qt.Checked
            for i in range(item.parent().childCount()):
                isChecked = item.parent().child(i).checkState(column) == Qt.Checked
                ParentIsTest.append(isChecked)
            isChecked_parent = any(ParentIsTest)
            self.ui.treeWidget.blockSignals(True)
            self.testcase.clone_suites[pNo].isTest = isChecked_parent
            item.parent().setCheckState(column, Qt.Checked if isChecked_parent else Qt.Unchecked)
            self.ui.treeWidget.blockSignals(False)

    def on_treeWidgetMenu(self):
        if gv.IsDebug:
            menu = QMenu(self.ui.treeWidget)
            menu.addAction(self.ui.actionStepping)
            menu.addAction(self.ui.actionEditStep)
            menu.addAction(self.ui.actionLooping)
            menu.addAction(self.ui.actionCheckAll)
            menu.addAction(self.ui.actionUncheckAll)
            menu.addAction(self.ui.actionExpandAll)
            menu.addAction(self.ui.actionCollapseAll)
            menu.exec_(QCursor.pos())

    def on_actionCheckAll(self):
        self.ShowTreeView(self.testSequences, True)

    def on_actionUncheckAll(self):
        self.ShowTreeView(self.testSequences, False)

    def on_actionStepping(self):
        self.on_returnPressed('stepping')

    def on_actionLooping(self):
        gv.FailNumOfCycleTest = 0
        gv.PassNumOfCycleTest = 0
        gv.IsCycle = True
        self.on_returnPressed()

    def on_actionOpen_TestCase(self):
        def thread_actionOpen_TestCase():
            os.startfile(self.testcase.testcase_path)

        thread = Thread(target=thread_actionOpen_TestCase)
        thread.start()

    def on_actionConvertExcelToJson(self):
        thread = Thread(
            target=robotsystem.model.loadseq.excel_convert_to_json, args=(self.testcase.testcase_path,
                                                                          gv.cf.station.station_all))
        thread.start()

    def on_actionOpenScript(self):
        def actionOpenScript():
            os.startfile(self.testcase.test_script_json)

        thread = Thread(target=actionOpenScript)
        thread.start()

    def on_actionSaveToScript(self):
        thread = Thread(target=robotsystem.model.loadseq.serialize_to_json,
                        args=(self.testcase.clone_suites, gv.test_script_json))
        thread.start()

    def on_actionPrivileges(self):
        if gv.IsDebug:
            QMessageBox.information(self, 'Authority', 'This is lab test privileges.', QMessageBox.Yes)
        else:
            QMessageBox.information(self, 'Authority', 'This is factory test privileges.', QMessageBox.Yes)

    def on_actionStart(self):
        if gv.startFlag:
            if not gv.pauseFlag:
                gv.pauseFlag = True
                self.ui.actionStart.setIcon(QIcon(':/images/Start-icon.png'))
                gv.pause_event.clear()
            else:
                gv.pauseFlag = False
                self.ui.actionStart.setIcon(QIcon(':/images/Pause-icon.png'))
                gv.pause_event.set()
        else:
            self.on_returnPressed()

    def on_actionStop(self):
        if gv.startFlag:
            if gv.FailNumOfCycleTest == 0:
                gv.finalTestResult = True
                self.SetTestStatus(TestStatus.PASS)
            else:
                self.SetTestStatus(TestStatus.FAIL)
            gv.IsCycle = False

    def on_actionClearLog(self):
        if not gv.startFlag:
            self.ui.textEdit.clear()

    def on_actionSaveLog(self, info):
        def thread_update():
            gv.txtLogPath = rf'{gv.logFolderPath}\{str(gv.finalTestResult).upper()}_{gv.SN}_' \
                            rf'{gv.error_details_first_fail}_{time.strftime("%H-%M-%S")}.txt'
            content = self.ui.textEdit.toPlainText()
            with open(gv.txtLogPath, 'wb') as f:
                f.write(content.encode('utf8'))
            lg.logger.debug(f"Save test log OK.{gv.txtLogPath}")

        thread = Thread(target=thread_update)
        thread.start()

    def on_actionEnable_lab(self):
        gv.IsDebug = True
        self.ui.actionPrivileges.setIcon(QIcon(':/images/lab-icon.png'))
        self.debug_switch(gv.IsDebug)

    def on_actionDisable_factory(self):
        gv.IsDebug = False
        self.ui.actionPrivileges.setIcon(QIcon(':/images/factory.png'))
        self.debug_switch(gv.IsDebug)

    def on_actionAbout(self):
        QMessageBox.about(self, 'About', 'Python3.8+PyQt5\nTechnical support: StevenShen\nWeChat:chenhlzqbx')

    def debug_switch(self, isDebug: bool):
        self.ui.actionConvertExcelToJson.setEnabled(isDebug)
        self.ui.actionSaveToScript.setEnabled(isDebug)
        self.ui.actionReloadScript.setEnabled(isDebug)
        self.ui.actionStart.setEnabled(isDebug)
        self.ui.actionStop.setEnabled(isDebug)
        self.ui.actionClearLog.setEnabled(isDebug)
        self.ui.actionSaveLog.setEnabled(isDebug)
        self.ui.actionConfig.setEnabled(isDebug)

    def on_actionEditStep(self):
        self.ui.tableWidget_2.blockSignals(True)
        if self.ui.tabWidget.currentIndex() != 1:
            self.ui.tabWidget.setCurrentIndex(1)
        for i in range(0, self.ui.tableWidget_2.rowCount()):
            self.ui.tableWidget_2.removeRow(0)
        step_obj = self.testcase.clone_suites[gv.SuiteNo].steps[gv.StepNo]
        for prop_name in list(dir(step_obj)):
            prop_value = getattr(step_obj, prop_name)
            if isinstance(prop_value, str) and not prop_name.startswith('_'):
                column_cnt = self.ui.tableWidget_2.columnCount()
                row_cnt = self.ui.tableWidget_2.rowCount()
                self.ui.tableWidget_2.insertRow(row_cnt)
                key_pairs = [prop_name, prop_value]
                for column in range(column_cnt):
                    self.ui.tableWidget_2.horizontalHeader().setSectionResizeMode(column,
                                                                                  QHeaderView.ResizeToContents)
                    item = QTableWidgetItem(key_pairs[column])
                    if column == 0:
                        item.setFlags(Qt.ItemIsEnabled)
                        item.setBackground(Qt.lightGray)
                    self.ui.tableWidget_2.setItem(row_cnt, column, item)
        self.ui.tableWidget_2.sortItems(1, order=Qt.DescendingOrder)
        self.ui.tableWidget_2.blockSignals(False)

    def on_tableWidget2Edit(self, item):
        prop_name = self.ui.tableWidget_2.item(item.row(), item.column() - 1).text()
        prop_value = item.text()
        setattr(self.testcase.clone_suites[gv.SuiteNo].steps[gv.StepNo], prop_name, prop_value)

    def on_actionExpandAll(self):
        self.ui.treeWidget.expandAll()
        self.ui.treeWidget.scrollToItem(self.ui.treeWidget.topLevelItem(0), hint=QAbstractItemView.EnsureVisible)

    def on_actionCollapseAll(self):
        self.ui.treeWidget.collapseAll()

    def ShowTreeView(self, sequences=None, checkall=True):
        if sequences is None:
            return
        self.ui.treeWidget.blockSignals(True)
        self.ui.treeWidget.clear()
        self.ui.treeWidget.setHeaderLabel(f'{gv.cf.station.station_no}')
        for suite in sequences:
            suite_node = QTreeWidgetItem(self.ui.treeWidget)
            suite_node.setData(0, Qt.DisplayRole, f'{suite.index + 1}. {suite.SuiteName}')
            suite_node.setIcon(0, QIcon(':/images/folder-icon.png'))
            if checkall:
                suite_node.setCheckState(0, Qt.Checked)
                suite.isTest = True
            else:
                suite_node.setCheckState(0, Qt.Unchecked)
                suite.isTest = False
            if gv.IsDebug:
                suite_node.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            else:
                suite_node.setFlags(Qt.ItemIsSelectable)
            for step in suite.steps:
                step_node = QTreeWidgetItem(suite_node)
                step_node.setData(0, Qt.DisplayRole, f'{step.index + 1}) {step.StepName}')
                if checkall:
                    step_node.setCheckState(0, Qt.Checked)
                    step.isTest = True
                else:
                    step_node.setCheckState(0, Qt.Unchecked)
                    step.isTest = False
                if gv.IsDebug:
                    step_node.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                else:
                    step_node.setFlags(Qt.ItemIsSelectable)
                step_node.setIcon(0, QIcon(':/images/Document-txt-icon.png'))
                suite_node.addChild(step_node)
        self.ui.treeWidget.setStyle(QStyleFactory.create('windows'))
        self.ui.treeWidget.resizeColumnToContents(0)
        self.ui.treeWidget.topLevelItem(0).setExpanded(True)
        self.ui.treeWidget.blockSignals(False)

    @QtCore.pyqtSlot(QBrush, int, int, bool)
    def update_treeWidget_color(self, color: QBrush, suiteNO_: int, stepNo_: int = -1, allChild=False):
        if stepNo_ == -1:
            if gv.IsCycle or not gv.startFlag:
                return
            self.ui.treeWidget.topLevelItem(suiteNO_).setExpanded(True)
            self.ui.treeWidget.topLevelItem(suiteNO_).setBackground(0, color)
            if allChild:
                for i in range(self.ui.treeWidget.topLevelItem(suiteNO_).childCount()):
                    self.ui.treeWidget.topLevelItem(suiteNO_).child(i).setBackground(0, color)
        else:
            self.ui.treeWidget.topLevelItem(suiteNO_).child(stepNo_).setBackground(0, color)
            self.ui.treeWidget.scrollToItem(self.ui.treeWidget.topLevelItem(suiteNO_).child(stepNo_),
                                            hint=QAbstractItemView.EnsureVisible)
        QApplication.processEvents()

    @QtCore.pyqtSlot(str, str, int, result=QMessageBox.StandardButton)
    def showMessageBox(self, title, text, level):
        if level == 0:
            return QMessageBox.information(self, title, text, QMessageBox.Yes)
        elif level == 1:
            return QMessageBox.warning(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        elif level == 2:
            aa = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            lg.logger.debug(aa)
            return aa
        elif level == 3:
            return QMessageBox.about(self, title, text)
        else:
            return QMessageBox.critical(self, title, text, QMessageBox.Yes)

    def lineEditEnable(self, isEnable):
        def thread_update():
            self.ui.lineEdit.setEnabled(isEnable)
            if isEnable:
                self.ui.lineEdit.setText('')
                self.ui.lineEdit.setFocus()

        thread = Thread(target=thread_update)
        thread.start()

    def on_textEditClear(self, info):
        lg.logger.debug(f'{currentframe().f_code.co_name}:{info}')
        self.ui.textEdit.clear()

    def updateStatusBar(self, info):
        def update_status_bar():
            lg.logger.debug(f'{currentframe().f_code.co_name}:{info}')
            with robotsystem.model.sqlite.Sqlite(gv.database_setting) as db:
                db.execute(f"UPDATE COUNT SET VALUE='{gv.continue_fail_count}' where NAME ='continue_fail_count'")
                db.execute(f"UPDATE COUNT SET VALUE='{gv.total_pass_count}' where NAME ='total_pass_count'")
                db.execute(f"UPDATE COUNT SET VALUE='{gv.total_fail_count}' where NAME ='total_fail_count'")
                db.execute(f"UPDATE COUNT SET VALUE='{gv.total_abort_count}' where NAME ='total_abort_count'")
            self.ui.lb_continuous_fail.setText(f'continuous_fail: {gv.continue_fail_count}')
            self.ui.lb_count_pass.setText(f'PASS: {gv.total_pass_count}')
            self.ui.lb_count_fail.setText(f'FAIL: {gv.total_fail_count}')
            self.ui.lb_count_abort.setText(f'ABORT: {gv.total_abort_count}')
            try:
                self.ui.lb_count_yield.setText('Yield: {:.2%}'.format(gv.total_pass_count / (
                        gv.total_pass_count + gv.total_fail_count + gv.total_abort_count)))
            except ZeroDivisionError:
                self.ui.lb_count_yield.setText('Yield: 0.00%')
            QApplication.processEvents()

        thread = Thread(target=update_status_bar)
        thread.start()

    def timerEvent(self, a):
        self.my_signals.updateLabel[QLabel, str, int].emit(self.ui.lb_errorCode, str(self.sec), 20)
        QApplication.processEvents()
        self.sec += 1

    def timing(self, flag):
        if flag:
            lg.logger.debug('start timing...')
            self.timer = self.startTimer(1000)
        else:
            lg.logger.debug('stop timing...')
            self.killTimer(self.timer)

    def get_stationNo(self):
        """通过串口读取治具中设置的测试工站名字"""
        if not gv.cf.station.fix_flag:
            return
        gv.FixSerialPort = robotsystem.sockets.serialport.SerialPort(gv.cf.station.fix_com_port,
                                                                     gv.cf.station.fix_com_baudRate)
        for i in range(0, 3):
            rReturn, revStr = gv.FixSerialPort.SendCommand('AT+READ_FIXNUM%', '\r\n', 1, False)
            if rReturn:
                gv.cf.station.station_no = revStr.replace('\r\n', '').strip()
                gv.cf.station.station_name = gv.cf.station.station_no[0, gv.cf.station.station_no.index('-')]
                lg.logger.debug(f"Read fix number success,stationName:{gv.cf.station.station_name}")
                break
        else:
            QMessageBox.Critical(self, 'Read StationNO', "Read FixNum error,Please check it!")
            sys.exit(0)

    def ContinuousFailReset_Click(self):
        """连续fail超过规定值需要TE确认问题并输入密码后才能继续测试"""
        text, ok = QInputDialog.getText(self, 'Reset', 'Please input Reset Password:', echo=QLineEdit.Password)
        if ok:
            if text == 'test123':
                gv.continue_fail_count = 0
                self.ui.lb_continuous_fail.setText(f'continuous_fail: {gv.continue_fail_count}')
                self.ui.lb_continuous_fail.setStyleSheet(
                    f"background-color:{self.ui.statusbar.palette().window().color().name()};")
                return True
            else:
                QMessageBox.critical(self, 'ERROR!', 'wrong password!')
                return False
        else:
            return False

    def CheckContinueFailNum(self):
        with robotsystem.model.sqlite.Sqlite(gv.database_setting) as db:
            db.execute(f"SELECT VALUE  from COUNT WHERE NAME='continue_fail_count'")
            gv.continue_fail_count = db.cur.fetchone()[0]
            lg.logger.debug(str(gv.continue_fail_count))
        if gv.continue_fail_count >= gv.cf.station.continue_fail_limit:
            self.ui.lb_continuous_fail.setStyleSheet(f"background-color:red;")
            if gv.IsDebug:
                return True
            else:
                return self.ContinuousFailReset_Click()
        else:
            self.ui.lb_continuous_fail.setStyleSheet(
                f"background-color:{self.ui.statusbar.palette().window().color().name()};")
            return True

    def on_textEdited(self):
        sn = self.ui.lineEdit.text()

        def JudgeProdMode():
            """通过SN判断机种"""
            if IsNullOrEmpty(sn):
                gv.dut_model = 'unknown'
                return gv.dut_model
            if sn[0] == 'J' or sn[0] == '6':
                gv.dut_mode = gv.cf.dut.dut_models[0]
            elif sn[0] == 'N' or sn[0] == '7':
                gv.dut_mode = gv.cf.dut.dut_models[1]
            elif sn[0] == 'Q' or sn[0] == '8':
                gv.dut_mode = gv.cf.dut.dut_models[2]
            elif sn[0] == 'S' or sn[0] == 'G':
                gv.dut_mode = gv.cf.dut.dut_models[3]
            else:
                gv.dut_model = 'unknown'
            self.ui.actionunknow.setText(gv.dut_model)
            return gv.dut_model

        if JudgeProdMode() != 'unknown' and not gv.IsDebug:
            reg = QRegExp(gv.cf.dut.dut_regex[gv.dut_model])
            pValidator = QRegExpValidator(reg, self)
            self.ui.lineEdit.setValidator(pValidator)

    def on_returnPressed(self, stepping_flag=None):
        if stepping_flag is not None:
            gv.SingleStepTest = True
        else:
            gv.SingleStepTest = False
        if gv.dut_model == 'unknown' and not gv.IsDebug:
            str_info = f'无法根据SN判断机种或者SN长度不对! 扫描:{len(self.ui.lineEdit.text())},规定:{gv.cf.dut.sn_len}.'
            QMetaObject.invokeMethod(self, 'showMessageBox', Qt.AutoConnection,
                                     QtCore.Q_RETURN_ARG(QMessageBox.StandardButton),
                                     QtCore.Q_ARG(str, 'JudgeMode!'),
                                     QtCore.Q_ARG(str, str_info),
                                     QtCore.Q_ARG(int, 5))
            return
        if not self.CheckContinueFailNum() and not gv.IsDebug:
            return

        if gv.IsDebug:
            if not gv.SingleStepTest:
                self.init_treeWidget_color()
        else:
            self.testSequences = copy.deepcopy(self.testcase.original_suites)
            self.testcase.clone_suites = self.testSequences
            self.ShowTreeView(self.testSequences)
        gv.SN = self.ui.lineEdit.text()
        self.variable_init()

    def variable_init(self):
        """测试变量初始化"""
        if not gv.testThread.is_alive():
            gv.testThread = Thread(target=self.test_thread, daemon=True)
            gv.testThread.start()

        if gv.SingleStepTest and self.testcase.Finished:
            pass
        else:
            gv.testGlobalVar = robotsystem.model.testglobalvar.TestGlobalVar(gv.cf.station.station_name,
                                                                             gv.cf.station.station_no, gv.SN,
                                                                             gv.cf.dut.dut_ip, gv.cf.station.log_folder)
        gv.stationObj = robotsystem.model.product.JsonObject(gv.SN, gv.cf.station.station_no,
                                                             gv.cf.dut.test_mode,
                                                             gv.cf.dut.qsdk_ver, gv.version)
        gv.mes_result = f'http://{gv.cf.station.mes_result}/api/2/serial/{gv.SN}/station/{gv.cf.station.station_no}/info'
        gv.shop_floor_url = f'http://{gv.cf.station.mes_shop_floor}/api/CHKRoute/serial/{gv.SN}/station/{gv.cf.station.station_name}'
        gv.mesPhases = robotsystem.model.product.MesInfo(gv.SN, gv.cf.station.station_no, gv.version)
        init_create_dirs()
        gv.csv_list_header = []
        gv.csv_list_result = []
        gv.error_code_first_fail = ''
        gv.error_details_first_fail = ''
        gv.finalTestResult = False
        gv.setIpFlag = False
        gv.DUTMesIP = ''
        gv.MesMac = ''
        gv.sec = 0
        if not gv.SingleStepTest:
            gv.SuiteNo = -1
            gv.StepNo = -1
        gv.WorkOrder = '1'
        gv.startTimeJsonFlag = True
        gv.startTimeJson = datetime.now()
        self.ui.lb_failInfo.setHidden(True)
        self.ui.lb_testTime.setHidden(True)
        self.sec = 1
        self.SetTestStatus(TestStatus.START)

    def SetTestStatus(self, status: TestStatus):
        """设置并处理不同的测试状态"""
        try:
            if status == TestStatus.START:
                self.main_form.ui.treeWidget.blockSignals(True)
                if not gv.SingleStepTest:
                    self.my_signals.textEditClearSignal[str].emit('')
                self.my_signals.lineEditEnableSignal[bool].emit(False)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_status, 'Testing', 36, Qt.yellow)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_errorCode, '', 20, Qt.yellow)
                self.my_signals.timingSignal[bool].emit(True)
                gv.startTime = datetime.now()
                self.my_signals.setIconSignal[QAction, QIcon].emit(self.ui.actionStart,
                                                                   QIcon(':/images/Pause-icon.png'))
                gv.startFlag = True
                lg.logger.debug(f"Start test,SN:{gv.SN},Station:{gv.cf.station.station_no},DUTMode:{gv.dut_model},"
                                f"TestMode:{gv.cf.dut.test_mode},IsDebug:{gv.IsDebug},"
                                f"FTC:{gv.cf.station.fail_continue},SoftVersion:{gv.version}")
                self.my_signals.update_tableWidget[str].emit('clear')
                gv.pause_event.set()
            elif status == TestStatus.FAIL:
                gv.total_fail_count += 1
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_status, 'FAIL', 36, Qt.red)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_testTime, str(self.sec), 11,
                                                                           Qt.gray)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_errorCode,
                                                                           gv.error_details_first_fail, 20, Qt.red)
                UpdateContinueFail(False)
                if gv.setIpFlag:
                    gv.dut_comm.send_command(f"luxsetip {gv.cf.dut.dut_ip} 255.255.255.0", )
            elif status == TestStatus.PASS:
                gv.total_pass_count += 1
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_status, 'PASS', 36, Qt.green)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_errorCode, str(self.sec), 20,
                                                                           Qt.green)
                UpdateContinueFail(True)
            elif status == TestStatus.ABORT:
                gv.total_abort_count += 1
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_status, 'Abort', 36, Qt.gray)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_testTime, str(self.sec), 11,
                                                                           Qt.gray)
                self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_errorCode,
                                                                           gv.error_details_first_fail, 20, Qt.gray)
        except Exception as e:
            lg.logger.exception(f"SetTestStatus Exception！！{e}")
        finally:
            try:
                if status != TestStatus.START:
                    self.my_signals.setIconSignal[QAction, QIcon].emit(self.ui.actionStart,
                                                                       QIcon(':/images/Start-icon.png'))
                    if gv.dut_comm is not None:
                        gv.dut_comm.close()
                    if gv.cf.station.fix_flag:
                        gv.FixSerialPort.SendCommand('AT+TESTEND%', 'OK')
                    # SFTP
            except Exception as e:
                lg.logger.exception(f"SetTestStatus Exception！！{e}")
            finally:
                try:
                    if status != TestStatus.START:
                        self.my_signals.lineEditEnableSignal[bool].emit(True)
                        self.my_signals.updateStatusBarSignal[str].emit('')
                        # save config/
                        # gv.txtLogPath = rf'{gv.logFolderPath}\{str(gv.finalTestResult).upper()}_{gv.SN}_{gv.error_details_first_fail}_{time.strftime("%H-%M-%S")}.txt'
                        self.my_signals.saveTextEditSignal[str].emit('')
                        if not gv.finalTestResult:
                            self.my_signals.updateLabel[QLabel, str, int, QBrush].emit(self.ui.lb_errorCode,
                                                                                       gv.error_details_first_fail, 20,
                                                                                       Qt.red)
                        self.my_signals.timingSignal[bool].emit(False)
                        lg.logger.debug(f"Test end,ElapsedTime:{self.sec}s.")
                        gv.startFlag = False
                        self.main_form.ui.treeWidget.blockSignals(False)
                except Exception as e:
                    lg.logger.exception(f"SetTestStatus Exception！！{e}")

    def test_thread(self):
        try:
            while True:
                if gv.startFlag:
                    if gv.IsCycle:
                        while gv.IsCycle:
                            if self.main_form.testcase.run(gv.cf.station.fail_continue):
                                gv.PassNumOfCycleTest += 1
                            else:
                                gv.FailNumOfCycleTest += 1
                    elif gv.SingleStepTest:
                        lg.logger.debug(f'Suite:{gv.SuiteNo},Step:{gv.StepNo}')
                        result = self.main_form.testcase.clone_suites[gv.SuiteNo].steps[
                            gv.StepNo].run(
                            self.main_form.testcase.clone_suites[gv.SuiteNo])
                        gv.finalTestResult = result
                        self.main_form.SetTestStatus(
                            TestStatus.PASS if gv.finalTestResult else TestStatus.FAIL)
                    else:
                        result = self.main_form.testcase.run(gv.cf.station.fail_continue)
                        result1 = upload_Json_to_client(gv.cf.station.rs_url, gv.txtLogPath)
                        result2 = upload_result_to_mes(gv.mes_result)
                        gv.finalTestResult = result & result1 & result2
                        self.main_form.SetTestStatus(
                            TestStatus.PASS if gv.finalTestResult else TestStatus.FAIL)
                        CollectResultToCsv()
                        saveTestResult()
        except Exception as e:
            lg.logger.exception(f"TestThread() Exception:{e}")
            self.main_form.SetTestStatus(TestStatus.ABORT)
        finally:
            lg.logger.debug('finally')


if __name__ == "__main__":
    app = QApplication([])
    mainWin = MainForm()
    mainWin.ui.show()
    app.exec_()
