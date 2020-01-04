import threading
from multiprocessing import Event
from PyQt5.QtCore import pyqtBoundSignal


class TaskAdapter:
    def __init__(self):
        self.cancel_event = Event()

    def on_pre_execute(self):
        '''
        任务执行前的初始化操作
        :return:
        '''
        pass

    def do_in_background(self):
        '''
        自定义的线程任务使用yield返回过程数据调用on_progress_update
        :return: 返回yield None终止任务,否则返回值作为调用on_progress_update的参数
        '''
        yield None

    def on_progress_update(self, *args, **kwargs):
        '''
        再主线程显示执行过程或进度
        :param args:
        :param kwargs:
        :return:返回True继续执行，返回False终止任务运行
        '''
        pass

    def on_post_execute(self):
        '''
        任务完成时在主线程调用。
        与on_cancelled只会执行一个
        :return: 不接收返回
        '''
        pass

    def on_cancelled(self):
        '''
        任务取消时在主线程调用。
        与on_post_execute只会执行一个
        :return: 不接收返回
        '''
        pass

    def cancel(self):
        '''
        取消运行任务
        :return:
        '''
        self.cancel_event.set()


class AsyncTask:
    def __init__(self, signal: pyqtBoundSignal):
        self.signal = signal
        self.signal.connect(AsyncTask.callback_slots)

    def execute(self, task: TaskAdapter):
        task.on_pre_execute()
        thread = threading.Thread(target=self.run, args=(task,))
        thread.setDaemon(True)
        thread.start()

    def run(self, task: TaskAdapter):
        it = task.do_in_background()
        # if not isinstance(it, type(i for i in range(1))):
        if str(type(it)) != "<class 'generator'>":
            # 返回值不是生成器那就不管返回值了
            self.signal.emit((None, task.on_post_execute, None))
            return

        for i in it:
            if i is None or task.cancel_event.is_set():
                self.signal.emit((None, task.on_cancelled, None))
                break
            self.signal.emit((task.cancel_event, task.on_progress_update, i))
        else:
            self.signal.emit((None, task.on_post_execute, None))

    @staticmethod
    def callback_slots(args):
        cancel_event, callback, arg = args
        if arg is None:
            res = callback()
        elif isinstance(arg, tuple):
            res = callback(*arg)
        else:
            res = callback(arg)
        if not res and cancel_event:
            cancel_event.set()
