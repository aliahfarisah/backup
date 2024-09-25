import Pyro5.api
import threading
import logging
from server import Server
from uwb import Uwb

# Configure logging to show only warnings and above
logging.basicConfig(level=logging.WARNING)

# Optionally configure specific loggers
bleak_logger = logging.getLogger('bleak')
bleak_logger.setLevel(logging.WARNING)

# Configure asyncio's logger specifically
asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.WARNING)

@Pyro5.api.expose

def start_daemon(class_instance, port, name):
    daemon = Pyro5.api.Daemon(host="192.168.50.141", port=port)
    uri = daemon.register(class_instance, name)
    print(f"{name} is running. Object URI: {uri}")
    return daemon

if __name__ == '__main__':
    base_path = "/home/pi/Desktop/rover"
    server_service = Server(base_path)
    uwb_service = Uwb()
    
    daemon_server = start_daemon(server_service, 9090, "server")
    daemon_uwb = start_daemon(uwb_service, 9091, "uwb")
    
    connect_thread = threading.Thread(target=uwb_service.start_connection, args=(5,))
    connect_thread.daemon = True
    connect_thread.start()
    
    server_thread = threading.Thread(target=daemon_server.requestLoop)
    server_thread.start()
    
    uwb_thread = threading.Thread(target=daemon_uwb.requestLoop)
    uwb_thread.start()