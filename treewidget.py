import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QTreeWidgetItem
from ftpclient import FtpClient
import threading


class TreeWidget(QtWidgets.QTreeWidget):
    def __init__(self, *args):
        QtWidgets.QTreeWidget.__init__(self, *args)
        self.setHeaderHidden(True)
        self.clicked.connect(self.on_clicked)
        # self.setRootIsDecorated(False)

    def init(self, refresh):
        self.notice_refresh = refresh

    def refresh(self):
        if hasattr(self, 't') and self.t.is_alive():
            return
        ftp = FtpClient.ftp()
        if ftp.sock is None:
            self.clear()
            return
        ftp = FtpClient()
        ftp.reconnect()
        self.t = threading.Thread(target=TreeWidget.show_item, args=(ftp, self, '/'))
        self.t.setDaemon(True)
        self.t.start()

    @staticmethod
    def show_item(ftp, parent_item, parent_dir: str):
        child_count = None
        child_item = None
        if hasattr(parent_item, 'topLevelItemCount'):
            child_count = getattr(parent_item, 'topLevelItemCount')
        if hasattr(parent_item, 'topLevelItem'):
            child_item = getattr(parent_item, 'topLevelItem')
        if hasattr(parent_item, 'childCount'):
            child_count = getattr(parent_item, 'childCount')
        if hasattr(parent_item, 'child'):
            child_item = getattr(parent_item, 'child')

        item_old_dict = dict()
        item_name_new_list = list()
        for i in range(child_count()):
            item = child_item(i)
            item_old_dict[item.text(0)] = item

        # ftp = FtpClient.ftp()
        ftp.cwd(parent_dir)
        file_info_list = ftp.listdir('.')
        for file_info in file_info_list:
            if file_info.chmod[0] == 'd':
                item_name_new_list.append(file_info.name)
                file_dir = os.path.join(parent_dir, file_info.name)
                if file_info.name not in item_old_dict:
                    item = QTreeWidgetItem(parent_item, [file_info.name, file_dir])
                else:
                    item = item_old_dict[file_info.name]
                TreeWidget.show_item(ftp, item, file_dir)
        for item_name in item_old_dict:
            item = item_old_dict[item_name]
            if item_name not in item_name_new_list:
                if hasattr(parent_item, 'removeChild'):
                    parent_item.removeChild(item)
        del_count = 0
        for i in range(child_count()):
            item = child_item(i - del_count)
            item_name = item.text(0)
            if item_name not in item_name_new_list:
                if hasattr(parent_item, 'takeTopLevelItem'):
                    parent_item.takeTopLevelItem(i)
                    del_count += 1

    def on_clicked(self, qmodeLindex):
        item = self.currentItem()
        ftp = FtpClient.ftp()
        try:
            ftp.cwd(item.text(1))
        except ConnectionResetError as e:
            if hasattr(e, 'winerror') and e.winerror == 10054:
                ftp.reconnect()
                ftp.cwd(item.text(1))
            else:
                print(e)
        except Exception as e:
            print(e)
        else:
            if hasattr(self, 'notice_refresh'):
                self.notice_refresh()
