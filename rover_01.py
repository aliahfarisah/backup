import Pyro5.api
import threading
import time
import pandas as pd

@Pyro5.api.expose
class RoverServer:
    def __init__(self, rover_id):
        self.rover_id = rover_id

    def get_rover_id(self):
        return self.rover_id

    def receive_message(self, message):
        print(f"Rover {self.rover_id} received: {message}")
        return f"Acknowledged: {message}"

def start_server(rover_id, host, port):
    daemon = Pyro5.api.Daemon(host=host, port=port)
    uri = daemon.register(RoverServer(rover_id), objectId=f"rover_{rover_id}")
    print(f"Rover {rover_id} Pyro server running on {uri}")
    daemon.requestLoop()

def send_message_to_rover(rover_ip, rover_port, rover_id, message):
    uri = f"PYRO:rover_{rover_id}@{rover_ip}:{rover_port}"
    rover = Pyro5.api.Proxy(uri)
    response = rover.receive_message(message)
    print(f"Response from Rover {rover_id}: {response}")

def main():
    # Read configuration from CSV using pandas
    df = pd.read_csv('rovers.csv')

    # Initialize configuration storage
    rovers_config = {}

    # Process each row in the DataFrame
    for _, row in df.iterrows():
        rover_id = int(row['rover_id'])
        host = row['host']
        port = int(row['port'])
        other_rover_ip = row['other_rover_ip']
        other_rover_port = int(row['other_rover_port'])
        other_rover_id = int(row['other_rover_id'])
        
        if rover_id not in rovers_config:
            rovers_config[rover_id] = {
                'host': host,
                'port': port,
                'peers': []
            }
        
        rovers_config[rover_id]['peers'].append({
            'ip': other_rover_ip,
            'port': other_rover_port,
            'id': other_rover_id
        })
    
    # Start the server threads for all rovers
    server_threads = []
    for rover_id, config in rovers_config.items():
        host = config['host']
        port = config['port']
        server_thread = threading.Thread(target=start_server, args=(rover_id, host, port))
        server_threads.append(server_thread)
        server_thread.start()
    
    # Give the servers a moment to start up
    time.sleep(2)
    
    # Example client usage - sending messages to the other rovers
    for rover_id, config in rovers_config.items():
        for peer in config['peers']:
            client_thread = threading.Thread(target=send_message_to_rover, args=(peer['ip'], peer['port'], peer['id'], f"Hello from Rover {rover_id}"))
            client_thread.start()
            client_thread.join()
            time.sleep(1)

            client_thread = threading.Thread(target=send_message_to_rover, args=(peer['ip'], peer['port'], peer['id'], "How are you?"))
            client_thread.start()
            client_thread.join()
            time.sleep(1)

if __name__ == "__main__":
    main()
