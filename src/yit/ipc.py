import os
import socket
import json
from .config import IPC_PIPE

class SocketWrapper:
    """Wraps a socket to behave like a file object (read/write/flush)."""
    def __init__(self, sock):
        self.sock = sock
        self.r_file = sock.makefile("rb", buffering=0)
        self.w_file = sock.makefile("wb", buffering=0)

    def write(self, data):
        self.w_file.write(data)

    def flush(self):
        self.w_file.flush()

    def readline(self):
        return self.r_file.readline()

    def close(self):
        try:
            self.r_file.close()
            self.w_file.close()
            self.sock.close()
        except: pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def connect_ipc():
    """Connects to the MPV IPC."""
    if os.name == 'nt':
        return open(IPC_PIPE, "r+b", buffering=0)
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(IPC_PIPE)
        return SocketWrapper(sock)

def send_ipc_command(command):
    """Sends a JSON-formatted command to the MPV IPC pipe."""
    try:
        with connect_ipc() as f:
            payload = json.dumps(command).encode("utf-8") + b"\n"
            f.write(payload)
            f.flush() # Essential for socket
            response_line = f.readline().decode("utf-8")
            if response_line:
                return json.loads(response_line)
            return {"error": "no_response"}
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        # On Linux, OSError might be "Connection refused" or "No such file"
        return None
    except Exception as e:
        print(f"Error communicating with player: {e}")
        return None

def get_ipc_property(prop):
    """Gets a property from MPV."""
    try:
        with connect_ipc() as f:
            cmd = {"command": ["get_property", prop]}
            payload = json.dumps(cmd).encode("utf-8") + b"\n"
            f.write(payload)
            f.flush()
            
            # Simple read line
            response = f.readline().decode("utf-8")
            return json.loads(response)
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        return None
    except Exception:
        return None
