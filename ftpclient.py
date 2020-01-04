import os
import ftplib
import ssl
from collections import namedtuple
from config import Config


class FtpLoginInfo:
    def __init__(self,
                 host='127.0.0.1',
                 port=21,
                 user='anonymous',
                 pwd=''):
        self.host = host.strip()
        self.port = port
        self.user = user.strip()
        self.pwd = pwd.strip()
        if user == '':
            self.user = 'anonymous'
            self.pwd = ''


FileInfo = namedtuple('FileInfo', ['name', 'size', 'date', 'chmod'])


class FtpClient(ftplib.FTP):
    __ftp = None
    __log_info = None

    def __init__(self):
        config = Config('ftp.ini', encoding='utf8')
        client_config = config['client']
        timeout = client_config.get('timeout', 20)
        encoding = client_config.get('encoding', 'utf8')
        debuglevel = client_config.get('debuglevel', 0)
        pasv = client_config.get('pasv', 1)
        ftplib.FTP.__init__(self, timeout=int(timeout))
        self.encoding = encoding
        self.set_debuglevel(int(debuglevel))
        self.set_pasv(bool(int(pasv)))

    @classmethod
    def is_connect(cls) -> bool:
        return cls.__log_info is not None

    def reconnect(self):
        self.connect_login(FtpClient.__log_info)

    def connect_login(self, log_info: FtpLoginInfo = None):
        self.connect(host=log_info.host, port=log_info.port)
        self.login(user=log_info.user, passwd=log_info.pwd)
        FtpClient.__log_info = log_info

    def disconnect(self):
        with self:
            pass
        FtpClient.__log_info = None

    @staticmethod
    def ftp():
        # TODO 这个多线程并不安全,需要改进
        if FtpClient.__ftp is None:
            FtpClient.__ftp = FtpClient()
        return FtpClient.__ftp

    def listdir(self, file_dir: str = '.') -> list:
        file_line_list = list()
        try:
            self.dir(file_dir, file_line_list.append)
        except ftplib.Error:
            pass
        file_list = list()
        for file_line in file_line_list:
            file = FtpClient.parse_line(file_line)
            file_list.append(file)
        return file_list

    @staticmethod
    def parse_line(line: str) -> FileInfo:
        data_list = list()
        data = ''
        for i in range(len(line)):
            ch = line[i]
            if ch != ' ':
                if len(data_list) == 8:
                    data_list.append(line[i:])
                    break
                data = data + ch
                continue
            if len(data) == 0:
                continue
            data_list.append(data)
            data = ''
        data_list[5] = ' '.join(data_list[5: 8])
        data_list[6] = data_list[8]
        data_list.pop()
        data_list.pop()
        return FileInfo(name=data_list[6], size=data_list[4], date=data_list[5], chmod=data_list[0])

    def cwd(self, file_dir: str):
        parent_dir, name = os.path.split(file_dir)
        if parent_dir == '' or parent_dir == '/':
            return ftplib.FTP.cwd(self, file_dir)
        self.cwd(parent_dir)
        return ftplib.FTP.cwd(self, name)

    def retrlines(self, cmd, callback=None):
        """Retrieve data in line mode.  A new port is created for you.

        Args:
          cmd: A RETR, LIST, or NLST command.
          callback: An optional single parameter callable that is called
                    for each line with the trailing CRLF stripped.
                    [default: print_line()]

        Returns:
          The response code.
        """
        if callback is None:
            callback = print
        resp = self.sendcmd('TYPE A')
        with self.transfercmd(cmd) as conn, \
                conn.makefile('r', encoding=self.encoding, errors='ignore') as fp:
            while 1:
                line = fp.readline(self.maxline + 1)
                if len(line) > self.maxline:
                    raise ftplib.Error("got more than %d bytes" % self.maxline)
                if self.debugging > 2:
                    print('*retr*', repr(line))
                if not line:
                    break
                if line[-2:] == '\r\n':
                    line = line[:-2]
                elif line[-1:] == '\n':
                    line = line[:-1]
                callback(line)
            # shutdown ssl layer
            if ssl.SSLSocket is not None and isinstance(conn, ssl.SSLSocket):
                conn.unwrap()
        return self.voidresp()
