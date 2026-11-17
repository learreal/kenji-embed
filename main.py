import socket
import sys
import threading
import time
import requests
from PyQt6.QtWidgets import QApplication, QMessageBox
from werkzeug.serving import make_server
from backend import app, init_db
from frontend import GymWindow

HOST = "127.0.0.1"  # Change to "0.0.0.0" when connecting your ESP32 over LAN
PORT = 8000


class FlaskThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.server = make_server(HOST, PORT, app)

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()


def port_busy(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    qt_app = QApplication(sys.argv)

    if port_busy(PORT):
        QMessageBox.critical(None, "Port Busy", f"Port {PORT} is already in use.")
        sys.exit(1)

    init_db()
    server = FlaskThread()
    server.start()

    base_url = f"http://127.0.0.1:{PORT}"
    for _ in range(25):
        try:
            if requests.get(f"{base_url}/api/health", timeout=0.3).status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    win = GymWindow(api_url=base_url)
    win.show()

    code = qt_app.exec()
    server.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()