import math
import geo_tools as gt
from fiona import collection
from shapely.geometry import shape, MultiLineString, LineString, MultiPoint, Point
from matplotlib import pyplot

DEBUG1 = gt.DEBUG1
DEBUG2 = gt.DEBUG2
NEW_DEBUG = True

LEFT = 'left'
RIGHT = 'right'


class ContourNotFound(Exception):
    pass


class ComplexContourError(Exception):
    pass


class RiverImportError(Exception):
    pass


class XSImportError(Exception):
    pass


class ChannelCrossingError(Exception):
    pass


class CrossSectionOrder(Exception):
    pass


class Contour(object):
    def __init__(self, line_list, elevation):
        """
        :param line_list: list of ADPolyline objects representing a dissolved contour
        :param elevation: contour elevation
        :return: None
        """
        self.line_list = line_list
        self.elevation = elevation

        if len(line_list) == 1:
            self.multipart = False
        else:
            self.multipart = True

    def plot(self, *args, **kwargs):
        for line in self.line_list:
            line.plot(*args, **kwargs)

    def __str__(self):
        s = '['
        for line in self.line_list:
            s += '[' + str(line) + '], '
        return s[:-2]+']'

    def __repr__(self):
        return str(self)


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

    # def first_point(self):
    #     return self.geo.vertices[0]
    # 
    # def last_point(self):
    #     return self.geo.vertices[-1]

    def plot(self, *args, **kwargs):
        X = self.geo.first_point.X
        Y = self.geo.first_point.Y
        pyplot.annotate(str(int(self.elevation)), xy=(X, Y))
        self.geo.plot(*args, **kwargs)


class CrossSection(object):
    """
    Contains hec-ras cross section cutlines in ADPolyline format and water surface extents in ADPoint format
    """
    def __init__(self, geo, id):
        self.geo = geo
        self.id = id
        self.name = id
        # The following attributes are populated by module methods
        self.left_extent = None
        self.right_extent = None
        self.elevation = None
        self.station = None
        self.river_intersect = None


def ez_xs_import(xs_file, id_field):
    """
    Imports hec-ras cross section cut lines from xs_file.
    :param xs_file: shapefile
    :param id_field: name of field with cross section id's (profilem)
    :return: list of CrossSection objects
    """
    cross_sections = []
    with collection(xs_file, 'r') as input_file:
        for feature in input_file:
            #print feature['properties']
            xs_id = feature['properties'][id_field]

            # Look out for duplicate XS's
            ### REMOVE WHEN CODE IS UPDATED TO HANDLE MORE XS'S THAN NEEDED
            if any(xs.id == xs_id for xs in cross_sections):
                print 'Duplicate cross section', xs_id, 'Ignoring'
                continue

            # Fiona might give a Linestring or a MultiLineString, handle both cases
            temp_geo = shape(feature['geometry'])
            if type(temp_geo) is not LineString:
                print 'Cross section', xs_id, 'is type', type(temp_geo), ', should be LineString. Aborting.'
                raise XSImportError

            geo = gt.ADPolyline(shapely_geo=temp_geo)
            cross_sections.append(CrossSection(geo, xs_id))
    return cross_sections


def ez_extents_import(extents_file, id_field, position_field, profile_field, profile, elevation_field, cross_sections):
    """
    Imports extents with 'profile' and appends them to appropriate cross_sections
    :param extents_file: shapefile
    :param id_field: field with cross section ids
    :param position_field: field with left or right
    :param profile_field: field listing profiles
    :param profile: desired profile
    :param elevation_field: field listing elevation
    :param cross_sections: list of CrossSection objects
    :return: None
    """
    def get_xs(temp_id):
        for temp_xs in cross_sections:
            if temp_xs.id == temp_id:
                return temp_xs
        print 'Extent for cross section', temp_id, 'does not have a matching cross section. Ignoring.'

    with collection(extents_file, 'r') as input_file:
        for feature in input_file:
            # Verify proper profile
            if feature['properties'][profile_field] != profile:
                continue

            xs_id = feature['properties'][id_field]
            position = feature['properties'][position_field]
            elevation = feature['properties'][elevation_field]
            temp_geo = shape(feature['geometry'])

            if type(temp_geo) is not Point:
                print 'Extent for cross section', xs_id, 'is type', type(temp_geo), ', should be Point. Ignoring.'
                continue

            geo = gt.ADPoint(shapely_geo=temp_geo)
            xs = get_xs(xs_id)
            if xs is None:
                continue
            xs.elevation = elevation
            if position == LEFT:
                xs.left_extent = geo
            elif position == RIGHT:
                xs.right_extent = geo
            else:
                print 'Extent for cross section', xs_id, 'has position', position, 'which is neither', LEFT, 'nor', \
                    RIGHT, 'Ignoring.'


def ez_river_import(river_file):
    """
    imports river from river_file shapefile and returns ADPolyline
    raises exception if file has more than one feature or is not Linestring
    :param river_file: shapefile name
    :return: ADPolyline
    """
    with collection(river_file, 'r') as input_file:
        feature = list(input_file)

        if len(feature) > 1:
            print 'More than one feature in river shapefile', river_file, 'Aborting.'
            raise RiverImportError
        # Fiona might give a Linestring or a MultiLineString, handle both cases
        temp_geo = shape(feature[0]['geometry'])
        if type(temp_geo) is MultiLineString:
            print 'Feature in', river_file, 'is MultiLineString. This is likely an error. Aborting.'
            raise RiverImportError
        elif type(temp_geo) is LineString:
            return gt.ADPolyline(shapely_geo=temp_geo)
        else:
            print 'Feature in', river_file, 'is not a Linestring. Aborting'
            raise RiverImportError


def ez_bfe_import(bfe_file, elevation_field, sort=True):
    """
    Imports bfes from shapefile, assumes all bfes are on the same river/reach
    :param bfe_file: bfe shapefile
    :param elevation_field: name of elevation attribute field in shapefile
    :param sort: sorts bfes in reverse order by elevation if True
    :return: list of BFE objects
    """
    bfes = []
    with collection(bfe_file, 'r') as input_file:
        for feature in input_file:
            elev = feature['properties'][elevation_field]

            # Look out for duplicate BFE's
            ### REMOVE WHEN CODE IS UPDATED TO HANDLE MORE XS'S THAN NEEDED
            if any(bfe.elevation == elev for bfe in bfes):
                print 'Duplicate BFE', elev, 'Ignoring'
                continue

            # Assume BFEs are not multipart
            geo = shape(feature['geometry'])
            if type(geo) is MultiLineString:
                print '*'*20, 'bfe', elev, 'appears to be a multipart feature, aborting'
                raise
            temp_poly = gt.ADPolyline(shapely_geo=geo)
            temp_bfe = BFE(temp_poly, elev)
            bfes.append(temp_bfe)
    if sort:
        bfes.sort(key=lambda x: x.elevation, reverse=True)
    return bfes


def import_contours(contour_file, elevation_field, chatty=False):
    """
    Imports contours from contour file, stores as list of Contour objects
    :param contour_file: name of contour shape file
    :param elevation_field: name of elevation attribute field in contour_file
    :return: list of Contour objects
    """
    contours = []
    with collection(contour_file, 'r') as input_file:
        for feature in input_file:
            elev = feature['properties'][elevation_field]
            # print elev

            # Fiona might give a Linestring or a MultiLineString, handle both cases
            temp_geo = shape(feature['geometry'])
            if type(temp_geo) is MultiLineString:
                geos = list(temp_geo)
            elif type(temp_geo) is LineString:
                geos = list(MultiLineString([temp_geo]))
            else:
                # ???
                raise

            # Convert to ADPolylines
            lines = []
            for geo in geos:
                temp_poly = gt.ADPolyline(shapely_geo=geo)
                lines.append(temp_poly)

            #Make a contour
            temp_contour = Contour(lines, elev)
            contours.append(temp_contour)
            if chatty:
                if len(contours) % 50 == 0:
                    print len(contours), 'contours imported...'
    return contours


def get_crs(filename):
    with collection(filename, 'r') as in_file:
        return in_file.crs


def calc_xs_stations(cross_sections, river):
    """
    Calculates CrossSection.stations for cross section along river
    :param cross_sections: list of CrossSection objects
    :param river: ADPolyline object
    :return: None
    """
    for xs in cross_sections:
        temp_point = river.intersection(xs.geo)
        if type(temp_point) is MultiPoint:
            raise ChannelCrossingError('Cross section'+str(xs.id)+'crosses channel alignment multiple times. Aborting')
        elif temp_point is None:
            raise ChannelCrossingError('Cross section '+str(xs.id)+' does not cross channel alignment. Aborting')
        xs.river_intersect = temp_point
        xs.station = river.project(xs.river_intersect)


def calc_xs_stations_NEW(cross_sections, river):
    """
    Calculates CrossSection.stations for cross section along river
    :param cross_sections: list of CrossSection objects
    :param river: ADPolyline object
    :return: None
    """
    valid_xs = []
    for xs in cross_sections:
        temp_point = river.intersection(xs.geo)
        if type(temp_point) is MultiPoint:
            raise ChannelCrossingError('Cross section'+str(xs.id)+'crosses channel alignment multiple times. Aborting')
        elif temp_point is None:
            print 'Cross section '+str(xs.id)+' does not cross channel alignment. Aborting'
            continue
        xs.river_intersect = temp_point
        xs.station = river.project(xs.river_intersect)
        valid_xs.append(xs)
    return


def calc_bfe_stations(bfes, river):
    """
    Calculates BFE.stations for bfe's along river
    :param bfes: list of BFE objects
    :param river: ADPolyline object
    :return: None
    """
    for bfe in bfes:
        temp_point = river.intersection(bfe.geo)
        if type(temp_point) is MultiPoint:
            print 'BFE', bfe.elevation, 'crosses channel alignment multiple times. Aborting'
            raise
        elif temp_point is None:
            print 'BFE', bfe.elevation, 'does not cross channel alignment. Aborting.'
            raise
        bfe.river_intersect = temp_point
        bfe.station = river.project(bfe.river_intersect)


def merge_bfe_and_xs(bfes, cross_sections):
    """
    Combines list of bfes and cross sections into one list sorted by station
    :param bfes: list of BFE objects
    :param cross_sections: list of CrossSection objects
    :return: combined, sorted list of bfes and cross sections
    """
    combo_list = bfes + cross_sections
    combo_list.sort(key=lambda x: x.station)
    return combo_list


def delineate(bfe_cross_sections, contours):
    """
    Creates floodplain boundaries based on bfes and cross sections along contours
    :param bfe_cross_sections: list of BFE and Cross section objects, sorted downstream to upstream
    :param contours: list of Contour objects
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
            orig_low_contour = _get_contour(contours, math.floor(last_bfe_xs.elevation))
            orig_high_contour = _get_contour(contours, math.ceil(current_bfe_xs.elevation))
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
            orig_low_contour = _get_contour(contours, math.floor(last_bfe_xs.elevation))
            orig_high_contour = _get_contour(contours, math.ceil(current_bfe_xs.elevation))
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


def _get_contour(contours, elevation):
    """
    returns the contour with elevation 'elevation'
    :param contours: list of Contour class objects
    :param elevation: elevation of desired contour
    :return: multi line string
    """
    for contour in contours:
        if contour.elevation == elevation:
            return contour
    raise ContourNotFound


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
        print 'BFE passed to _calc_right_position(). Aborting'
        raise
    high_contour = _get_contour(contours, math.ceil(xs.elevation))
    high_contour = _closest_contour_segment(high_contour, extent)
    low_contour = _get_contour(contours, math.floor(xs.elevation))
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
