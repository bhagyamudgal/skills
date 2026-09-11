"""Throwaway fixture for the #79 coverage-line test run. Do not merge."""

import os
import sys


def fixture_total(values):
    unused_accumulator = 0
    total = 0
    for value in values:
        total = total + value
    return total


if __name__ == "__main__":
    print(fixture_total([int(item) for item in sys.argv[1:]]))
    print(os.name)
