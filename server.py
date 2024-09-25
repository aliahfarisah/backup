import csv
import datetime
import os
import pickle
import base64
import logging
import select
import Pyro5.api

logging.basicConfig(level=logging.DEBUG)

# CombinedService class
@Pyro5.api.expose
class Server:
    def __init__(self, base_path):
        self.base_path = base_path

    def check_identity(self, id_database):
        try:
            with open('identity.csv', 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    id_rover = row['ID'].strip()
                    if id_rover == id_database:
                        print(id_rover)  # Print the ID when found
                        return 0
                print("ID not found in the CSV file.")
                return 1
        except FileNotFoundError:
            print("identity.csv file not found.")
            return 2

    def get_server_time(self):
        return datetime.datetime.now().strftime("%H:%M:%S %p")

    def get_file_list(self):
        files = []
        for filename in os.listdir(self.base_path):
            #if filename.endswith(".csv"):
            files.append(filename)
        return sorted(files)

    def upload_file(self, filename, data):
        try:
            decoded_data = base64.b64decode(data['data'])
            file_data = pickle.loads(decoded_data)
            file_path = os.path.join(self.base_path, filename)
            with open(file_path, 'wb') as f:
                f.write(file_data)
            return f"File '{filename}' uploaded successfully."
        except Exception as e:
            return f"Error uploading file '{filename}': {e}"
        
    def download_file(self, filename):
        try:
            file_path = os.path.join(self.base_path, filename)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                encoded_data = base64.b64encode(pickle.dumps(file_data)).decode('utf-8')
                return {"filename": filename, "data": encoded_data}
            else:
                return {"error": "File not found"}
        except Exception as e:
            return {"error": str(e)}

    def get_file_metadata(self, filename):
        try:
            file_path = os.path.join(self.base_path, filename)
            if os.path.exists(file_path):
                file_mtime = os.path.getmtime(file_path)
                file_date_time = datetime.datetime.fromtimestamp(file_mtime)
                file_date = file_date_time.strftime("%Y-%m-%d")
                file_time = file_date_time.strftime("%H:%M:%S")
                return {
                    "date": file_date,
                    "time": file_time
                }
            else:
                return {"error": "File not found"}
        except Exception as e:
            return {"error": str(e)}

if __name__ == '__main__':
    base_path = "/home/pi/Desktop/lightShow"
    rover_service = Server(base_path)
    daemon = Pyro5.api.Daemon(host="192.168.50.141", port=9090)
    uri = daemon.register(rover_service, "rover")
    print(uri)
    print("Rover is ready")

    try:
        while True:
            daemon.requestLoop()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        daemon.close()
