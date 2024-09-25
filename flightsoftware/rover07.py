import threading
import time
import paramiko

class Rover:
    def __init__(self, rover_id, ip_address, on_status_update):
        self.rover_id = rover_id
        self.ip_address = ip_address
        self.on_status_update = on_status_update
        self.is_connected = False
        self.is_running = False
        self.thread = None
        self.username = "pi"
        self.password = "raspberry"
        self.ssh_client = None
        self.id_rover_verified = None  # Initialize id_rover attribute

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
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.ip_address, username=self.username, password=self.password)

            self.is_connected = True
            self.on_status_update(self.rover_id, 'yellow')

            # Verify the rover identity
            exit_status, id_rover = self.verify_identity()
            
            if exit_status == 0:
                self.id_rover_verified = id_rover  # Store the verified id_rover
                self.on_status_update(self.rover_id, 'green')
                print(f"Rover {self.rover_id} successfully connected and identity verified. ID: {self.id_rover_verified}")
            else:
                self.on_status_update(self.rover_id, 'yellow')
                print(f"Rover {self.rover_id} failed identity verification or ID not found. Exit Status: {exit_status}")

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
            if self.ssh_client:
                self.ssh_client.close()

    def verify_identity(self):
        try:
            id_database = self.rover_id  # Use the rover_id for verification
            command = f'cd Desktop/rover && python3 identity.py {id_database}'
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            stdout_output = stdout.read().decode().strip()
            stderr_output = stderr.read().decode().strip()
            
            # print(f"stdout: {stdout_output}")
            # print(f"stderr: {stderr_output}")
            
            if exit_status == 0:
                return 0, stdout_output  # Return the verified ID
            else:
                print(f"Identity verification script error: {stderr_output}")
                return exit_status, None
        except Exception as e:
            print(f"Error verifying identity for Rover {self.rover_id}: {e}")
            return None, None

    def check_csv_exists(self):
        if self.is_connected:
            try:
                command = f'cd Desktop/lightShow && [ -f Rover{self.rover_id}.csv ] && echo "exists" || echo "missing"'
                stdin, stdout, stderr = self.ssh_client.exec_command(command)
                result = stdout.read().decode().strip()
                return result == "exists"
            except Exception as e:
                print(f"Error checking CSV on Rover {self.rover_id}: {e}")
                return False
        else:
            print(f"Rover {self.rover_id} is not connected. Cannot check for CSV.")
            return False

    def execute_movement(self, adjusted_hour, adjusted_minute, adjusted_second):
        if self.is_connected:
            if self.check_csv_exists():
                try:
                    command = f'cd Desktop/lightShow && sudo python3 00_import_csv_rev07.py --id_rover {self.id_rover_verified} --hour {adjusted_hour} --minute {adjusted_minute} --second {adjusted_second}'
                    stdin, stdout, stderr = self.ssh_client.exec_command(command)
                    stdout.channel.recv_exit_status()
                    print(stdout.read().decode())
                    print(stderr.read().decode())
                except Exception as e:
                    print(f"Error executing movement on Rover {self.rover_id}: {e}")
