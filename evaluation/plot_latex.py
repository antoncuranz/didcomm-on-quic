import os
import sys
from os import listdir
from os.path import isfile, join, isdir

from eval_conn import create_boxplot as create_boxplot_conn
from eval_chunk import create_boxplot as create_boxplot_chunk
from eval_pres import create_boxplot as create_boxplot_pres
from eval_file import create_boxplot as create_boxplot_file

LATEX_PRE = \
"""\\documentclass[tikz]{{standalone}}

\\usepackage{{pgfplots}}
\\pgfplotsset{{compat = newest}}
\\usepgfplotslibrary{{statistics}}

\\begin{{document}}
\\begin{{tikzpicture}}

\\definecolor{{red}}{{RGB}}{{219,58,52}}
\\definecolor{{blue}}{{RGB}}{{23,126,137}}

\\begin{{axis}}
[
    %title={{{}}},
    xlabel={{TODO}},
    ylabel={{time in seconds}},
    yticklabel style={{text width=8mm,align=right}},
    xtick={{{}}},
    xticklabels={{{}}},
    %ymin=0.1,
    %ytick distance=0.05,
    %ymax=0.6,
    boxplot/box extend=0.35,
    boxplot/draw direction=y,
    area legend,
    legend entries={{http1, http3}},
    legend pos=north west,
    ymajorgrids = true,
    yminorgrids = true,
    major grid style = {{lightgray}},
    minor grid style = {{lightgray!25}},
    width = 15cm,
    height = 11.5cm,
]

% START PLOTS
"""

LATEX_PLOT = """
\\addplot+[
fill={},
draw=black,
solid,
mark=asterisk,
boxplot prepared={{
    draw position={},
    lower whisker={},
    lower quartile={},
    median={},
    upper quartile={},
    upper whisker={}
}},
% ] coordinates {{}};
] coordinates {{{}}};"""

LATEX_POST = \
"""
% END PLOTS

\\end{axis}
\\end{tikzpicture}
\\end{document}"""


TYPES = {
    "conn": {
        "title": "Time to establish DIDComm connection ({})",
        "bpf": create_boxplot_conn
    },
    "chunk": {
        "title": "DASH segment transmission time ({})",
        "bpf": create_boxplot_chunk
    },
    "pres": {
        "title": "Time to request and verify presentation (batched) ({})",
        "bpf": create_boxplot_pres
    },
    "file": {
        "title": "File transmission time ({})",
        "bpf": create_boxplot_file
    }
}


def process_subdir(files, bp, drawpos, outfile):
    outliers = [flier.get_ydata() for flier in bp["fliers"]]
    boxes = [box.get_ydata() for box in bp["boxes"]]
    medians = [median.get_ydata() for median in bp["medians"]]
    whiskers = [whiskers.get_ydata() for whiskers in bp["whiskers"]]

    if len(files) != 2:
        print("Error: folder must contain 2 files")
        sys.exit(1)

    for i, file in enumerate(files):
        fill = "blue" if "http3" in file else "red"
        position = drawpos + .2 if "http3" in file else drawpos - .2
        latex = LATEX_PLOT.format(fill, position, whiskers[i * 2][1], boxes[i][1], medians[i][1], boxes[i][2],
                                  whiskers[i * 2 + 1][1], " ".join(["(0,{})".format(str(o)) for o in outliers[i]]))
        outfile.write(latex)


def process_dir(path, type, outfile):
    folders = [f for f in listdir(path) if isdir(join(path, f))]
    folders.sort()
    common_prefix = os.path.commonprefix(folders)
    
    title = TYPES[type]["title"].format(path)

    latex = LATEX_PRE.format(title, ",".join([str(i) for i in range(1, len(folders) + 1)]),
                             ",".join([f.removeprefix(common_prefix) for f in folders]))
    outfile.write(latex)

    for i, folder in enumerate(folders, start=1):
        files = [f for f in listdir(join(path, folder)) if isfile(join(path, folder, f)) and f.endswith(".txt")]
        files.sort(key=lambda fn: "http3" in fn)

        bp = TYPES[type]["bpf"](join(path, folder), files)
        process_subdir(files, bp, i, outfile)

    outfile.write(LATEX_POST)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in TYPES.keys():
        print("USAGE: {} <folder> <{}>".format(sys.argv[0], "|".join(TYPES.keys())))
        sys.exit(1)

    outfilename = join(sys.argv[1], "{}-{}.tex".format(sys.argv[1].replace("/", "-"), sys.argv[2]))
    with open(outfilename, "w") as outfile:
        process_dir(sys.argv[1], sys.argv[2], outfile)
