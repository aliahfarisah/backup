import Pyro5.api
import threading
import time
import pandas as pd
from ble_manager import BLEDeviceManager

@Pyro5.api.expose
class RoverServer:
    def __init__(self):
        self.device_manager = BLEDeviceManager()
        self.device_manager.stop_event = threading.Event()
        self.connection_lock = threading.Lock()

    def start_connection(self, id_rover):   
        self.device_manager.start_connection(id_rover)

    def get_coordinates(self):
        if self.device_manager.is_connected():
            info = self.device_manager.get_device_info()
            
            if not pd.api.types.is_datetime64_any_dtype(info['Time']):
                info['Time'] = pd.to_datetime(info['Time'])

            # Convert pandas Series to lists or scalars
            name = info['Name'].tolist() if isinstance(info['Name'], pd.Series) else info['Name']
            x = info['X'].tolist() if isinstance(info['X'], pd.Series) else info['X']
            y = info['Y'].tolist() if isinstance(info['Y'], pd.Series) else info['Y']
            z = info['Z'].tolist() if isinstance(info['Z'], pd.Series) else info['Z']
            t_tag = info['Time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').tolist()
            status = info['Status'].tolist() if isinstance(info['Status'], pd.Series) else info['Status']

            return name, x, y, z, t_tag, status
        else:
            return None, None, None, None, None, None
        
def main():
    rover_server = RoverServer()
    daemon = Pyro5.api.Daemon(host="192.168.50.251", port=9091)
    uri = daemon.register(rover_server, "rover_server")
    
    thread = threading.Thread(target=rover_server.start_connection, args=(3,))
    thread.daemon = True
    thread.start()
    
    print(f"Server is running. Object URI: {uri}")
    daemon.requestLoop()
    
    

if __name__ == "__main__":
    main()
