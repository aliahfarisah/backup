import Pyro5.api
import threading
import pandas as pd
from ble_manager import BLEDeviceManager
from rover_nn_rev03 import execute_movement

@Pyro5.api.expose
class RoverServer:
    def __init__(self):
        self.device_manager = BLEDeviceManager()
        self.device_manager.stop_event = threading.Event()
        self.connection_lock = threading.Lock()
        print("RoverServer initialized.")

    def start_connection(self, id_rover):
        with self.connection_lock:
            if not self.device_manager.is_connected():
                print(f"Attempting to start connection with {id_rover}.")
                self.device_manager.start_connection(id_rover)
                # Add a small delay to ensure the connection attempt is registered
                time.sleep(2)
                if self.device_manager.is_connected():
                    print(f"Connected to {id_rover}.")
                else:
                    print(f"Failed to connect to {id_rover}.")
            else:
                print("Already connected.")

    def get_coordinates(self):
        if self.device_manager.is_connected():
            print("Fetching coordinates...")
            info = self.device_manager.get_device_info()

            if not pd.api.types.is_datetime64_any_dtype(info['Time']):
                info['Time'] = pd.to_datetime(info['Time'])

            name = info['Name'].tolist() if isinstance(info['Name'], pd.Series) else info['Name']
            x = info['X'].tolist() if isinstance(info['X'], pd.Series) else info['X']
            y = info['Y'].tolist() if isinstance(info['Y'], pd.Series) else info['Y']
            z = info['Z'].tolist() if isinstance(info['Z'], pd.Series) else info['Z']
            t_tag = info['Time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').tolist()

            return name, x, y, z, t_tag
        else:
            print("Not connected to any device.")
            return None, None, None
        
    def move_rover(self, id_rover):
        self.start_connection(id_rover)
        movement_thread = threading.Thread(target=execute_movement, args=(id_rover,))
        movement_thread.start()

def main():
    rover_server = RoverServer()
    daemon = Pyro5.api.Daemon(host="192.168.50.8", port=9091)
    uri = daemon.register(rover_server, "rover_server")
    
    print(f"Server is running. Object URI: {uri}")
    daemon.requestLoop()

if __name__ == "__main__":
    main()
