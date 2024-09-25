import threading
import time
import Pyro5.api
import csv

# Define the server class
@Pyro5.api.expose
class GreetingServer:
    def __init__(self, rover_id):
        self.rover_id = rover_id

    def get_greeting(self):
        return f"Hello from {self.rover_id}!"

# Function to start the Pyro5 server
def start_server(rover_id, server_port):
    greeting_server = GreetingServer(rover_id)
    daemon = Pyro5.server.Daemon(host="0.0.0.0", port=server_port)
    uri = daemon.register(greeting_server, "greeting")
    print(f"Server started for Rover {rover_id} with URI: {uri}")
    daemon.requestLoop()

# Function to get greeting from another rover
def get_greeting(server_uri):
    with Pyro5.api.Proxy(server_uri) as greeting_server:
        return greeting_server.get_greeting()

# Function to run the client task
def client_task(rover_id, other_rovers):
    while True:
        for other_rover in other_rovers:
            try:
                other_rover_uri = f"PYRO:greeting@{other_rover['IP']}:{other_rover['Port']}"
                greeting = get_greeting(other_rover_uri)
                print(f"Rover {rover_id} received: {greeting}")
            except Exception as e:
                print(f"Rover {rover_id} failed to get greeting from Rover {other_rover['ID']}: {e}")
        time.sleep(5)  # Interval between requests

# Function to read configuration from CSV
def read_config(file_path, rover_id):
    other_rovers = []
    my_config = None
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row["ID"] == rover_id:
                my_config = row
            else:
                other_rovers.append(row)
    return my_config, other_rovers

if __name__ == "__main__":
    rover_id = "1"  # Change this for each rover
    config_file = "rovers.csv"

    my_config, other_rovers = read_config(config_file, rover_id)
    if not my_config:
        print(f"Configuration for Rover {rover_id} not found in {config_file}")
        exit(1)

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(my_config["ID"], int(my_config["Port"])))
    server_thread.start()

    # Start the client task in the main thread
    client_task(my_config["ID"], other_rovers)
