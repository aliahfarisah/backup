import threading
import time
import paramiko
import csv

class Rover:
    def __init__(self, rover_id, ip_address, on_status_update):
        self.rover_id = rover_id  # Make sure rover_id is stored correctly
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
            # Connect to the rover using SSH
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(self.ip_address, username=self.username, password=self.password)

            # Connection successful, update status to yellow
            self.is_connected = True
            self.on_status_update(self.rover_id, 'yellow')  # Update status using rover_id

            # Verify the rover identity
            command = 'cd Desktop/rover && python3 identity.py ' + str(self.rover_id)
            stdin, stdout, stderr = ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()

            # If the ID matches, turn green, otherwise turn yellow
            if exit_status == 0:
                self.on_status_update(self.rover_id, 'green')
                print(f"Rover {self.rover_id} successfully connected")  # Print rover_id
            else:
                self.on_status_update(self.rover_id, 'yellow')
                print(f"Rover {self.rover_id} not successfully connected with its ID.")

            # Keep the connection alive
            while self.is_running:
                time.sleep(5)
                
        except paramiko.AuthenticationException as auth_exception:
            print(f"Authentication failed for Rover {self.rover_id}: {auth_exception}")
            self.on_status_update(self.rover_id, 'red')

        except Exception as e:
            print(f"Error connecting to Rover {self.rover_id}: {e}\n")
            self.on_status_update(self.rover_id, '#4D4E6D')
        finally:
            self.is_running = False
            self.is_connected = False
