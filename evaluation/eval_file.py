import os
import sys
from os import listdir
from os.path import isfile, join

import pandas as pd
import matplotlib.pyplot as plt

SAMPLE_SIZE = 100


def create_boxplot(path, files):
    data = {}

    for file in files:
        f = open(join(path, file), "r")
        lines = f.readlines()
        file = file[27:-4]
        data[file] = []

        skip = True

        for line in lines:
            line = line.rstrip()
            if line.startswith("BM(file):"):
                if skip:
                    skip = False
                    continue

                time = line.split(";")[-1]
                data[file].append(float(time))

                if len(data[file]) == SAMPLE_SIZE:
                    break

    df = pd.DataFrame(data)
    _, bp = pd.DataFrame.boxplot(df, return_type='both')
    return bp


def process(path):
    title = os.path.basename(os.path.normpath(path))
    plt.figure(title)
    plt.title("Time to establish connection ({})".format(title))
    print("Processing {}".format(path))
    files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith(".txt")]
    create_boxplot(path, files)
    plt.savefig(join(path, title))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USAGE: {} <folder...>".format(sys.argv[0]))
        sys.exit(1)

    for path in sys.argv[1:]:
        process(path)

    # plt.show()
