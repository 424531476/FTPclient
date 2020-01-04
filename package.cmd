chcp 65001
pyinstaller -F -w  -i jie.ico -n JieFtp mainwin.py
copy "ftp.ini" "dist/ftp.ini"
pause