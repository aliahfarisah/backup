import Pyro5.api

# Import the movement logic here
import uwb_movement_rev05

# Expose the RoverController class with Pyro5
@Pyro5.api.expose
class RoverController:
    def __init__(self):
        pass

    def start_movement(self, id_rover):
        uwb_movement_rev05.start_rover(id_rover)

if __name__ == "__main__":
    move = RoverController()
    daemon = Pyro5.api.Daemon(host="192.168.50.52", port=9093)
    uri = daemon.register(move, "move")
    print("Rover controller is ready.")
    daemon.requestLoop()

