import Pyro5.api
import threading
import uwb_movement_rev05b

# Expose the RoverController class with Pyro5
@Pyro5.api.expose
class RoverController:
    def __init__(self):
        self.movement_trigger_event = threading.Event()  # Event to control start trigger

    def start_movement(self, id_rover):
        self.movement_trigger_event.clear()
        # Run the movement logic in a separate thread so the server remains responsive
        movement_thread = threading.Thread(target=self.run_movement_logic, args=(id_rover,))
        movement_thread.start()

    def run_movement_logic(self, id_rover):
        """Internal function that runs the movement and waits for a signal from the client to start."""
        print(f"Rover {id_rover} waiting for movement start command...")
        uwb_movement_rev05b.start_rover(id_rover)
        if self.movement_trigger_event.is_set():
            print("Event is already set, starting movement")
        else:
            print(f"Rover {id_rover} waiting for the 'go' signal")
        self.movement_trigger_event.wait()  # Wait until the client sends the "go" command
        print(f"Rover {id_rover} received the start command, beginning movement...")
        uwb_movement_rev05b.start_movement(id_rover)  # Now call the movement function after the trigger

    def trigger_start(self):
        """This will be called by the client to signal the rover to start moving."""
        print("Movement start command received.")
        self.movement_trigger_event.set()  # Trigger the event to start the movement
        print("Movement event set. The rover should now start moving")

if __name__ == "__main__":
    move = RoverController()
    daemon = Pyro5.api.Daemon(host="192.168.50.215", port=9093)
    uri = daemon.register(move, "move")
    print(f"Rover controller is ready. URI: {uri}")
    daemon.requestLoop()
