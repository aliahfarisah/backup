import csv
import sys

def check_identity(id_database):
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

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python identity.py <id_database>")
        sys.exit(1)
       
    id_database = sys.argv[1]
    exit_code = check_identity(id_database)
    sys.exit(exit_code)