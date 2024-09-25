import asyncio
import Pyro5.api
from ble_manager import BLEDeviceManager

class BLEDeviceManagerServer:
    def __init__(self):
        self.device_manager = BLEDeviceManager()
        self.connection_task = None

    @Pyro5.api.expose
    def start(self, id_rover):
        if not self.connection_task:
            print(f"Starting BLEDeviceManager for rover ID: {id_rover}")
            self.connection_task = asyncio.create_task(self.device_manager.start_connection(id_rover))
        else:
            print("BLEDeviceManager is already running")

    @Pyro5.api.expose
    def stop(self):
        if self.connection_task:
            print("Stopping BLEDeviceManager...")
            self.connection_task.cancel()
            self.connection_task = None
        else:
            print("BLEDeviceManager is not running")

if __name__ == "__main__":
    ble_service = BLEDeviceManagerServer()
    daemon= Pyro5.api.Daemon(host="192.168.50.156", port=9093)
    uri_time = daemon.register(ble_service, "ble")
    print(uri_time)
    print("TimeService is ready")
    daemon.requestLoop()