import threading
import time
import paramiko

class Rover:
    def __init__(self, index, ip_address, on_status_update):
        self.index = index
        self.ip_address = ip_address
        self.on_status_update = on_status_update
        self.is_connected = False
        self.is_running = False
        self.thread = None
        self.username = "pi"  # SSH username
        self.password = "raspberry"  # SSH password

    def start_connection(self):
        if not self.is_running:
            self.thread = threading.Thread(target=self.connect)
            self.thread.start()
            self.is_running = True

    def stop_connection(self):
        self.is_running = False
        if self.thread:
            self.thread.join()

    def connect(self):
        try:
            # Connect to the rover using SSH (example using paramiko)
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.ip_address, username=self.username, password=self.password)

            # Connection successful
            self.is_connected = True
            self.on_status_update(self.index, True)

            # Keep the connection alive (example)
            while self.is_running:
                # Perform some operations or wait
                time.sleep(5)

        except Exception as e:
            print(f"Error connecting to Rover {self.index + 1}: {e}")
            self.is_connected = False
            self.on_status_update(self.index, False)

        finally:
            self.is_running = False
            
    def disconnect(self):
        if self.is_connected:
            self.ssh_client.close()
            self.is_connected = False
            self.on_status_update(self.index, False)
