#pylint: disable=W0223
"""
tree classes which hold the parsed PDF document data
"""

import collections
from counter import Counter

class Histogram(Counter):
    """ Returns itself """
    def rounder(self, tol):
        """ Creates this class with Counter init """
        histog = Histogram()
        _rounder = lambda x, y: round((1.0 * x) / y) * y
        for item in self:
            histog = histog + Histogram({_rounder(item, tol): self[item]})
        return histog

class Leaf(object):
    """ Leaf """
    def __init__(self, obj):
        if isinstance(obj, tuple):
            (self.bbox, self.classname, self.text) = obj
        else:
            if obj.__class__.__name__ != 'LTAnon':
                self.bbox = obj.bbox
            else:
                self.bbox = (0, 0, 0, 0)
            self.classname = obj.__class__.__name__
            try:
                self.text = obj.get_text()
            except AttributeError:
                self.text = ''

        self.width = self.bbox[2] - self.bbox[0]

    def __getitem__(self, i):
        """backwards-compatibility helper, don't use it!"""
        error = ("DEPRECATED: don't use leaf[x] - use these instead: "
                 "[0]: bbox, [1]: classname, [2]: text")
        raise RuntimeError(error)
        # return [self.bbox, self.classname, self.text][i]

    def left(self):
        """ get left coordinate """
        return self.bbox[0]

    def bottom(self):
        """ get bottom coordinate """
        return self.bbox[1]

    def right(self):
        """ get right coordinate """
        return self.bbox[2]

    def top(self):
        """ get top cooridinate """
        return self.bbox[3]

    def midline(self):
        """ get self.midline value """
        return (self.bbox[3] + self.bbox[1]) / 2.0

    def centreline(self):
        """ get self.centreline value """
        return (self.bbox[0] + self.bbox[2]) / 2.0

    def get_bbox(self):
        """ get self.bbox value """
        return self.bbox

def children(obj):
    """get all descendants of nested iterables"""
    if isinstance(obj, collections.Iterable):
        for child in obj:
            for node in children(child):
                yield node
    yield obj

class LeafList(list):
    """ builds a list of Leaf instances """
    def purge_empty_text(self):
        """ get rid of any empty text boxes """
        return LeafList(box for box in self if box.text.strip()
                        or box.classname != 'LTTextLineHorizontal')

    def filter_by_type(self, flt=None):
        """ get filter boxes by type(flt) """
        if not flt:
            return self
        return LeafList(box for box in self if box.classname in flt)

    def histogram(self, dir_fun):
        """
        bbox index: 0 = left, 1 = top, 2 = right, 3 = bottom
        for item in self:
            assert type(item) == Leaf, item
        """
        return Histogram(dir_fun(box) for box in self)

    def populate(self, pdfpage, interested=None):
        """ build LeafList """
        if interested is None:
            interested = ["LTPage", "LTTextLineHorizontal"]

        for obj in children(pdfpage):
            if not interested or obj.__class__.__name__ in interested:
                self.append(Leaf(obj))
        return self

    def count(self):
        """ Get Count """
        return Counter(x.classname for x in self)
