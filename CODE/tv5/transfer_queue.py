import queue


class TransferQueue:

    def __init__(self, max_size=100):
        self.queue = queue.Queue(maxsize=max_size)

    def put(self, task):
        """
        Thêm một tác vụ vào hàng đợi.
        """
        self.queue.put(task)

    def get(self, timeout=1):
        """
        Lấy tác vụ tiếp theo.
        """
        return self.queue.get(timeout=timeout)

    def task_done(self):
        """
        Đánh dấu tác vụ đã hoàn thành.
        """
        self.queue.task_done()

    def empty(self):
        return self.queue.empty()