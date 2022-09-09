from PySide2.QtCore import QThread, Signal
import time
import socket
import pickle
import hou
import platform
import os

SOCKET_PORT = 13290
HEADERSIZE = 15

if platform.system() == "Darwin":
    process = os.popen('ipconfig getifaddr en0')
    SERVER = process.read()
    process.close()
else:
    SERVER = socket.gethostbyname(socket.gethostname())

class QSocketMonitor(QThread):

    ButtonCall = Signal(str)
    DataCall = Signal(object)
    Instance = []

    def __init__(self):
        QThread.__init__(self)
        QSocketMonitor.Instance.append(self)
        self.TotalData=b""
        print(SERVER)

    def __del__(self):
        self.quit()
        self.wait()

    def stop(self):
        self.terminate()

    def run(self):
        #time.sleep(0.025)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((SERVER.strip(), SOCKET_PORT))
            print(SOCKET_PORT)
            print(SERVER.strip())

            while True:
                s.listen(5)
                client, address = s.accept()
                data = ""
                data = client.recv(4096)
                if data != "":
                    self.TotalData = b""
                    self.TotalData += data
                    while True:
                        data = client.recv(4096)
                        if data : self.TotalData += data
                        else : break

                    decode_msg = self.TotalData[:HEADERSIZE]
                    print(decode_msg)
                    print_me = decode_msg.decode("utf-8")
                    print(print_me)

                    # inc_msg = pickle.loads(self.TotalData)
                    # if inc_msg == "status_ping":
                    #     self.ButtonCall.emit(address[0] + ":" + str(address[1]))
                    # elif inc_msg == "shutdown!":
                    #     break
                    # else:
                    #     self.DataCall.emit(inc_msg)
        except socket.error as emsg:
            print(emsg)


