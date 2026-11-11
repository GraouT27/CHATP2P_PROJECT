import queue

from PyQt6.QtCore import QThread, pyqtSignal

from transfer_queue import TransferQueue  #sửa sau



class TransferWorker(QThread):

    # Signal báo trạng thái về GUI
    status_changed = pyqtSignal(str)

    # Signal báo dữ liệu đã xử lý
    data_processed = pyqtSignal(object)

    # Signal báo lỗi
    error_occurred = pyqtSignal(str)


    def __init__(self):

        super().__init__()

        self.transfer_queue = TransferQueue()

        self.running = True


    def add_task(self, task):

        """
        Thêm task từ GUI hoặc Network.
        """

        self.transfer_queue.put(task)

        self.status_changed.emit(
            "Đã thêm tác vụ vào Queue"
        )


    def run(self):

        """
        Hàm này chạy trong QThread.
        """

        self.status_changed.emit(
            "Transfer Worker đã bắt đầu"
        )

        while self.running:

            try:

                task = self.transfer_queue.get(
                    timeout=1
                )

                self.process_task(task)

                self.transfer_queue.task_done()


            except queue.Empty:

                # Queue đang trống
                continue


            except Exception as error:

                self.error_occurred.emit(
                    str(error)
                )


        self.status_changed.emit(
            "Transfer Worker đã dừng"
        )


    def process_task(self, task):

        """
        Xử lý task lấy từ Queue.
        """

        task_type = task.get("type")

        if task_type == "message":

            data = task.get("data")

            self.data_processed.emit(data)

            self.status_changed.emit(
                "Đã xử lý Message"
            )


        elif task_type == "file":

            self.status_changed.emit(
                "Đã nhận File Task"
            )

            # Chặng sau sẽ xử lý Chunking thật


        else:

            raise ValueError(
                f"Task không hợp lệ: {task_type}"
            )


    def stop(self):

        """
        Dừng Worker an toàn.
        """

        self.running = False