import sys
import re
from os import listdir
from os.path import isfile, join

import pandas as pd
import matplotlib.pyplot as plt

FIRST_CHUNK = 1


def print_latex(files, bp):
    outliers = [flier.get_ydata() for flier in bp["fliers"]]
    boxes = [box.get_ydata() for box in bp["boxes"]]
    medians = [median.get_ydata() for median in bp["medians"]]
    whiskers = [whiskers.get_ydata() for whiskers in bp["whiskers"]]

    for i, file in enumerate(files):
        fill = "blue" if "http3" in file else "red"
        position = 1.2 if "http3" in file else 0.8
        latex = """
\\addplot+[
fill={},
draw=black,
boxplot prepared={{
    draw position={},
    lower whisker={},
    lower quartile={},
    median={},
    upper quartile={},
    upper whisker={}
}},
] coordinates {{}};
% ] coordinates {{{}}};
            """.format(fill, position, whiskers[i * 2][1], boxes[i][1], medians[i][1], boxes[i][2], whiskers[i * 2 + 1][1],
                       " ".join(["(0,{})".format(str(o)) for o in outliers[i]]))
        print(latex)


def process(path):
    plt.figure(path)
    plt.title("Time to retrieve DASH segment ({})".format(path))
    print("Processing {}".format(path))
    files = [f for f in listdir(path) if isfile(join(path, f))]
    data = {}

    for file in files:
        f = open(join(path, file), "r")
        lines = f.readlines()
        file = file[27:-4]
        data[file] = []

        for line in lines:
            line = line.rstrip()
            if line.startswith("BM(chunk):"):
                chunk = re.search(r"(\d+|init).(?:m4s|mp4)", line).group(1)
                if chunk == "init" or int(chunk) < FIRST_CHUNK:
                    continue
                time = line.split(";")[-1]
                data[file].append(float(time))

    df = pd.DataFrame(data)
    _, bp = pd.DataFrame.boxplot(df, return_type='both')

    print_latex(files, bp)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USAGE: {} <folder...>".format(sys.argv[0]))
        sys.exit(1)

    for path in sys.argv[1:]:
        process(path)

    plt.show()
