import math
import geo_tools as gt
from fiona import collection
from shapely.geometry import shape, MultiLineString, LineString, MultiPoint, Point
from matplotlib import pyplot

DEBUG1 = gt.DEBUG1
DEBUG2 = gt.DEBUG2
NEW_DEBUG = True


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
        # Following are populated by calc_bfe_stations()
        self.river_intersect = None
        self.station = None
        self.first_point = self.geo.first_point
        self.last_point = self.geo.last_point

    def plot(self, *args, **kwargs):
        X = self.geo.first_point.X
        Y = self.geo.first_point.Y
        pyplot.annotate(str(int(self.elevation)), xy=(X, Y))
        self.geo.plot(*args, **kwargs)


def delineate(bfe_cross_sections, contours):
    """
    Creates floodplain boundaries based on bfes and cross sections along contours
    :param bfe_cross_sections: list of BFE and Cross section objects, sorted downstream to upstream
    :param contours: Contours object
    :return: two lists of ADPolyline objects, left boundary and right boundary
    """
    # Check for proper order
    if bfe_cross_sections[0].elevation > bfe_cross_sections[-1].elevation:
        print 'BFE/cross section list appears to be in reverse order. Reversing.'
        bfe_cross_sections = bfe_cross_sections[::-1]

    # Do left side -----------------------------------------------------------------------------
    print '--'*20+'left side'
    left_boundary = []
    # Find first valid bfe/cross_section
    remaining_bfe_xs = None
    for i, bfe_xs in enumerate(bfe_cross_sections):
        last_bfe_xs = bfe_xs
        if type(last_bfe_xs) is BFE:
            last_position = 0.0
            last_high_pt = last_bfe_xs.first_point
            last_low_pt = last_bfe_xs.first_point
            remaining_bfe_xs = bfe_cross_sections[i+1:]
            break
        else:  # cross section
            last_position, last_high_pt, last_low_pt = _calc_extent_position(last_bfe_xs,
                                                                             last_bfe_xs.left_extent, contours)
            if last_position >= 0:
                remaining_bfe_xs = bfe_cross_sections[i+1:]
                break
    if remaining_bfe_xs is None:
        print 'Error finding valid BFE/cross section'
        raise

    # Loop through all the remaining BFE/XS
    for current_bfe_xs in remaining_bfe_xs:
        print '*******Working on last', last_bfe_xs.name, 'to current', current_bfe_xs.name
        try:
            orig_low_contour = contours.get(math.floor(last_bfe_xs.elevation))
            orig_high_contour = contours.get(math.ceil(current_bfe_xs.elevation))
            # Calculate current high and low points for clipping contours
            if type(current_bfe_xs) is BFE:
                current_position = 1
                current_high_pt = current_bfe_xs.first_point
                # Hack, should run an intersect
                #current_low_pt = current_bfe_xs.first_point
                temp_low_contour = _closest_contour_segment(orig_low_contour, current_bfe_xs.first_point)
                current_low_pt = current_bfe_xs.geo.nearest_intersection(temp_low_contour, current_bfe_xs.first_point)
            else:  # CrossSection
                current_position, current_high_pt, current_low_pt = \
                    _calc_extent_position(current_bfe_xs, current_bfe_xs.left_extent, contours)
                # Ignore extent if outside of contours
                if current_position < 0:
                    print 'Bad extent, ignoring.'
                    continue

            print 'last low pt', type(last_low_pt), last_low_pt, 'current_low_pt', type(current_low_pt), current_low_pt
            low_contour = _clip_to_bfe(orig_low_contour, last_low_pt, current_low_pt)
            high_contour = _clip_to_bfe(orig_high_contour, last_high_pt, current_high_pt)

            _orient_contours(last_low_pt, low_contour)
            _orient_contours(last_high_pt, high_contour)

            if NEW_DEBUG:
                low_contour.plot(color='black', linewidth=2)
                high_contour.plot(color='red')
                low_contour.first_point.plot(marker='o')
                low_contour.last_point.plot(marker='o')
                high_contour.first_point.plot(marker='o')
                high_contour.last_point.plot(marker='o')

            boundary = gt.draw_line_between_contours(low_contour, high_contour, last_position, current_position)
            if type(boundary) is gt.ADPolyline:
                print 'Success'
            left_boundary.append(boundary)

            if DEBUG1:
                boundary.plot(marker='D')
        except ComplexContourError:
            print 'Left: Funky contour'
        except ContourNotFound:
            print 'Left: Contour not found'
        except Exception as e:
            print 'Left: unknown exception:', str(e)
            raise

        # Reset for next BFE/XS
        last_bfe_xs = current_bfe_xs
        if type(last_bfe_xs) is BFE:
            # BFE, last high is new low
            last_low_pt = current_high_pt
            # Hack, should extend BFE or intersect XS
            last_high_pt = current_high_pt
        else: # Cross section
            last_low_pt = current_low_pt
            # Hack, should extend BFE or intersect XS
            last_high_pt = current_high_pt
        if current_position == 1:
            last_position = 0
        else:
            last_position = current_position

    # Do right side --------------------------------------------------------------------------
    print '--'*20+'right side'
    right_boundary = []
    # Find first valid bfe/cross_section
    remaining_bfe_xs = None
    for i, bfe_xs in enumerate(bfe_cross_sections):
        last_bfe_xs = bfe_xs
        if type(last_bfe_xs) is BFE:
            last_position = 0.0
            last_high_pt = last_bfe_xs.last_point
            last_low_pt = last_bfe_xs.last_point
            remaining_bfe_xs = bfe_cross_sections[i+1:]
            break
        else:  # cross section
            last_position, last_high_pt, last_low_pt = _calc_extent_position(last_bfe_xs,
                                                                             last_bfe_xs.right_extent, contours)
            if last_position >= 0:
                remaining_bfe_xs = bfe_cross_sections[i+1:]
                break
    if remaining_bfe_xs is None:
        print 'Error finding valid BFE/cross section'
        raise

    # Loop through all the remaining BFE/XS
    for current_bfe_xs in remaining_bfe_xs:
        print '*******Working on last', last_bfe_xs.name, 'to current', current_bfe_xs.name
        try:
            orig_low_contour = contours.get(math.floor(last_bfe_xs.elevation))
            orig_high_contour = contours.get(math.ceil(current_bfe_xs.elevation))
            if type(current_bfe_xs) is BFE:
                current_position = 1
                current_high_pt = current_bfe_xs.last_point
                # Hack, should run an intersect
                # current_low_pt = current_bfe_xs.last_point
                temp_low_contour = _closest_contour_segment(orig_low_contour, current_bfe_xs.last_point)
                current_low_pt = current_bfe_xs.geo.nearest_intersection(temp_low_contour, current_bfe_xs.last_point)
            else:  # CrossSection
                current_position, current_high_pt, current_low_pt = \
                    _calc_extent_position(current_bfe_xs, current_bfe_xs.right_extent, contours)
                # Ignore extent if outside of contours
                if current_position < 0:
                    print 'Bad extent, ignoring.'
                    continue

            #print 'last low pt', type(last_low_pt), last_low_pt, 'current_low_pt', type(current_low_pt), current_low_pt
            low_contour = _clip_to_bfe(orig_low_contour, last_low_pt, current_low_pt)
            high_contour = _clip_to_bfe(orig_high_contour, last_high_pt, current_high_pt)

            _orient_contours(last_low_pt, low_contour)
            _orient_contours(last_high_pt, high_contour)

            if NEW_DEBUG:
                low_contour.plot(color='black', linewidth=2)
                high_contour.plot(color='red')
                low_contour.first_point.plot(marker='o')
                low_contour.last_point.plot(marker='o')
                high_contour.first_point.plot(marker='o')
                high_contour.last_point.plot(marker='o')

            boundary = gt.draw_line_between_contours(low_contour, high_contour, last_position, current_position)
            if type(boundary) is gt.ADPolyline:
                print 'Success'
            right_boundary.append(boundary)

            if DEBUG1:
                boundary.plot(marker='D')
        except ComplexContourError:
            print 'Right: Funky contour'
        except ContourNotFound:
            print 'Right: Contour not found'
        except Exception as e:
            print 'Right: unknown exception:', str(e)
            raise

        # Reset for next BFE/XS
        last_bfe_xs = current_bfe_xs
        if type(last_bfe_xs) is BFE:
            # BFE, last high is new low
            last_low_pt = current_high_pt
            # Hack, should extend BFE or intersect XS
            last_high_pt = current_high_pt
        else:  # Cross section
            last_low_pt = current_low_pt
            last_high_pt = current_high_pt
        if current_position == 1:
            last_position = 0
        else:
            last_position = current_position
    return left_boundary, right_boundary


def _clip_to_bfe(contour, point1, point2):
    """
    returns segment of contour between points on line nearest point1 and point2
    :param contour: list of ADPolyline objects
    :param point1: ADPoint
    :param point2: ADPoint
    :return: ADPolyline
    """
    if contour.multipart:
        # Find segment nearest to both points
        index1 = _closest_segment_by_index(contour.line_list, point1)
        index2 = _closest_segment_by_index(contour.line_list, point2)
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


def _closest_segment_by_index(line_list, point):
        """
        Returns index of line (contour) in line_list that is closest to point
        :param line_list: list of ADPolylines
        :param point: ADPoint
        :return: int
        """
        index = 0
        #print ' in closest_segment-', type(point)
        current_dist = line_list[0].distance_to(point)
        for i in range(1, len(line_list)):
            dist = line_list[i].distance_to(point)
            if dist < current_dist:
                current_dist = dist
                index = i
        return index


def _closest_contour_segment(contour, point):
    """
    Returns ADPolyline segment of contour closest to point
    :param contour: Contour object
    :param point: ADPoint object
    :return: ADPolyline object
    """
    i = _closest_segment_by_index(contour.line_list, point)
    return contour.line_list[i]


def _calc_extent_position(xs, extent, contours):
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
        print 'BFE passed to _calc_extent_position(). Aborting'
        raise
    high_contour = contours.get(math.ceil(xs.elevation))
    high_contour = _closest_contour_segment(high_contour, extent)
    low_contour = contours.get(math.floor(xs.elevation))
    low_contour = _closest_contour_segment(low_contour, extent)
    # Cross section contour intersections
    high_point = simplify(high_contour.intersection(xs.geo))
    low_point = simplify(low_contour.intersection(xs.geo))
    if high_point is None or low_point is None:
        return -2, None, None

    # See if extent is between correct contours
    high_dist = high_point.distance(extent)
    low_dist = low_point.distance(extent)
    contour_dist = high_point.distance(low_point)
    if high_dist > contour_dist or low_dist > contour_dist:
        # outside contours
        return -1, None, None
    # Return position
    return low_dist/contour_dist, high_point, low_point


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
        if contour.crosses(boundary):
            return True
    for contour in contour2.line_list:
        if contour.crosses(boundary):
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

#def _calc_bfe_intersects(last_bfe_xs, contours):
#     """
#     Returns bfe contour intersection point
#     :param last_bfe_xs: BFE object
#     :param contours: list of Contour objects
#     :return: ADPoint, ADPoint
#     """
#     if contour.multipart:
#         # Find segment nearest to both points
#         index1 = _closest_segment_by_index(contour.line_list, point1)
#         index2 = _closest_segment_by_index(contour.line_list, point2)
#         # If not on same segment raise ComplexContourError
#         if index1 != index2:
#             raise ComplexContourError
#         contour_poly = contour.line_list[index1]
#     else:
#         contour_poly = contour[0]
#
#     if DEBUG1:
#         print 'contour in _clip_to_bfe first/last point', contour_poly.first_point, contour_poly.last_point
#     # Find nearest points to point1 and point2 on contour
#     point1 = contour_poly.point_at_distance(contour_poly.project(point1))
#     point2 = contour_poly.point_at_distance(contour_poly.project(point2))
#     pass

# def delineate_by_bfes(bfes, contours):
#     """
#     Creates floodplain boundaries based on bfes along contours
#     :param bfes: list of BFE objects
#     :param contours: list of Contour objects
#     :return: two lists of ADPolyline objects, left boundary and right boundary
#     """
#     left_boundary = []
#     right_boundary = []
#     # Assumes bfes is in decreasing elevation
#     last_bfe = bfes.pop(0)
#     for current_bfe in bfes:
#         try:
#             print '*'*30+str(current_bfe.elevation)
#             # Do left side -----------------------------------------------------------------------------
#             if DEBUG1:
#                 print '-'*20+'left side'
#             orig_contour1 = _get_contour(contours, last_bfe.elevation)
#             contour1 = _clip_to_bfe(orig_contour1, last_bfe.first_point, current_bfe.first_point)
#             orig_contour2 = _get_contour(contours, current_bfe.elevation)
#             contour2 = _clip_to_bfe(orig_contour2, current_bfe.first_point, last_bfe.first_point)
#
#             if DEBUG1:
#                 print 'contour1 first point/last point', str(contour1.first_point), str(contour1.last_point)
#             _orient_contours(last_bfe.first_point, contour1, contour2)
#             if DEBUG1:
#                 print 'contour1 first point/last after orient', str(contour1.first_point), str(contour1.last_point)
#                 contour1.plot(color='black', linewidth=2)
#                 contour2.plot(color='red')
#                 contour1.first_point.plot(marker='*')
#
#             boundary = gt.draw_line_between_contours(contour1, contour2)
#             if _contour_crosses_boundary(boundary, orig_contour1, orig_contour2):
#                 boundary.status = 'crosses_contour'
#             else:
#                 boundary.status = 'ok'
#             left_boundary.append(boundary)
#
#             if DEBUG1:
#                 boundary.plot(marker='D')
#         except ComplexContourError:
#             print 'Left: Funky contour'
#         except ContourNotFound:
#             print 'Left: Contour not found'
#         except Exception as e:
#             print 'Right: unknown exception:', str(e)
#
#         try:
#             # Do right side --------------------------------------------------------------------------
#             if DEBUG1:
#                 print '-'*20+'right side'
#             orig_contour1 = _get_contour(contours, last_bfe.elevation)
#             contour1 = _clip_to_bfe(orig_contour1, last_bfe.last_point, current_bfe.last_point)
#             orig_contour2 = _get_contour(contours, current_bfe.elevation)
#             contour2 = _clip_to_bfe(orig_contour2, current_bfe.last_point, last_bfe.last_point)
#             if DEBUG1:
#                 print 'contour1 first point/last point', str(contour1.first_point), str(contour1.last_point)
#
#             _orient_contours(last_bfe.last_point, contour1, contour2)
#             if DEBUG1:
#                 print 'contour1 first point/last after orient', str(contour1.first_point), str(contour1.last_point)
#             if DEBUG1:
#                 contour1.plot(color='black', linewidth=2)
#                 contour2.plot(color='red')
#                 contour1.first_point.plot(marker='*')
#
#             boundary = gt.draw_line_between_contours(contour1, contour2)
#             if _contour_crosses_boundary(boundary, orig_contour1, orig_contour2):
#                 boundary.status = 'crosses_contour'
#             else:
#                 boundary.status = 'ok'
#             right_boundary.append(boundary)
#
#             if DEBUG1:
#                 boundary.plot(marker='D')
#         except ComplexContourError:
#             print 'Right: Funky contour. Not delineating'
#         except ContourNotFound:
#             print 'Right: Contour not found. Not delineating'
#         except Exception as e:
#             print 'Right: unknown exception:', str(e)
#
#         last_bfe = current_bfe
#     return left_boundary, right_boundary
