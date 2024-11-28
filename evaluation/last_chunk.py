import shutil
import sys
from os import listdir
from os.path import isfile, join

prefix = "Requesting stream from connection"

def process(path):
    files = [join(path, f) for f in listdir(path) if isfile(join(path, f)) and f.endswith(".txt")]
    for file in files:
        print(file)
        backup_file = file + '.bak'
        shutil.move(file, backup_file)
        print(f"Backup of the original file created: {backup_file}")
        
        last_occurrence = 0
        with open(backup_file, 'r') as infile:
            for line_number, line in enumerate(infile):
                if line.startswith(prefix):
                    last_occurrence = line_number

        with open(backup_file, 'r') as infile, open(file, 'w') as outfile:
            for line_number, line in enumerate(infile):
                if line_number >= last_occurrence:
                    outfile.write(line)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USAGE: {} <folder...>".format(sys.argv[0]))
        sys.exit(1)

    for path in sys.argv[1:]:
        process(path)
