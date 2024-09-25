import threading
import time
import Pyro5.api

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
            self.thread_connect = threading.Thread(target=self.connect)
            self.thread_connect.start()
            #self.thread_verify = threading.Thread(target=self.verify_identity)
            #self.thread_verify.start()
            self.is_running = True

    def stop_connection(self):
        self.is_running = False
        if self.thread_connect:
            self.thread_connect.join()
        #if self.thread_verify:
            #self.thread_verify.join()

    def connect(self):
        try:
            self.is_connected = True
            self.on_status_update(self.rover_id, '#4D4E6D')  # Update status to yellow during connection

            # Verify the rover identity
            exit_status, id_rover = self.verify_identity()
            
            if exit_status == 0:
                self.id_rover_verified = id_rover  # Store the verified id_rover
                self.on_status_update(self.rover_id, 'green')  # Update status to green upon successful verification
                print(f"Rover {self.rover_id} successfully connected and identity verified. ID: {self.id_rover_verified}\n")
            elif exit_status == 1:
                self.on_status_update(self.rover_id, 'yellow')  # Update status to yellow if verification failed
                print(f"Rover {self.rover_id} failed identity verification or ID not found. Exit Status: {exit_status}\n")
            else:
                self.on_status_update(self.rover_id, 'red')  # Update status to red if there was an error
                print(f"Error during identity verification for Rover {self.rover_id}. Exit Status: {exit_status}\n")

            while self.is_running:
                time.sleep(5)  # Adjust sleep duration as needed

        except Exception as e:
            print(f"Error connecting to Rover {self.rover_id}: {e}\n")
            self.on_status_update(self.rover_id, 'red')  # Update status to default color upon error

        finally:
            self.is_running = False
            self.is_connected = False

    def verify_identity(self):
        try:
            # Connect to the remote Pyro server
            with Pyro5.api.Proxy(f"PYRO:identity@{self.ip_address}:9090") as identity_service:
                exit_status = identity_service.check_identity(self.rover_id)
                return exit_status, self.rover_id
        except Pyro5.errors.CommunicationError as e:
            print(f"Communication error verifying identity for Rover {self.rover_id}: {e}")
            return 2, None  # Return 2 for communication errors
        except Exception as e:
            print(f"Error verifying identity for Rover {self.rover_id}: {e}")
            return 3, None  # Return 3 for other errors
        
    def execute_movement(self):
        try:
            # Connect to the remote Pyro server
            with Pyro5.api.Proxy(f"PYRO:move@{self.ip_address}:9093") as movement_service:
                movement_service.start_movement(self.rover_id)
        except Pyro5.errors.CommunicationError as e:
            print(f"Communication error verifying identity for Rover {self.rover_id}: {e}")
            return 2, None  # Return 2 for communication errors
        
        
    

    