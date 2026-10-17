import pickle
import socket

from PySide6.QtCore import QThread, Signal

SOCKET_PORT = 13290
HEADERSIZE = 15
SERVER = "0.0.0.0"

class QSocketMonitor(QThread):

    ChopsCall = Signal(object)
    ButtonCall = Signal(str)
    DataCall = Signal(object)
    Instance = []

    def __init__(self):
        super().__init__()
        QSocketMonitor.Instance.append(self)
        self.run_time = True

    def stop(self):
        self.run_time = False
        self.requestInterruption()

    def _receive_data(self, client):
        chunks = []
        client.settimeout(0.2)
        while self.run_time and not self.isInterruptionRequested():
            try:
                data = client.recv(4096)
            except socket.timeout:
                continue
            if not data:
                return b"".join(chunks)
            chunks.append(data)
        return b""

    def _dispatch_data(self, data, address):
        if len(data) < HEADERSIZE:
            raise ValueError("incomplete socket header")

        header = data[:HEADERSIZE].decode("utf-8").strip()
        payload = data[HEADERSIZE:]
        if header and header != "normal_send":
            take_num, separator, slate_name = header.partition(".")
            if not separator:
                raise ValueError("invalid bclip header")
            self.ChopsCall.emit((take_num, slate_name, payload))
            return

        message = pickle.loads(payload)
        if message == "status_ping":
            self.ButtonCall.emit(f"{address[0]}:{address[1]}")
        elif message == "shutdown!":
            self.stop()
        else:
            self.DataCall.emit(message)

    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((SERVER, SOCKET_PORT))
                server.listen(5)
                server.settimeout(0.2)

                while self.run_time and not self.isInterruptionRequested():
                    try:
                        client, address = server.accept()
                    except socket.timeout:
                        continue

                    with client:
                        data = self._receive_data(client)
                    if not data:
                        continue
                    try:
                        self._dispatch_data(data, address)
                    except (EOFError, UnicodeDecodeError, ValueError, pickle.UnpicklingError) as error:
                        print(f"Ignoring malformed socket message: {error}")
        except OSError as error:
            if self.run_time:
                print(f"Socket listener stopped: {error}")
        finally:
            if self in QSocketMonitor.Instance:
                QSocketMonitor.Instance.remove(self)
