#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ScraperWiki Limited
# Ian Hopkinson, 2013-06-04
"""
Some experiments with pdfminer
http://www.unixuser.org/~euske/python/pdfminer/programming.html
Some help here:
http://denis.papathanasiou.org/2010/08/04/extracting-text-images-from-pdf-files
"""

import argparse
import math
import numpy

from display import to_string
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams, LTPage
from pdfminer.converter import PDFPageAggregator

from tree import Leaf, LeafList
from counter import Counter

IS_TABLE_COLUMN_COUNT_THRESHOLD = 3
IS_TABLE_ROW_COUNT_THRESHOLD = 3
LEFT = 0
TOP = 3
RIGHT = 2
BOTTOM = 1

class Table(list):
    """ Hold a table definition """
    def __init__(self, content, page, table):
        super(Table, self).__init__(content)
        self.page_number = page["page"]
        self.total_pages = page["page_total"]
        self.table_number_on_page = table["table_index"]
        self.total_tables_on_page = table["table_index_total"]

def get_tables(file_location, password):
    """
    Return a list of 'tables' from the given file handle, where a table is a
    list of rows, and a row is a list of strings.
    """
    result = []
    doc, interpreter, device = initialize_pdf_miner(file_location, password)
    pages = [page for page in PDFPage.create_pages(doc)]
    doc_length = len(pages)
    for i, pdf_page in enumerate(pages):
        if not page_contains_tables(pdf_page, interpreter, device):
            continue

        # receive the LTPage object for the page.
        interpreter.process_page(pdf_page)
        processed_page = device.get_result()
        table = page_to_tables(processed_page, extend_y=True, hints=[], atomise=True)
        crop_table(table)
        result.append(
            Table(
                table,
                {
                    "page": i+1,
                    "page_total":doc_length
                },
                {
                    "table_index": 1,
                    "table_index_total": 1
                }
            )
        )

    return result


def crop_table(table):
    """
    Remove empty rows from the top and bottom of the table.
    """
    for row in list(table):  # top -> bottom
        if not any(cell.strip() for cell in row):
            table.remove(row)
        else:
            break

    for row in list(reversed(table)):  # bottom -> top
        if not any(cell.strip() for cell in row):
            table.remove(row)
        else:
            break


def initialize_pdf_miner(file_location, password=""):
    """ Setup PDF Miner """
    # Create a PDF parser object associated with the file object.
    pdf_parser = PDFParser(file_location)
    # Supply the password for initialization.
    # (If no password is set, give an empty string.)
    # Create a PDF document object that stores the document structure.
    doc = PDFDocument(pdf_parser, password)
    # Connect the parser and document objects.
    pdf_parser.set_document(doc)
    # Check if the document allows text extraction. If not, abort.
    if not doc.is_extractable:
        raise ValueError("PDFDocument is_extractable was False.")
    # Create a PDF resource manager object that stores shared resources.
    rsrcmgr = PDFResourceManager()
    # Create a PDF device object.
    device = PDFDevice(rsrcmgr)
    # Create a PDF interpreter object.
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    # Process each page contained in the document.
    # for page in doc.get_pages():
    #    interpreter.process_page(page)

    # Set parameters for analysis.
    laparams = LAParams()
    laparams.word_margin = 0.0
    # Create a PDF page aggregator object.
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    return doc, interpreter, device

def page_contains_tables(pdf_page, interpreter, device):
    """ check if page contains table """
    interpreter.process_page(pdf_page)
    # receive the LTPage object for the page.
    layout = device.get_result()
    box_list = LeafList().populate(layout)
    """
    for item in box_list:
        assert isinstance(item, Leaf), "NOT LEAF"
    """
    yhist = box_list.histogram(Leaf.top).rounder(1)
    test = [k for k, v in yhist.items() if v > IS_TABLE_COLUMN_COUNT_THRESHOLD]
    return len(test) > IS_TABLE_ROW_COUNT_THRESHOLD


def threshold_above(hist, threshold_value):
    """
    threshold_above(Counter({518: 10, 520: 20, 530: 20, \
                            525: 17}), 15)
    [520, 530, 525]
    """
    if not isinstance(hist, Counter):
        raise ValueError("requires Counter")  # TypeError then?

    above = [k for k, v in hist.items() if v > threshold_value]
    return above


def comb(combarray, value):
    """
    Takes a sorted array and returns the interval number of the value passed to
    the function
    """
    # Raise an error in combarray not sorted
    if (combarray != sorted(combarray)) and (combarray != sorted(
            combarray, reverse=True)):
        raise Exception("comb: combarray is not sorted")

    index = -1
    if combarray[0] > combarray[-1]:
        for i in range(1, len(combarray)):
            if combarray[i - 1] >= value >= combarray[i]:
                index = i - 1
    else:
        for i in range(1, len(combarray)):
            if combarray[i - 1] <= value <= combarray[i]:
                index = i - 1

    return index


def apply_combs(box_list, x_comb, y_comb):
    """Allocates text to table cells using the x and y combs"""
    ncolumns = len(x_comb) - 1
    nrows = len(y_comb) - 1
    table_array = [[''] * ncolumns for j in range(nrows)]
    for box in box_list:
        rowindex = comb(y_comb, round(box.midline()))
        columnindex = comb(x_comb, round(box.centreline()))
        if rowindex != -1 and columnindex != -1:
            # there was already some content at this coordinate so we
            # concatenate (in an arbitrary order!)
            table_array[rowindex][columnindex] += box.text.rstrip('\n\r')

    return table_array


def comb_from_projection(projection, threshold, orientation):
    """Calculates the boundaries between cells from the projection of the boxes
    onto either the y axis (for rows) or the x-axis (for columns). These
    boundaries are known as the comb
    """
    if orientation == "row":
        tol = 1
    elif orientation == "column":
        tol = 3

    projection_threshold = threshold_above(projection, threshold)

    projection_threshold = sorted(projection_threshold)
    # need to generate a list of uppers (right or top edges)
    # and a list of lowers (left or bottom edges)

    # uppers = [k for k, v in yhisttop.items() if v > yThreshold]
    # lowers = [k for k, v in yhistbottom.items() if v > yThreshold]
    uppers = []
    lowers = []

    lowers.append(projection_threshold[0])
    for i in range(1, len(projection_threshold)):
        if projection_threshold[i] > (
                projection_threshold[i-1] + 1):
            uppers.append(projection_threshold[i - 1])
            lowers.append(projection_threshold[i])
    uppers.append(projection_threshold[-1])

    comb_over = comb_from_uppers_and_lowers(uppers, lowers, tol=tol,
                                            projection=projection)
    comb_over.reverse()

    return comb_over


def comb_from_uppers_and_lowers(uppers, lowers, tol=1, projection=None):
    """Called by comb_from_projection to calculate the comb given a set of
    uppers and lowers, which are upper and lower edges of the thresholded
    projection"""
    # tol is a tolerance to remove very small minima, increasing to 2 fowls up
    # row separation
    if projection is None:
        projection = {}

    assert len(uppers) == len(lowers)
    uppers.sort(reverse=True)
    lowers.sort(reverse=True)
    comb_under = []
    comb_under.append(uppers[0])
    for i in range(1, len(uppers)):
        if (lowers[i - 1] - uppers[i]) > tol:
            comb_under.append(find_minima(lowers[i - 1], uppers[i], projection))

    comb_under.append(lowers[-1])

    return comb_under

def find_minima(lower, upper, projection=None):
    """ find the the median """
    if projection is None:
        projection = {}

    if projection == {}:
        idx = (lower + upper) / 2.0
    else:
        profile = []
        for i in range(upper, lower):
            profile.append(projection[i])

        _, idx = min((val, idx) for (idx, val) in enumerate(profile))
        idx = upper + idx

    return idx

def comb_extend(comb_left, minv, maxv):
    """Extend the comb to minv and maxv"""
    # Find sort order of comb_left, convert to ascending
    is_reversed = False
    if comb_left[0] > comb_left[-1]:
        comb_left.reverse()
        is_reversed = True
    # Find min and max of comb
    minc = comb_left[0]
    maxc = comb_left[-1]
    # Get average row spacing
    row_spacing = numpy.average(numpy.diff(comb_left))
    # Extend minimum
    if minv < minc:
        comb_left.reverse()
        comb_left.extend(list(numpy.arange(minc, minv, (row_spacing * -1)))[1:])
        comb_left.reverse()
    # Extend maximum
    if maxv > maxc:
        comb_left.extend(list(numpy.arange(maxc, maxv, row_spacing))[1:])

    if is_reversed:
        comb_left.reverse()

    return comb_left

def project_boxes(box_list, orientation, erosion=0):
    """
    Take a set of boxes and project their extent onto an axis
    """
    if orientation == "column":
        upper = RIGHT
        lower = LEFT
    elif orientation == "row":
        upper = TOP
        lower = BOTTOM

    projection = {}
    # ensure some overlap
    minv = round(min([box.bbox[lower] for box in box_list])) - 2
    maxv = round(max([box.bbox[upper] for box in box_list])) + 2

    # Initialise projection structure
    coords = range(int(minv), int(maxv))
    projection = list(coords)

    for box in box_list:
        for i in range(int(round(box.bbox[lower])) + erosion,
                       int(round(box.bbox[upper])) - erosion):
            projection.append(i)

    return Counter(projection)

def get_min_and_max_y_from_hints(box_list, top_string, bottom_string):
    """ Get min and max from hints """
    miny = None
    maxy = None
    if top_string:
        top_box = [box for box in box_list if top_string in box.text]
        if top_box:
            maxy = top_box[0].top
    if bottom_string:
        bottom_box = [box for box in box_list if bottom_string in box.text]
        if bottom_box:
            miny = bottom_box[0].bottom
    return miny, maxy

def init_comb(row_projection, column_projection, minx, maxx):
    """ init our x and y comb for page_to_tables """
    # For LTTextLine horizontal column and row thresholds of 3 work ok
    column_threshold = 5
    row_threshold = 3

    y_comb = comb_from_projection(row_projection, row_threshold, "row")
    y_comb.reverse()

    # column_threshold = max(len(y_comb)*0.75,5)
    x_comb = comb_from_projection(column_projection, column_threshold, "column")

    x_comb[0] = minx
    x_comb[-1] = maxx

    return x_comb, y_comb

def apply_the_combs(box_list, x_comb, y_comb, atomise):
    """ Applying the combs """
    table_array = apply_combs(box_list, x_comb, y_comb)
    # Strip out leading and trailing spaces when atomise true
    if atomise:
        tmp_table = []
        for row in table_array:
            stripped_row = [r.strip() for r in row]
            tmp_table.append(stripped_row)
        table_array = tmp_table
    return table_array

def get_projection(leaf, box_list, min_max_y, min_max_x):
    """ get row and column projection """
    filtered_box_list = filter_box_list_by_position(
        filter_box_list_by_position(
            box_list,
            min_max_y["min"],
            min_max_y["max"],
            leaf.midline),
        min_max_x["min"],
        min_max_x["max"],
        leaf.centreline)

    # Project boxes onto horizontal axis
    column_projection = project_boxes(filtered_box_list, "column")

    # Project boxes onto vertical axis
    # Erode row height by a fraction of the modal text box height
    erodelevel = int(math.floor(calculate_modal_height(filtered_box_list) / 4))
    row_projection = project_boxes(filtered_box_list, "row", erosion=erodelevel)
    return row_projection, column_projection

def page_to_tables(page, extend_y=False, hints=None, atomise=False):
    """
    Get a rectangular list of list of strings from one page of a document
    """
    if not isinstance(page, LTPage):
        raise TypeError("page must be LTPage, not {}".format(page.__class__))

    if atomise:
        flt = ['LTPage', 'LTTextLineHorizontal', 'LTChar']
    else:
        flt = ['LTPage', 'LTTextLineHorizontal']
    box_list = LeafList().populate(page, flt).purge_empty_text()

    (minx, maxx, miny, maxy) = find_table_bounding_box(box_list, hints=hints)

    # If miny and maxy are None then we found no tables and should exit
    if miny is None and maxy is None:
        return list([])

    if atomise:
        box_list = box_list.filter_by_type(['LTPage', 'LTChar'])

    row_projection, column_projection = get_projection(
        Leaf,
        box_list,
        {"min": miny, "max": maxy},
        {"min": minx, "max": maxx})

    x_comb, y_comb = init_comb(row_projection, column_projection, minx, maxx)
    # Extend y_comb to page size if extend_y is true
    if extend_y:
        y_comb = comb_extend(
            y_comb,
            min([box.bottom() for box in box_list]),
            max([box.top() for box in box_list]))

    return apply_the_combs(box_list, x_comb, y_comb, atomise)

def find_table_bounding_box(box_list, hints=None):
    """ Returns one bounding box (minx, maxx, miny, maxy) for tables based
    on a boxlist
    """

    miny = min([box.bottom() for box in box_list])
    maxy = max([box.top() for box in box_list])
    minx = min([box.left() for box in box_list])
    maxx = max([box.right() for box in box_list])

    # Get rid of LTChar for this stage
    text_line_boxlist = box_list.filter_by_type('LTTextLineHorizontal')

    # Try to reduce the y range with a threshold, wouldn't work for x"""
    yhisttop = text_line_boxlist.histogram(Leaf.top).rounder(2)
    yhistbottom = text_line_boxlist.histogram(Leaf.bottom).rounder(2)

    try:
        miny = min(threshold_above(yhistbottom, IS_TABLE_COLUMN_COUNT_THRESHOLD))
    # and the top of the top cell
        maxy = max(threshold_above(yhisttop, IS_TABLE_COLUMN_COUNT_THRESHOLD))
    except ValueError:
        # Value errors raised when min and/or max fed empty lists
        miny = None
        maxy = None
        #raise ValueError("table_threshold caught nothing")

    # The table miny and maxy can be modified by hints
    if hints:
        top_string = hints[0]  # "% Change"
        bottom_string = hints[1]  # "15.67%"
        hintedminy, hintedmaxy = get_min_and_max_y_from_hints(
            text_line_boxlist, top_string, bottom_string)
        if hintedminy:
            miny = hintedminy
        if hintedmaxy:
            maxy = hintedmaxy
    # Modify table minx and maxx with hints?

    return (minx, maxx, miny, maxy)

def filter_box_list_by_position(box_list, minv, maxv, dir_fun):
    """ filter the box by it's position """
    filtered_box_list = LeafList()
    for box in box_list:
        # box = boxstruct[0]
        if dir_fun(box) >= minv and dir_fun(box) <= maxv:
            filtered_box_list.append(box)

    return filtered_box_list

def calculate_modal_height(box_list):
    """ calculate the modal's height """
    height_list = []
    for box in box_list:
        if box.classname in ('LTTextLineHorizontal', 'LTChar'):
            height_list.append(round(box.bbox[TOP] - box.bbox[BOTTOM]))

    modal_height = Counter(height_list).most_common(1)
    return modal_height[0][0]

def main(args):
    """ main function """
    with open(args.file_name, 'rb') as file_ptr:
        tables = get_tables(file_ptr, args.password)
        for i, table in enumerate(tables):
            print("TABLE {}: ".format(i + 1))
            if args.display:
                print(to_string(table))

if __name__ == '__main__':
    ARGS = argparse.ArgumentParser(description="Parse out tables from PDF")
    ARGS.add_argument('-f', '--file', action='store',
                      required=True,
                      dest='file_name',
                      help='PDF file location and name')
    ARGS.add_argument('-p', '--password', action='store',
                      default='',
                      dest='password',
                      help='PDF file password if required')
    ARGS.add_argument('-d', '--display', action='store_true',
                      help='Output to terminal')
    main(ARGS.parse_args())
