# rover.py
import Pyro5.api
from rover_interface import RoverInterface

@Pyro5.api.expose
class Rover(RoverInterface):
    
    def __init__(self, id: int):
        self.id = id
        self._peers = {}  # Dictionary to store references to other rovers

    def receive_message(self, message: str) -> None:
        print(f"Rover {self.id} received message: {message}")
    
    def send_message(self, message: str, target_id: int) -> None:
        if target_id in self._peers:
            peer = self._peers[target_id]
            peer.receive_message(message)
        else:
            print(f"Rover {self.id} does not know rover {target_id}")

    def add_peer(self, id: int, peer: RoverInterface) -> None:
        self._peers[id] = peer
