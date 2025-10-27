import csv
import globals

def setup(outslug: str = "") -> None:
    outf = open("./output/" + outslug + "_findings.csv", "w")
    globals.csvwriter = csv.writer(outf)
