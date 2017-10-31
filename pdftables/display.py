"""display.py

This module displays the results of the table extraction in the terminal.

"""

from collections import defaultdict
from io import StringIO

def to_string(table):
    """
    Returns a list of the maximum width for each column across all rows
    type(to_string([['foo', 'goodbye'], ['llama', 'bar']]))
    """
    result = StringIO()

    (columns, rows) = get_dimensions(table)

    result.write("     {} columns, {} rows\n".format(columns, rows))
    col_widths = find_column_widths(table)
    table_width = sum(col_widths) + len(col_widths) + 2
    hbar = '    {}\n'.format('-' * table_width)

    try:
        result.write("      {}\n".format(' '.join(
            [unicode(col_index).rjust(width, ' ') for (col_index, width)
             in enumerate(col_widths)])))
    except NameError:
        result.write("      {}\n".format(' '.join(
            [str(col_index).rjust(width, ' ') for (col_index, width)
             in enumerate(col_widths)])))

    result.write(hbar)
    for row_index, row in enumerate(table):
        try:
            cells = [unicode(cell).rjust(width, ' ') for (cell, width) in zip(row, col_widths)]
            result.write("{:>3} | {}|\n".format(row_index, '|'.join(cells).encode('utf-8')))
        except NameError:
            cells = [str(cell).rjust(width, ' ') for (cell, width) in zip(row, col_widths)]
            result.write("{:>3} | {}|\n".format(row_index, '|'.join(cells)))

    result.write(hbar)
    result.seek(0)
    read_result = result.read()

    try:
        return unicode(read_result)
    except NameError:
        return str(read_result)


def get_dimensions(table):
    """
    Returns columns, rows for a table.
    get_dimensions([['row1', 'apple', 'llama'], ['row2', 'plum', 'goat']])
    (3, 2)

    get_dimensions([['row1', 'apple', 'llama'], ['row2', 'banana']])
    (3, 2)
    """
    rows = len(table)
    try:
        cols = max(len(list(row)) for row in table)
    except ValueError:
        cols = 0
    return (cols, rows)


def find_column_widths(table):
    """
    Returns a list of the maximum width for each column across all rows
    find_column_widths([['foo', 'goodbye'], ['llama', 'bar']])
    [5, 7]
    """
    col_widths = defaultdict(lambda: 0)
    for row in table:
        for column_index, cell in enumerate(row):
            col_widths[column_index] = max(col_widths[column_index], len(cell))
    return [col_widths[col] for col in sorted(col_widths)]
