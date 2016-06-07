import geo_tools as gt


class Segment(object):
    """
    Stores information required to delineate a segment of floodplain between two contours. This is used for SMP.
    """
    def __init__(self, low_contour, high_contour, last_pos, current_pos):
        self.low_contour = low_contour
        self.high_contour = high_contour
        self.last_pos = last_pos
        self.current_pos = current_pos

    def run(self):
        return gt.draw_line_between_contours(self.low_contour, self.high_contour, self.last_pos, self.current_pos)


def run_seg(seg):
    return seg.run()
