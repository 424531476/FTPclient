import os
import time
import ftpclient
from concurrent.futures import ThreadPoolExecutor
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtCore import pyqtSignal
import traceback


class TransferWidget(QtWidgets.QTableWidget):
    show_signal = pyqtSignal(object)

    def __init__(self, *args):
        QtWidgets.QTableWidget.__init__(self, *args)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.resizeRowsToContents()
        # self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pool = ThreadPoolExecutor(4)
        self.show_signal.connect(self.update_proc)

    def __del__(self):
        self.pool.shutdown()

    class TransferCallback:
        def __init__(self, signal, transfer_hash, file_size, call=None):
            self.siganl = signal
            self.hash = transfer_hash
            self.process_size = 0
            self.file_size = file_size
            self.call = call
            self.t0 = time.time()
            self.block_size = 0

        def __call__(self, *args, **kwargs):
            data = args[0]
            if self.call is not None:
                self.call(data)
            data_len = len(data)
            self.process_size += data_len
            self.block_size += data_len
            t = time.time() - self.t0
            speed = None
            if t > 1:
                speed = self.block_size / t
                self.t0 = time.time()
                self.block_size = 0
            if speed is not None or int(t * 1000) % 20 == 0 or self.process_size == self.file_size:
                self.siganl.emit((self.hash, speed, self.process_size, self.file_size))

    def upload(self, src_file, dest_file):
        transfer_hash = hash('upload:%s:%s' % (src_file, dest_file))
        row = self.rowCount()
        for i in range(row):
            if self.item(i, 0).hash == transfer_hash:
                print('%s已在传输队列中' % os.path.split(src_file)[1])
                return
        self.insertRow(row)
        item = QTableWidgetItem(os.path.split(src_file)[1])
        item.hash = transfer_hash
        self.setItem(row, 0, item)
        self.setItem(row, 1, QTableWidgetItem('0%'))
        self.setItem(row, 2, QTableWidgetItem('0KB/S'))
        self.setItem(row, 3, QTableWidgetItem(src_file))
        self.setItem(row, 4, QTableWidgetItem(dest_file))
        self.pool.submit(TransferWidget.upload_process,
                         src_file, dest_file, self.show_signal, transfer_hash)

    @staticmethod
    def upload_process(src_file: str, dest_file: str, show_signal, transfer_hash):
        try:
            with ftpclient.FtpClient()as ftp:
                ftp.reconnect()
                file_size = os.path.getsize(src_file)
                dest_dir, dest_name = os.path.split(dest_file)
                ftp.cwd(dest_dir)
                callback = TransferWidget.TransferCallback(show_signal, transfer_hash, file_size)
                t0 = time.time()
                with open(src_file, 'rb')as fp:
                    try:
                        ret = ftp.storbinary('STOR ' + dest_name, fp=fp, blocksize=1024 * 100, callback=callback)
                    except Exception as e_stor:
                        raise e_stor
                print('%s %s 用时%d秒' % (src_file, ret, time.time() - t0))
        except Exception as e:
            if 'e_stor' in vars():
                if e_stor is e:
                    print(src_file, e_stor)
                else:
                    print(src_file, e_stor, '另一个异常：', e)
            else:
                print(src_file, e)
        show_signal.emit((transfer_hash, '', 1, 1))

    def download(self, src_file: str, dest_file: str):
        transfer_hash = hash('download:%s:%s' % (src_file, dest_file))
        row = self.rowCount()
        for i in range(row):
            if self.item(i, 0).hash == transfer_hash:
                print('%s已在传输队列中' % os.path.split(src_file)[1])
                return
        self.insertRow(row)
        item = QTableWidgetItem(os.path.split(src_file)[1])
        item.hash = transfer_hash
        self.setItem(row, 0, item)
        self.setItem(row, 1, QTableWidgetItem('0%'))
        self.setItem(row, 2, QTableWidgetItem('0KB/S'))
        self.setItem(row, 3, QTableWidgetItem(src_file))
        self.setItem(row, 4, QTableWidgetItem(dest_file))
        self.pool.submit(TransferWidget.download_process,
                         src_file, dest_file, self.show_signal, transfer_hash)

    @staticmethod
    def download_process(src_file: str, dest_file: str, show_signal, transfer_hash):
        try:
            with ftpclient.FtpClient()as ftp:
                ftp.reconnect()
                ftp.voidcmd('TYPE I')
                src_dir, src_name = os.path.split(src_file)
                ftp.cwd(src_dir)
                file_size = ftp.size(src_name)
                t0 = time.time()
                with open(dest_file + '.tmp', 'wb')as fp:
                    try:
                        callback = TransferWidget.TransferCallback(show_signal, transfer_hash, file_size, fp.write)
                        ret = ftp.retrbinary('RETR ' + src_name, callback, blocksize=1024 * 100)
                    except Exception as e_retr:
                        raise e_retr
                os.rename(dest_file + '.tmp', dest_file)
                print('%s %s 用时%d秒' % (src_file, ret, time.time() - t0))
        except Exception as e:
            if 'e_retr' in vars():
                if e_retr is e:
                    print(src_file, e_retr)
                else:
                    print(src_file, e_retr, '另一个异常：', e)
            else:
                print(src_file, e)
            # print(traceback.format_exc())
        show_signal.emit((transfer_hash, '', 1, 1))

    @staticmethod
    def format_file_size(file_size: int):
        s = 'B'
        if file_size > 1024:
            file_size /= 1024
            s = 'KB'
        if file_size > 1024:
            file_size /= 1024
            s = 'MB'
        if file_size > 1024:
            file_size /= 1024
            s = 'GB'
        if file_size > 1024:
            file_size /= 1024
            s = 'TB'
        return '%0.3f%s' % (file_size, s)

    def update_proc(self, args):
        transfer_hash, speed, process_size, file_size = args
        # print('速度:', speed)
        row_count = self.rowCount()
        for i in range(row_count):
            if self.item(i, 0).hash == transfer_hash:
                if process_size == file_size:
                    self.removeRow(i)
                else:
                    if speed is not None:
                        self.item(i, 2).setText(self.format_file_size(speed) + '/S')
                    self.item(i, 1).setText('%0.2f%%' % (process_size * 100 / file_size))
                return
