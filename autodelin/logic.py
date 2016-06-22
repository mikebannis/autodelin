import math
import geo_tools as gt
import segment
from matplotlib import pyplot
import pathos.multiprocessing as mp
import datetime

DEBUG1 = gt.DEBUG1
DEBUG2 = gt.DEBUG2
NEW_DEBUG = False
DEBUG_COMPLEX_CONTOUR = True

LEFT = 'left'
RIGHT = 'right'
TOLERANCE = 0.001


class ContourNotFound(Exception):
    pass


class ComplexContourError(Exception):
    pass


class CrossSectionOrder(Exception):
    pass


class BFE(object):
    def __init__(self, geo, elevation):
        """
        :param geo: ADPolyline of BFE geometry
        :param elevation: bfe elevation (int/float)
        :return: None
        """
        self.geo = geo
        self.elevation = elevation
        self.name = elevation
        # Following are populated by _calc_bfe_stations()
        self.river_intersect = None
        self.station = None
        self.first_point = self.geo.first_point
        self.last_point = self.geo.last_point

    def plot(self, *args, **kwargs):
        X = self.geo.first_point.X
        Y = self.geo.first_point.Y
        pyplot.annotate(str(int(self.elevation)), xy=(X, Y))
        self.geo.plot(*args, **kwargs)

    def __str__(self):
        return 'bfe-' + str(self.name)

    def __repr__(self):
        return str(self)


def create_segments(bfe_cross_sections, contours, workers=0):
    """
    Runs segment side for both right and left sides.
    :param bfe_cross_sections: list of BFE and Cross Section objects
    :param contours: Contours object
    :param workers: no SMP if 0, uses smp with workers workers if non zero
    :return: list of ADPolyline
    """
    # Check for proper order
    if bfe_cross_sections[0].elevation > bfe_cross_sections[-1].elevation:
        print 'BFE/cross section list appears to be in reverse order. Reversing.'
        bfe_cross_sections = bfe_cross_sections[::-1]

    #l_bound = segment_side(bfe_cross_sections, contours, LEFT, workers)
    r_bound = segment_side(bfe_cross_sections, contours, RIGHT, workers)
    return l_bound + r_bound


def segment_side(bfe_cross_sections, contours, side, workers):
    """
    Delineates floodplain and returns boundary
    :param bfe_cross_sections: list of BFE and CrossSection objects
    :param contours: Contours object
    :param side: string: LEFT or RIGHT
    :param workers: no SMP if 0, uses smp with workers workers if non zero
    :return: list of ADPolyline
    """
    # TODO - make this whole thing an object
    # Set attribute names for LEFT vs RIGHT
    if side == LEFT:
        end_point = 'first_point'
        extent = 'left_extent'
        other_extent = 'right_extent'
    elif side == RIGHT:
        end_point = 'last_point'
        extent = 'right_extent'
        other_extent = 'left_extent'
    else:
        raise ValueError('side was set to ' + side + '. side must be ' + LEFT + ' or ' + RIGHT)

    print '******** Working on', side, 'side'

    # Find first valid bfe/cross_section
    remaining_bfe_xs = None
    for i, bfe_xs in enumerate(bfe_cross_sections):
        last_bfe_xs = bfe_xs
        if type(last_bfe_xs) is BFE:
            last_position = 0.0
            last_high_pt = getattr(last_bfe_xs, end_point)
            last_low_pt = getattr(last_bfe_xs, end_point)
            remaining_bfe_xs = bfe_cross_sections[i + 1:]
            break
        else:  # cross section
            last_position, last_high_pt, last_low_pt = \
                _calc_extent_position(last_bfe_xs, getattr(last_bfe_xs, extent), getattr(last_bfe_xs, other_extent),
                                      contours)
            if last_position >= 0:
                remaining_bfe_xs = bfe_cross_sections[i + 1:]
                break
    if remaining_bfe_xs is None:
        raise ValueError('Unable to find valid BFE/cross section in bfe_cross_sections.')

    segments = []
    boundary = []
    # Loop through all the remaining BFE/XS
    for current_bfe_xs in remaining_bfe_xs:
        print '--- Segmenting last', last_bfe_xs.name, 'to current', current_bfe_xs.name
        try:
            orig_low_contour = contours.get(math.floor(last_bfe_xs.elevation))
            orig_high_contour = contours.get(math.ceil(current_bfe_xs.elevation))

            # Calculate current high and low points for clipping contours
            if type(current_bfe_xs) is BFE:
                # current_high_pt is last vertex on BFE
                current_position = 1
                current_high_pt = getattr(current_bfe_xs, end_point)
                # current_low_pt is found by intersecting current BFE w/ low contour
                temp_low_contour = orig_low_contour.closest_contour_segment(getattr(current_bfe_xs, end_point))
                current_low_pt = current_bfe_xs.geo.nearest_intersection(temp_low_contour, getattr(current_bfe_xs,
                                                                                                   end_point))
            else:  # CrossSection
                current_position, current_high_pt, current_low_pt = \
                    _calc_extent_position(current_bfe_xs, getattr(current_bfe_xs, extent),
                                          getattr(current_bfe_xs, other_extent), contours)
                # Ignore extent if outside of contours
                if current_position < 0:
                    print 'Bad extent, ignoring.'
                    continue

            # print 'last low pt',type(last_low_pt), last_low_pt, 'current_low_pt', type(current_low_pt), current_low_pt
            # trim contours between current and last BFE/XS
            low_contour = _clip_complex(orig_low_contour, last_low_pt, current_low_pt)
            high_contour = _clip_complex(orig_high_contour, last_high_pt, current_high_pt)

            if NEW_DEBUG:
                low_contour.plot(color='black', linewidth=2)
                high_contour.plot(color='red')
                low_contour.first_point.plot(marker='o')
                low_contour.last_point.plot(marker='o')
                high_contour.first_point.plot(marker='o')
                high_contour.last_point.plot(marker='o')

            # print 'lens', len(low_contour), len(high_contour), low_contour, high_contour
            if type(low_contour) is gt.ADPolyline and type(high_contour) is gt.ADPolyline:
                # force contours to point upstream
                _orient_contours(last_low_pt, low_contour)
                _orient_contours(last_high_pt, high_contour)

                temp_seg = segment.Segment(low_contour, high_contour, last_position, current_position)
                temp_seg.current_feature = current_bfe_xs
                temp_seg.last_feature = last_bfe_xs
                segments.append(temp_seg)
            elif type(low_contour) is tuple and type(high_contour) is gt.ADPolyline:
                print ' &&&&&&&&&&&&&& Got a complex one'
                low_contour1 = low_contour[0]
                low_contour2 = low_contour[1]

                # force contours to point upstream
                _orient_contours(last_high_pt, high_contour)
                _orient_contours(last_low_pt, low_contour1)
                _orient_contours(last_low_pt, low_contour2)

                if DEBUG_COMPLEX_CONTOUR:
                    high_contour.plot()
                    low_contour1.plot()
                    low_contour2.plot()
                    pyplot.show()

                # Calculate position in middle. This may need to be upgraded
                middle_position = last_position + (current_position - last_position)*low_contour1.length / \
                                                  (low_contour1.length + low_contour2.length)
                print last_position, middle_position, current_position
                temp_seg1 = segment.Segment(low_contour1, high_contour, last_position, middle_position)
                temp_seg2 = segment.Segment(low_contour2, high_contour, middle_position, current_position)
                segments.append(temp_seg1)
                segments.append(temp_seg2)
            else:
                print 'Unhandled funky contour'

        except ComplexContourError:
            print 'Funky contour - skipping'
        except ContourNotFound:
            print 'Contour not found'
        except gt.UnknownIntersection:
            print 'Contour doesn\'t intersect BFE/cross section'
        # except Exception as e:
        #     print 'Unknown exception:', str(e)

        # Reset for next BFE/XS
        last_bfe_xs = current_bfe_xs
        if type(last_bfe_xs) is BFE:
            # BFE, last high is new low
            last_low_pt = current_high_pt
            # TODO - Hack, should extend BFE or intersect XS
            last_high_pt = current_high_pt
        else:  # Cross section
            last_low_pt = current_low_pt
            # Hack, should extend BFE or intersect XS
            last_high_pt = current_high_pt
        if current_position == 1:
            last_position = 0
        else:
            last_position = current_position

    # ---------------- run segments -----------------
    now = datetime.datetime.now()
    if workers == 0:  # Don't use SMP
        print 'Delineating segments (no SMP)'
        for current_segment in segments:
            print str(current_segment)
            result = current_segment.run()
            result.status = 'testing'
            boundary.append(result)
    else:
        pool = mp.ProcessingPool(workers=workers)
        print 'Delineating', len(segments), 'segments with', workers, 'sub processes.'
        boundary = list(pool.map(segment.run_seg, segments))
    time = datetime.datetime.now() - now
    print 'Completed', len(segments), 'in', time, '.', (time / len(segments)), 'per segment.'

    for x in boundary:
        x.status = 'testing'
    return boundary


def _clip_to_bfe(contour, point1, point2):
    """
    returns segment of contour between points on line nearest point1 and point2
    :param contour: Contour object
    :param point1: ADPoint
    :param point2: ADPoint
    :return: ADPolyline
    """
    if contour.multipart:
        # Find segment nearest to both points
        index1 = contour.closest_segment_by_index(point1)
        index2 = contour.closest_segment_by_index(point2)
        # If not on same segment raise ComplexContourError
        if index1 != index2:
            raise ComplexContourError
        contour_poly = contour.line_list[index1]
    else:
        contour_poly = contour[0]

    if DEBUG1:
        print 'contour in _clip_to_bfe first/last point', contour_poly.first_point, contour_poly.last_point
    # Find nearest points to point1 and point2 on contour
    point1 = contour_poly.point_at_distance(contour_poly.project(point1))
    point2 = contour_poly.point_at_distance(contour_poly.project(point2))
    return contour_poly.clip(point1, point2)


def _clip_complex(complex_contour, point1, point2):
    """
    Clip complex contour by proximity to the opposite point. Returns
    two ADPolylines, the contour fragment closest to point1, followed by the fragment closest to point 2
    If simple contour: returns _clip_to_bfe()
    :param complex_contour: Contour object
    :param point1: ADPoint - point on complex_contour
    :param point2: ADPoint - point on complex_contour
    :return: ADPolyline or (ADPolyline, ADPolyline)
    """
    # TODO - this is likely easily fooled by curved and "odd" contours. Update to clip by location on simple contour
    # closest to both complex segments

    if not complex_contour.multipart:
        return _clip_to_bfe(complex_contour, point1, point2)
    # Find segment nearest to both points
    index1 = complex_contour.closest_segment_by_index(point1)
    index2 = complex_contour.closest_segment_by_index(point2)
    # if index is the same use the simple function
    if index1 == index2:
        return _clip_to_bfe(complex_contour, point1, point2)

    # Find segments nearest to both points
    contour_poly1 = complex_contour.closest_contour_segment(point1)
    contour_poly2 = complex_contour.closest_contour_segment(point2)

    # Find points to clip first segment
    point_A = contour_poly1.point_at_distance(contour_poly1.project(point1))
    point_B = contour_poly1.point_at_distance(contour_poly1.project(point2))

    # Find points to clip second segment
    point_C = contour_poly2.point_at_distance(contour_poly2.project(point1))
    point_D = contour_poly2.point_at_distance(contour_poly2.project(point2))

    return contour_poly1.clip(point_A, point_B), contour_poly2.clip(point_C, point_D)


def _calc_extent_position(xs, extent, other_extent, contours):
    """
    Calculates the desired position of the floodplain boundary between the lower and higher contour as a value
     between 0.0 and 1.0.  If the cross section extent is outside the appropriate contours it will be -1
     This only handles cross sections, not bfes
    :param xs: CrossSection object
    :param contours: contour list
    :return: float, -1 if outside contours, -2 if other error, high point and low point
    """

    def simplify(points):
        """ reduces list of ADPoints to the point closest to extent """
        if type(points) is gt.ADPoint:
            return points
        elif type(points) is list:
            points.sort(key=lambda x: x.distance(extent))
            return points[0]
        else:
            return None

    if type(xs) is BFE:
        raise ValueError('BFE passed to _calc_extent_position().')

    high_contour = contours.get(math.ceil(xs.elevation))
    high_contour = high_contour.closest_contour_segment(extent)
    low_contour = contours.get(math.floor(xs.elevation))
    low_contour = low_contour.closest_contour_segment(extent)

    # Cross section contour intersections
    high_point = simplify(high_contour.intersection(xs.geo))
    low_point = simplify(low_contour.intersection(xs.geo))

    # Check for no intersect and us nearest point
    if high_point is None:
        high_point = extent.closest_point(high_contour)
    if low_point is None:
        low_point = extent.closest_point(low_contour)
    # Detect single intersection on wrong side of XS and return nearest point on contour
    if high_point.distance(other_extent) < high_point.distance(extent):
        high_point = extent.closest_point(high_contour)
    if low_point.distance(other_extent) < low_point.distance(extent):
        low_point = extent.closest_point(low_contour)

    # See if extent is between correct contours
    high_dist = high_point.distance(extent)
    low_dist = low_point.distance(extent)
    contour_dist = high_point.distance(low_point)
    if high_dist > contour_dist or low_dist > contour_dist:
        # outside contours
        return -1, None, None
    # Return position
    return low_dist / contour_dist, high_point, low_point


def _contour_crosses_boundary(boundary, contour1, contour2):
    """
    Tests if boundary crosses contour1 or contour2. Returns True if crosses, else False
    DOES NOT CURRENTLY WORK AND IS NOT USED. PLEASE UPDATE
    :param boundary: ADPolyline object
    :param contour1: Contour object
    :param contour2: Contour object
    :return: boolean
    """
    for contour in contour1.line_list:
        if contour.num_intersects(boundary) > 1:
            return True
    for contour in contour2.line_list:
        if contour.num_intersects(boundary) > 1:
            return True
    return False


def _orient_contours(point, contour):
    """
    orients contour so that the LineString beginning is nearest to point
    :param point: ADPoint
    :param contour: ADPolyline
    :return: None
    """
    first_dist = point.distance(contour.first_point)
    last_dist = point.distance(contour.last_point)
    if DEBUG1:
        print 'dist to contour: first_point=', first_dist, 'last point=', last_dist
    if first_dist > last_dist:
        if DEBUG1:
            print 'flipping contour'
        contour.flip()
