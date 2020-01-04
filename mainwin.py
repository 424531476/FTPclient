import os
import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView, QHeaderView, QFileDialog, QMessageBox
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import pyqtSignal, Qt
import ui_mainwin
import traceback
from ftpclient import FtpClient, FtpLoginInfo
from jie import asynctask
import config


class ConnTask(asynctask.TaskAdapter):
    def __init__(self, view, login_info: FtpLoginInfo):
        asynctask.TaskAdapter.__init__(self)
        self.view = view
        self.login_info = login_info
        self.res = False
        self.e = None

    def do_in_background(self):
        try:
            FtpClient.ftp().connect_login(self.login_info)
        except Exception as e:
            FtpClient.ftp().disconnect()
            self.res = False
            self.e = e
        else:
            self.res = True
            self.e = None

    def on_post_execute(self):
        if self.res:
            self.view.setstate_connect()
        elif isinstance(self.e, Exception):
            print(self.e)
            self.view.setstate_disconnect()
            self.view.status_label.setText(str(self.e))
        self.view.ui.ConnectButton.setEnabled(True)


class SignalOut:
    def __init__(self, signal):
        self.signal = signal

    def write(self, out):
        self.signal.emit(out)

    def flush(self):
        pass


class MainWin(QtWidgets.QMainWindow):
    async_signal = pyqtSignal(object)
    out_signal = pyqtSignal(object)
    title = 'JIE FTP'
    int_test = 1

    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = ui_mainwin.Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.splitterHT.setStretchFactor(0, 1)
        self.ui.splitterHT.setStretchFactor(1, 4)
        self.ui.splitterV.setStretchFactor(0, 3)
        self.ui.splitterV.setStretchFactor(1, 2)
        self.status_label = QtWidgets.QLabel(self.ui.centralwidget)
        self.ui.statusbar.addWidget(self.status_label)
        self.setWindowTitle(self.title)
        self.out_signal.connect(self.text_edit_out)
        sys.stdout = SignalOut(self.out_signal)
        self.async_task = asynctask.AsyncTask(self.async_signal)
        self.ui.action_upload.triggered.connect(self.on_upload_menu)
        self.ui.action_download.triggered.connect(self.on_download_menu)
        self.ui.action_delete.triggered.connect(self.on_delete_menu)
        self.ui.action_refresh.triggered.connect(self.on_refresh)
        self.setstate_disconnect()
        self.ui.ExplorerWidget.init(self.upload_file, self.upload_directory)
        self.ui.TreeWidget.init(self.refresh)
        self.init_edit()

    def init_edit(self):
        conf = config.Config('ftp.ini')
        conf_client = conf['client']
        if 'address' in conf_client:
            self.ui.HostEdit.setText(conf_client['address'])
        if 'port' in conf_client:
            self.ui.PortEdit.setText(conf_client['port'])
        if 'user' in conf_client:
            self.ui.UserEdit.setText(conf_client['user'])

    def text_edit_out(self, out):
        self.ui.textEdit.moveCursor(QTextCursor.End)
        self.ui.textEdit.insertPlainText(str(out))

    def on_connect_btn_click(self):
        text = self.ui.ConnectButton.text()
        if text == '连接':
            self.connect()
        elif text == '断开':
            self.close()
        else:
            print('连接按钮异常' + text)

    def connect(self):
        self.ui.HostEdit.setEnabled(False)
        self.ui.PortEdit.setEnabled(False)
        self.ui.UserEdit.setEnabled(False)
        self.ui.PwdEdit.setEnabled(False)
        self.ui.ConnectButton.setEnabled(False)
        host = self.ui.HostEdit.text()
        port = int(self.ui.PortEdit.text())
        user = self.ui.UserEdit.text()
        pwd = self.ui.PwdEdit.text()
        login_info = FtpLoginInfo(host, port, user, pwd)
        conn_task = ConnTask(self, login_info)
        self.async_task.execute(conn_task)
        # self.async_task.execute(MainWin.connect_proc, self.on_connect, args=login_info)
        self.status_label.setText('正在连接...')

    def close(self):
        FtpClient.ftp().disconnect()
        self.setstate_disconnect()

    def on_explorer_dbclick(self):
        row = self.ui.ExplorerWidget.currentRow()
        d = self.ui.ExplorerWidget.item(row, 3).text()[0]
        if d != 'd':
            return
        dir_name = self.ui.ExplorerWidget.item(row, 0).text()
        ftp = FtpClient.ftp()
        try:
            ftp.cwd(dir_name)
        except ConnectionResetError as e:
            if hasattr(e, 'winerror') and e.winerror == 10054:
                ftp.reconnect()
                ftp.cwd(dir_name)
            else:
                print(e)
        except Exception as e:
            print(e)
        self.refresh()

    def on_explorer_context_menu_requested(self, point):
        pos = self.ui.ExplorerWidget.mapToGlobal(self.ui.ExplorerWidget.pos())
        self.ui.menu.move(pos + point)
        self.ui.menu.show()

    def on_delete_menu(self):
        file_list = self.ui.ExplorerWidget.select_file_info_list()
        if len(file_list) == 0:
            return
        reply = QMessageBox.information(self, '1', '确认要删除%d 项?' % (len(file_list)),
                                        QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            for file_name, is_dir in file_list:
                if is_dir:
                    FtpClient.ftp().rmd(file_name)
                else:
                    FtpClient.ftp().delete(file_name)
            self.refresh()
        except Exception as e:
            print(e)

    def on_upload_menu(self):
        file_paths, file_type = QFileDialog.getOpenFileNames(parent=self, caption='请选择文件', directory='.',
                                                             filter='All Files (*);;Text Files (*.txt)')
        for file_path in file_paths:
            file_name = os.path.split(file_path)[1]
            save_file = os.path.join(self.ui.DirectorEdit.text(), file_name)
            self.upload_file(file_path, save_file)

    def upload_file(self, src_file, save_file):
        self.ui.TransferWidget.upload(src_file, save_file)

    def upload_directory(self, src_dir, save_dir):
        try:
            ftp = FtpClient.ftp()
            pwd = '.'
        except Exception as e:
            print(e)
            return
        try:
            pwd = ftp.pwd()
            parent_dir, save_name = os.path.split(save_dir)
            ftp.cwd(parent_dir)
            ftp.mkd(save_name)
            file_names = os.listdir(src_dir)
            for file_name in file_names:
                src_file = os.path.join(src_dir, file_name)
                save_file = os.path.join(save_dir, file_name)
                if os.path.isdir(src_file):
                    self.upload_directory(src_file, save_file)
                else:
                    self.upload_file(src_file, save_file)
        except Exception as e:
            print(e)
        finally:
            ftp.cwd(pwd)

    def on_download_menu(self):
        file_list = self.ui.ExplorerWidget.select_file_info_list()
        if len(file_list) == 0:
            return
        save_dir = QFileDialog.getExistingDirectory(parent=self, caption='选择文件夹', directory='./')
        if save_dir == '':
            return
        for file_name, is_dir in file_list:
            src_file = os.path.join(self.ui.DirectorEdit.text(), file_name)
            save_file = os.path.join(save_dir, file_name)
            if is_dir:
                self.download_directory(src_file, save_file)
            else:
                self.ui.TransferWidget.download(src_file, save_file)

    def download_directory(self, src_dir, save_dir):
        try:
            ftp = FtpClient.ftp()
            pwd = '.'
        except Exception as e:
            print(e)
            return
        try:
            pwd = ftp.pwd()
            os.mkdir(save_dir)
            parent_dir, src_name = os.path.split(src_dir)
            ftp.cwd(parent_dir)
            file_list = ftp.listdir(src_name)
            for file_info in file_list:
                src_file = os.path.join(src_dir, file_info.name)
                save_file = os.path.join(save_dir, file_info.name)
                if file_info.chmod[0] == 'd':
                    self.download_directory(src_file, save_file)
                else:
                    self.ui.TransferWidget.download(src_file, save_file)
        except Exception as e:
            print(e)
        finally:
            ftp.cwd(pwd)

    def on_refresh(self):
        self.refresh()

    def refresh(self):
        ftp = FtpClient.ftp()
        if ftp.sock is None:
            self.ui.DirectorEdit.setText('')
            self.ui.ExplorerWidget.refresh()
            self.ui.TreeWidget.refresh()
            return
        try:
            pwd = ftp.pwd()
        except ConnectionResetError as e:
            if hasattr(e, 'winerror') and e.winerror == 10054:
                ftp.reconnect()
                pwd = ftp.pwd()
            else:
                pwd = ''
                print(e)
        except Exception as e:
            pwd = ''
            print(e)
        try:
            self.ui.DirectorEdit.setText(pwd)
            self.ui.ExplorerWidget.refresh()
            self.ui.TreeWidget.refresh()
        except Exception as e:
            print(e)

    def setstate_disconnect(self):
        self.ui.HostEdit.setEnabled(True)
        self.ui.PortEdit.setEnabled(True)
        self.ui.UserEdit.setEnabled(True)
        self.ui.PwdEdit.setEnabled(True)
        self.ui.ConnectButton.setText('连接')
        self.ui.ConnectButton.setEnabled(True)
        self.status_label.setText('断开')
        self.setWindowTitle(self.title)
        self.refresh()

    def setstate_connect(self):
        self.ui.HostEdit.setEnabled(False)
        self.ui.PortEdit.setEnabled(False)
        self.ui.UserEdit.setEnabled(False)
        self.ui.PwdEdit.setEnabled(False)
        self.ui.ConnectButton.setText('断开')
        self.ui.ConnectButton.setEnabled(True)
        host = self.ui.HostEdit.text()
        self.status_label.setText('连接%s成功' % host)
        self.setWindowTitle('%s - %s' % (host, self.title))
        self.refresh()

    def setstate_connecting(self):
        self.ui.HostEdit.setEnabled(False)
        self.ui.PortEdit.setEnabled(False)
        self.ui.UserEdit.setEnabled(False)
        self.ui.PwdEdit.setEnabled(False)
        self.ui.ConnectButton.setText('连接')
        self.ui.ConnectButton.setEnabled(False)
        host = self.ui.HostEdit.text()
        self.status_label.setText('正在连接%s' % host)
        self.setWindowTitle(self.title)


def main() -> int:
    try:
        app = QtWidgets.QApplication(sys.argv)
        win = MainWin()
        win.show()
        return app.exec_()
    except Exception as e:
        print(traceback.format_exc())
        print(str(e))
        QMessageBox.information(None, "error", str(e), QMessageBox.Ok, QMessageBox.Ok)
        return 0


if __name__ == '__main__':
    main()
