"""
process_failures.py

Reads failure_records.csv, converts the 'failure_timestamp' column
(format: YYYY-MM-DDTHH:MM:SS) into two new columns:

    date         -> DD-MM-YYYY
    day_of_week  -> Monday, Tuesday, ... Sunday
    time_of_day  -> morning / afternoon / evening / night

Usage:
    python process_failures.py [input_csv] [output_csv]

If no arguments are given, it defaults to:
    input_csv  = failure_records.csv
    output_csv = failure_records_processed.csv
"""

import sys
import csv
import os
from datetime import datetime


def classify_time_of_day(hour: int) -> str:
    """Return the time-of-day bucket for a given hour (0-23)."""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:  # 21:00 - 04:59
        return "night"


def resolve_input_path(input_path: str) -> str:
    """
    Find the input file whether the script is run from VSCode, a GitHub
    Codespace/clone, or Google Colab -- these environments often have
    different working directories.

    Tries, in order:
        1. The path as given (relative to the current working directory)
        2. The same filename next to this script
        3. (Colab only) /content/<filename>, the default upload location
    """
    if os.path.isfile(input_path):
        return input_path

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(script_dir, os.path.basename(input_path))
    if os.path.isfile(candidate):
        return candidate

    colab_candidate = os.path.join("/content", os.path.basename(input_path))
    if os.path.isfile(colab_candidate):
        return colab_candidate

    raise FileNotFoundError(
        f"Could not find '{input_path}'. Checked the current working "
        f"directory ('{os.getcwd()}'), the script's folder "
        f"('{script_dir}'), and '/content' (Colab default). "
        "Either place the CSV in one of these locations, or pass its "
        "full path as the first argument, e.g.\n"
        "    python process_failures.py /full/path/to/failure_records.csv"
    )


def open_csv_for_read(path: str):
    """
    Open a CSV for reading, tolerant of the encoding quirks that most often
    trip this up across environments: a UTF-8 byte-order-mark (common when
    a file was saved from Excel on Windows) or a non-UTF-8 Windows encoding.
    Falls back through encodings and raises a clear error if all fail.
    """
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            f = open(path, newline="", encoding=encoding)
            f.read(1024)  # force a decode check now, not lazily later
            f.seek(0)
            return f
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(
        "utf-8-sig", b"", 0, 1,
        f"Could not decode '{path}' as utf-8-sig, cp1252, or latin-1. "
        "Try re-saving the file with 'UTF-8' encoding."
    )


def process_file(input_path: str, output_path: str) -> None:
    input_path = resolve_input_path(input_path)
    infile = open_csv_for_read(input_path)
    with infile:
        reader = csv.DictReader(infile)

        if "failure_timestamp" not in reader.fieldnames:
            raise ValueError(
                f"Column 'failure_timestamp' not found. "
                f"Available columns: {reader.fieldnames}"
            )

        # Build output fieldnames: replace failure_timestamp with date + time_of_day,
        # keeping all other original columns in place.
        fieldnames = []
        for col in reader.fieldnames:
            if col == "failure_timestamp":
                fieldnames.extend(["date", "day_of_week", "time_of_day"])
            else:
                fieldnames.append(col)

        rows_out = []
        errors = 0

        for i, row in enumerate(reader, start=2):  # start=2 accounts for header row
            raw_ts = row.pop("failure_timestamp", "")
            try:
                ts = datetime.strptime(raw_ts.strip(), "%Y-%m-%dT%H:%M:%S")
                row["date"] = ts.strftime("%d-%m-%Y")
                row["day_of_week"] = ts.strftime("%A")
                row["time_of_day"] = classify_time_of_day(ts.hour)
            except (ValueError, AttributeError):
                print(f"Warning: row {i} has unparseable timestamp: {raw_ts!r}")
                row["date"] = ""
                row["day_of_week"] = ""
                row["time_of_day"] = ""
                errors += 1

            rows_out.append(row)

    with open(output_path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Done. Wrote {len(rows_out)} rows to '{output_path}'.")
    if errors:
        print(f"{errors} row(s) had timestamps that could not be parsed.")


if __name__ == "__main__":
    input_csv = sys.argv[1] if len(sys.argv) > 1 else "failure_records.csv"
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "failure_records_processed.csv"
    try:
        process_file(input_csv, output_csv)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)