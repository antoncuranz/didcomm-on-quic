import os
import sys
from os import listdir
from os.path import isfile, join

import pandas as pd
import matplotlib.pyplot as plt

SAMPLE_SIZE = 50


def create_boxplot(path, files):
    data = {}

    for file in files:
        f = open(join(path, file), "r")
        lines = f.readlines()
        file = file[27:-4]
        data[file] = []

        for line in lines:
            line = line.rstrip()
            if line.startswith("BM(pres):"):
                time = line.split(";")[-1]
                data[file].append(float(time))

                if len(data[file]) == SAMPLE_SIZE:
                    break

    # print(data[file])
    data2 = [data[file[27:-4]] for file in files]
    bins = [x / 100.0 for x in range(100, 351, 25)]
    plt.hist(data2, bins=bins, density=True, histtype='bar', color=["red", "blue"], label=["http2", "http3"])
    plt.xticks(bins)
    plt.legend(prop={'size': 10})
    # df = pd.DataFrame(data)
    # df.hist(density=True, histtype='bar')
    # pd.DataFrame.hist(df)
    # return bp


def process(path):
    title = os.path.basename(os.path.normpath(path))
    plt.figure(title)
    plt.title("Time to request and verify presentation ({})".format(title))
    print("Processing {}".format(path))
    files = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith(".txt")]
    create_boxplot(path, files)
    # plt.savefig(join(path, title))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USAGE: {} <folder...>".format(sys.argv[0]))
        sys.exit(1)

    for path in sys.argv[1:]:
        process(path)

    plt.show()
