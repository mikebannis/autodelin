import geo_tools as gt


class Segment(object):
    """
    Stores information required to segment a segment of floodplain between two contours. This is used for SMP.
    """
    def __init__(self, low_contour, high_contour, last_pos, current_pos):
        self.low_contour = low_contour
        self.high_contour = high_contour
        self.last_pos = last_pos
        self.current_pos = current_pos

        self.current_feature = None
        self.last_feature = None
        # TODO - Add cross sections and contours to this list and check for intersections after running, update status

    def run(self):
        return gt.draw_line_between_contours(self.low_contour, self.high_contour, self.last_pos, self.current_pos)

    def __str__(self):
        return 'Current: '+str(self.current_feature)+' Last: '+str(self.last_feature)#+' High C: '+self.high_contour.elev+ \
               # ' Low C: '+self.low_contour.elev


def run_seg(seg):
    return seg.run()

    # if type(boundary) is gt.ADPolyline:
    #     print 'Success'
    # if _contour_crosses_boundary(boundary, orig_high_contour, orig_low_contour):
    #     status = 'Crosses'
    # else:
    #     status = 'OK'
    # boundary.status = status
    #
    # left_boundary.append(boundary)
