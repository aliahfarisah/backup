'''
rev 01 - Class UWB_USB to retrieve position data
'''

import serial
import time

class UwbUsbReader:
    def __init__(self, port, baudrate=115200, timeout=1):
        """
        Initializes the serial connection.
        Args:
            port (str): The port to connect to (e.g., 'COM3' or '/dev/ttyUSB0').
            baudrate (int, optional): The baudrate for the serial connection. Defaults to 9600.
            timeout (int, optional): The timeout for serial reads. Defaults to 1 second.
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = serial.Serial(port, baudrate, timeout=timeout)

    def activate_shell_mode(self):
        """
        Activate UART shell mode
        """
        for i in range(2):
            self.serial_connection.write(b'\r')
            time.sleep(0.2)
        print("Successfully entered UART Shell Mode...")

    def request_lec(self):
        """
        Activate UART shell mode
        """
        self.serial_connection.write(b'lec\r')
        #print("Sending COMMAND: LEC")

    def read_data(self):
        """
        Reads a line of data from the serial connection.
        Returns:
            str: The decoded line of data.
        """
        if self.serial_connection.inWaiting() > 0:  # Check if there is data waiting
            data = self.serial_connection.readline().decode('utf-8').strip()  # Read and decode
            return data
        return None

    def close(self):
        """Closes the serial connection."""
        if self.serial_connection.is_open:
            self.serial_connection.close()
            print("Serial connection closed.")

    def read_until_keyword(self, keyword):
        """
        Reads from the serial port until a specific keyword is found.
        Args:
            keyword (str): The keyword to search for.
        Returns:
            str: The line containing the keyword.
        """
        while True:
            data = self.read_data()
            if data and keyword in data:
                return data

# Example usage
if __name__ == "__main__":
    serial_port = "COM7"
    baud_rate = 115200
    reader = UwbUsbReader(serial_port)
    # Wait a moment for the connection to be established
    time.sleep(2)
    print(f"Connected to {serial_port} at baud rate {baud_rate}")

    #Activates shell mode
    reader.activate_shell_mode()
    time.sleep(1)

    pos_x, pos_y, pos_z = 0, 0, 0

    try:
        while True:
            data = reader.read_data()

            if data == "dwm>":
                reader.request_lec()
            elif data is None:
                continue

            #print("data:", data)
            data_split = data.split(",")
            if data_split[0] == "DIST":
                print("Data:", data_split)
                # Check if 'POS' exists in the data list
                if 'POS' in data_split:
                    # Find the index of 'POS'
                    pos_index = data_split.index('POS')
                    #print("Index:", pos_index)
                    
                    # Extract position data: X, Y, Z, and quality
                    pos_x = float(data_split[pos_index + 1])
                    pos_y = float(data_split[pos_index + 2])
                    pos_z = float(data_split[pos_index + 3])
                else:
                    pass
            
            print(f"X: {pos_x} meters, Y: {pos_y} meters, Z: {pos_z} meters")
                
    except KeyboardInterrupt:
        print("Process interrupted.")
    finally:
        # Close the connection
        reader.close()