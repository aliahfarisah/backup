import threading
import time
import Pyro5.api

# Define the server class
@Pyro5.api.expose
class GreetingServer:
    def get_greeting(self):
        return "Hello from the rover!"

# Function to start the Pyro5 server
def start_server(server_port):
    greeting_server = GreetingServer()
    daemon = Pyro5.server.Daemon(host="0.0.0.0", port=server_port)
    uri = daemon.register(greeting_server, "greeting")
    print(f"Server started with URI: {uri}")
    daemon.requestLoop()

# Function to get greeting from another rover
def get_greeting(server_uri):
    with Pyro5.api.Proxy(server_uri) as greeting_server:
        return greeting_server.get_greeting()

# Function to run the client task
def client_task(other_rover_uri):
    while True:
        try:
            greeting = get_greeting(other_rover_uri)
            print(greeting)
        except Exception as e:
            print(f"Failed to get greeting: {e}")
        time.sleep(5)  # Interval between requests

if __name__ == "__main__":
    # Define server and client parameters
    server_port = 9090  # Use a specific port for each rover
    other_rover_uri = "PYRO:greeting@localhost:9090"  # Replace with the actual URI of the other rover

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(server_port,))
    server_thread.start()

    # Start the client task in the main thread
    client_task(other_rover_uri)
