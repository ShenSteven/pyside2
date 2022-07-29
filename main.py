#!/usr/bin/env python
# coding: utf-8
"""
@File   : main.py
@Author : Steven.Shen
@Date   : 2022/3/7
@Desc   : 
"""
import sys
from os.path import dirname, abspath
from traceback import format_exception
from PyQt5.QtWidgets import QApplication, QMessageBox
# import conf.logprint as lg
import ui.mainform as mf

# get app dir path
bundle_dir = ''
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    print('running in a PyInstaller bundle')
    bundle_dir = sys._MEIPASS
else:
    print('running in a normal Python process')
    bundle_dir = dirname(abspath(__file__))
print(bundle_dir)


def excepthook(cls, exception, traceback):
    # lg.logger.exception(format_exception(cls, exception, traceback))
    QMessageBox.critical(None, "Error", "".join(format_exception(cls, exception, traceback)))


def main():
    sys.excepthook = excepthook
    app = QApplication([])
    print("applicationDirPath:", app.applicationDirPath())
    mainWin = mf.MainForm()
    mainWin.ui.show()
    try:
        app.exec_()
    except KeyboardInterrupt:
        # lg.logger.exception('KeyboardInterrupt')
        pass


if __name__ == "__main__":
    # for x in dir():
    #     print(x, ":", eval(x))
    main()