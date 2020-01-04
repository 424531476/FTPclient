import os
import ftplib
from ftpclient import FtpClient, FileInfo
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtGui import QDragEnterEvent
from PyQt5.QtCore import QEvent


class ExplorerWidget(QtWidgets.QTableWidget):
    def __init__(self, *args):
        QtWidgets.QTableWidget.__init__(self, *args)
        self.pwd = '/'
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resizeRowsToContents()
        self.setAcceptDrops(True)
        self.upload_file = None
        self.upload_directory = None

    def init(self, upload_file, upload_directory):
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.upload_file = upload_file
        self.upload_directory = upload_directory

    def dragEnterEvent(self, e: QDragEnterEvent):
        QtWidgets.QTableWidget.dragEnterEvent(self, e)
        if e.type() != QEvent.DragEnter:
            return
        text = e.mimeData().text()
        files = text.split('\n')
        for file in files:
            if not file.startswith(r'file:///'):
                return
            file = file[len(r'file:///'):]
            if os.path.isdir(file) or os.path.isfile(file):
                e.accept()
            break

    def dropEvent(self, e: QDragEnterEvent):
        text = e.mimeData().text()
        files = text.split('\n')
        for file in files:
            file = file[len(r'file:///'):]
            name = os.path.split(file)[1]
            save_file = os.path.join(self.pwd, name)
            if os.path.isdir(file) and self.upload_directory is not None:
                self.upload_directory(file, save_file)
            elif os.path.isfile(file) and self.upload_file is not None:
                self.upload_file(file, save_file)

    def dragMoveEvent(self, e: QDragEnterEvent):
        pass

    def refresh(self):
        ftp = FtpClient.ftp()
        if ftp.sock is None:
            self.setRowCount(0)
            return
        try:
            file_list = ftp.listdir()
        except ftplib.error_perm as e:
            print(e)
            file_list = list()
        self.pwd = ftp.pwd()
        if self.pwd != '/':
            file_list.insert(0, FileInfo('..', '0', '', 'drwxrwxrwx'))
        self.setRowCount(len(file_list))
        for i in range(0, len(file_list)):
            self.setItem(i, 0, QTableWidgetItem(file_list[i].name))
            self.setItem(i, 1, QTableWidgetItem(file_list[i].size))
            self.setItem(i, 2, QTableWidgetItem(file_list[i].date))
            self.setItem(i, 3, QTableWidgetItem(file_list[i].chmod))

    def select_file_info_list(self):
        index_list = self.select_index_list()
        file_list = list()
        for i in index_list:
            file_name = self.item(i, 0).text()
            is_dir = self.item(i, 3).text()[0] == 'd'
            file_list.append((file_name, is_dir))
        return file_list

    def select_index_list(self):
        items = self.selectedItems()
        index_list = list()
        for item in items:
            if item.column() != 0:
                continue
            if item.text() != '..':
                index_list.append(item.row())
        return index_list
