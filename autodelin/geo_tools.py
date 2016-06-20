from shapely.geometry import LineString, Point, MultiPoint, GeometryCollection
from matplotlib import pyplot
import copy

PRECISION = 5

DEBUG1 = False
DEBUG2 = False
DEBUG_X_LINES_1_N_2 = False
DEBUG_same_as = False
DEBUG_x_line_dist = False
DEBUG_zig_zag = False
DEBUG_draw_xlines = False
DEBUG_draw_xlines_B = True
DEBUG_contour_loop = False
DEBUG_draw_contour = True


class UnknownIntersection(Exception):
    pass


class NoIntersection(Exception):
    pass


class ADPolyline(object):
    def __init__(self, shapely_geo=None, vertices=None, use_arcpy=False, use_shapely=False):
        """
        Can be initiated with either a shapely Linestring or a list of ADPoints (vertices)
        :param shapely_geo: Linestring object
        :param vertices: list of ADPoint objects
        :param use_arcpy: not implemented yet
        :param use_shapely: default
        :return: None
        """
        if vertices is not None and shapely_geo is None:
            # vertices supplied, create geo
            # assume vertices are all ADPoint
            self.vertices = vertices
            self.__geo_from_vertices(vertices)
        elif vertices is None and shapely_geo is not None:
            # Extract vertices from shapely geo
            self.vertices = []
            self.shapely_geo = shapely_geo
            # Make coordinates python friendly
            coord_list = list(shapely_geo.coords)

            if len(coord_list[0]) == 2:
                # 2d linestring
                for x, y in coord_list:
                    vertex = ADPoint(x, y)
                    self.vertices.append(vertex)
            elif len(coord_list[0]) == 3:
                # 3d linestring - ignore z value
                for x, y, _ in coord_list:
                    vertex = ADPoint(x, y)
                    self.vertices.append(vertex)
            self.first_point = self.vertices[0]
            self.last_point = self.vertices[-1]
        else:
            # got nothing, bail
            raise

        # Only allowed to use arcpy or shapely
        if use_arcpy and use_arcpy:
            raise

        if use_arcpy:
            raise NotImplementedError
            # self.geometry = arcpy.yadayada
            # self.point_at_distance() = arcpy.yada

        if use_shapely:
            pass

        self.length = self.shapely_geo.length

    def __geo_from_vertices(self, vertices):
        temp_vertices = []
        for vertex in vertices:
            temp_vertex = (vertex.X, vertex.Y)
            temp_vertices.append(temp_vertex)
        self.shapely_geo = LineString(temp_vertices)
        self.first_point = self.vertices[0]
        self.last_point = self.vertices[-1]

    def __str__(self):
        s = ''
        for vertex in self.vertices:
            s += str(vertex) + ', '
        return s[:-2]

    def crosses(self, line):
        return self.shapely_geo.crosses(line.shapely_geo)

    def is_same_as(self, polyline):
        if not isinstance(polyline, ADPolyline):
            raise  # something
        if DEBUG_same_as:
            print 'comparing 2 polylines'
        for vertex1, vertex2 in zip(self.vertices, polyline.vertices):
            if not vertex1.is_same_as(vertex2):
                return False
        return True

    def intersection(self, polyline):
        """
        Intersects self with polyline. Returns either ADPoint, list of ADPoints, or returns None
        :param polyline: ADPolyline
        :return: ADPoint, list of ADPoints or None
        """
        new_geo = self.shapely_geo.intersection(polyline.shapely_geo)
        if type(new_geo) is Point:
            return ADPoint(shapely_geo=new_geo)
        elif type(new_geo) is MultiPoint:
            shapely_points = list(new_geo)
            ad_points = []
            for point in shapely_points:
                ad_points.append(ADPoint(shapely_geo=point))
            return ad_points
        else:
            return None

    def mid_point(self):
        """
        Returns midpoint of self
        :return: ADPoint
        """
        return self.interpolate(0.5, normalized=True)

    def nearest_intersection(self, line, test_point):
        """
        Intersects self.shapely_geo with line and returns the intersection nearest to test_point
        If test_point is the location of an intersection it will be returned
        :param line: ADPolyline
        :param point: ADPoint
        :return: ADPoint
        """
        intersects = self.intersection(line)
        # Check for multipoint return or no intersection
        if type(intersects) is ADPoint:
            # single intersection
            return intersects
        elif type(intersects) is None:
            raise UnknownIntersection('BFE doesn\'t intersect with contour')
        elif type(intersects) is not list:
            raise UnknownIntersection('Unknown return type from intersection: '+str(type(intersects)))
        # Assume intersects is a list of ADPoints
        # Sort by distance along self, relative to test_point
        test_dist = self.project(test_point)
        for point in intersects:
            point.station = abs(self.project(point)-test_dist)
        intersects.sort(key=lambda x: x.station)
        # Return closest point
        return intersects[0]

    def num_intersects(self, line):
        """
        Intersects self with line. returns the number of point intersections
        :param line: ADPolyline
        :return: int
        """
        intersect = self.intersection(line)
        if intersect is None:
            return 0
        elif type(intersect) is ADPoint:
            return 1
        elif type(intersect) is list:
            return len(intersect)
        else:
            # Returned polyline or something weird. Maybe raise an exception here?
            return 0

    def point_at_distance(self, distance, normalize=False):
        new_pt = self.shapely_geo.interpolate(distance, normalized=normalize)
        return ADPoint(shapely_geo=new_pt)

    def distance_to(self, gis_thing):
        #print type(gis_thing)
        return self.shapely_geo.distance(gis_thing.shapely_geo)

    def interpolate(self, distance, normalized=False):
        """ Returns ADPoint at distance along polyline """
        geo = self.shapely_geo.interpolate(distance, normalized)
        return ADPoint(shapely_geo=geo)

    def project(self, gis_thing):
        """Returns the distance along this geometric object to a point nearest the other object."""
        return self.shapely_geo.project(gis_thing.shapely_geo)

    def plot(self, *args, **kwargs):
        pyplot.plot(self.shapely_geo.xy[0], self.shapely_geo.xy[1], *args, **kwargs)

    def label(self, text='insert text here', reverse=False, *args, **kwargs):
        if reverse:
            X = self.last_point.X
            Y = self.last_point.Y
        else:
            X = self.first_point.X
            Y = self.first_point.Y
        pyplot.annotate(str(text), xy=(X, Y), *args, **kwargs)

    def clip(self, point1, point2):
        """
        Returns ADPolyline of the current polyline clipped between point1 and point2
        Searches for loop (closed) contours and returns the shortest portion of the contour
        between point1 and point2
        :param point1: ADPoint
        :param point2: ADPoint
        :return: ADPolyline
        """
        # Don't screw up the real vertex order
        vertices = copy.copy(self.vertices)

        if DEBUG_contour_loop:
            print '..before sort start/end vertices', vertices[0], vertices[-1]
        # Check for loop contour
        if vertices[-1].is_same_as(vertices[0]):
            loop_flag = True
        else:
            loop_flag = False

        # tag existing vertices
        for vertex in vertices:
            vertex.flag = False
        # tag new vertices
        point1.flag = True
        point2.flag = True

        # calculate distances for contour vertices the fast way
        last_point = vertices[0]
        last_point.station = 0
        station = 0
        for vertex in vertices[1:]:
            station += vertex.distance(last_point)
            vertex.station = station
            last_point = vertex
        # calculate distances for new vertices the slow way
        point1.station = self.project(point1)
        point2.station = self.project(point2)
        vertices += [point1, point2]
        # sort the vertices
        vertices.sort(key=lambda x: x.station)

        if DEBUG_contour_loop:
            print '..after sort start/end vertices', vertices[0], vertices[-1]

        # extract middle points, keep beginning and end of line for loop calcs
        start_vertices = []
        new_vertices = []
        end_vertices = []
        state = 'start'
        for vertex in vertices:
            if state == 'start' and vertex.flag is False:
                # not one of our points
                start_vertices.append(vertex)
            elif state == 'start' and vertex.flag is True:
                state = 'in'
                new_vertices.append(vertex)
            elif state == 'in' and vertex.flag is False:
                new_vertices.append(vertex)
            elif state == 'in' and vertex.flag is True:
                # last vertex in middle
                state = 'end'
                new_vertices.append(vertex)
            elif state == 'end':
                end_vertices.append(vertex)

        # outside portion of line, for loop contour tests
        outside_vertices = end_vertices + start_vertices[1:]

        if DEBUG_contour_loop:
            print '..len vertices = ', len(vertices)
            print '..len new_vertices = ', len(new_vertices)
            print '..line outside_vertices = ', len(outside_vertices)
            print '..start/end vertices', start_vertices[0], end_vertices[-1]

        inside_line = ADPolyline(vertices=new_vertices)

        # Check for loop contour
        if loop_flag:
            outside_line = ADPolyline(vertices=outside_vertices)
            # loop contour, see if outside is shorter
            if DEBUG_contour_loop:
                print '..loop contour'
                print '..outside line lenght = ', outside_line.length
                print '..inside line length = ', inside_line.length
            if outside_line.length < inside_line.length:
                return outside_line
        if DEBUG_contour_loop:
            print '..returning inside line'
        return inside_line

    def flip(self):
        self.vertices = self.vertices[::-1]
        self.__geo_from_vertices(self.vertices)


class ADPoint(object):
    def __init__(self, X=None, Y=None, shapely_geo=None):
        if X is not None and Y is not None and shapely_geo is None:
            # X and Y supplied, create geo
            self.X = X
            self.Y = Y
            self.shapely_geo = Point((self.X, self.Y))
        elif X is None and Y is None and shapely_geo is not None:
            # Geometry supplied, extract X and Y
            if not isinstance(shapely_geo, Point):
                raise
            self.shapely_geo = shapely_geo
            self.X = list(shapely_geo.coords)[0][0]
            self.Y = list(shapely_geo.coords)[0][1]
        elif X is not None and Y is not None and shapely_geo is not None:
            # Got both, see if they match
            geo_X = list(shapely_geo.coords)[0][0]
            geo_Y = list(shapely_geo.coords)[0][1]
            if geo_X != X or geo_Y != Y:
                raise
            self.X = X
            self.Y = Y
            self.shapely_geo = shapely_geo
        else:
            # Didn't get anything
            raise

    def __str__(self):
        return '(' + str(self.X) + ', ' + str(self.Y) + ')'

    def distance(self, point):
        if not isinstance(point, ADPoint):
            raise
        c_squared = (self.X - point.X) ** 2 + (self.Y - point.Y) ** 2
        return c_squared ** 0.5

    def is_same_as(self, vertex):
        if not isinstance(vertex, ADPoint):
            raise
        if DEBUG_same_as:
            print 'comparing '+str(self)+'/'+str(vertex)
        if round(self.X, PRECISION) == round(vertex.X, PRECISION) and \
                round(self.Y, PRECISION) == round(vertex.Y, PRECISION):
            if DEBUG_same_as:
                print 'same! returning true'
            return True
        else:
            if DEBUG_same_as:
                print 'not same =p returning False'
            return False

    def closest_point(self, polyline):
        """
        Returns closest point to self on polyline
        :param polyline: ADPolyline
        :return: ADPoint
        """
        distance = polyline.shapely_geo.project(self.shapely_geo)
        new_pt = polyline.shapely_geo.interpolate(distance)
        return ADPoint(shapely_geo=new_pt)

    def distance_to(self, gis_thing):
        return self.shapely_geo.distance(gis_thing.shapely_geo)

    def plot(self, *args, **kwargs):
        pyplot.plot(self.X, self.Y, *args, **kwargs)

    def label(self, text='insert text here', *args, **kwargs):
        x = self.X
        y = self.Y
        pyplot.annotate(str(text), xy=(x, y), *args, **kwargs)


class FilterCrossingLines(object):
    """
    Used by _sort_lines() to remove intersecting crossing lines. Preferentially removes lines that
    cross the most other lines. Each crossing line keeps a list (crossing list) of other lines it intersects. When a
    crossing line is removed the crossing list for the other lines is intersects is up dated. This allows the removal
    of the fewest number of lines.
    """
    def __init__(self, lines):
        self.lines = lines

    def filter(self):
        """
        Filters lines in self.lines and intelligently removes intersecting lines. Returns list of resulting lines
        :return: list of ADPolyline
        """
        self._calc_intersections()
        while self._lines_cross():
            self.lines.sort(key=lambda x: x.num_crosses)
            self._remove_last_line()
        assert self.lines != []
        return self.lines

    def _calc_intersections(self):
        """
        Calculates number of intersections for each line in self.lines and which lines intersect.
        Stores number of intersections in line.num_crosses
        Stores list of intersecting ADPolylines in line.crossing_lines
        """
        for current_index, current_line in enumerate(self.lines):
            current_line.num_crosses = 0
            current_line.crossing_lines = []
            # Test against all lines
            for temp_index, temp_line in enumerate(self.lines):
                if current_index == temp_index:
                    # Ignore current line
                    continue
                if current_line.crosses(temp_line):
                    current_line.num_crosses += 1
                    current_line.crossing_lines.append(temp_line)

        # if not True:
        #     for i in range(len(self.lines)):
        #         self.lines[i].number = i
        #
        #     for line in self.lines:
        #         print '\nline', line.number, 'intersects: ',
        #         for other_line in line.crossing_lines:
        #             print other_line.number, ', ',

    def _lines_cross(self):
        """
        Returns true if num_crosses is > 0 for any line in self.lines, else false
        :return: Bool
        """
        for line in self.lines:
            if line.num_crosses > 0:
                return True
        return False

    def _remove_last_line(self):
        """
        Removes last line from self.lines (pop(-1)). Updates num_crosses and intersect_lines for all lines
        the last line intersects
        """
        # Remove last line
        last_line = self.lines.pop(-1)

        if last_line.num_crosses == 0 or last_line.crossing_lines == []:
            raise NoIntersection

        # print '\nremoving line', last_line.number
        # print '\tline', last_line.number, 'intersects: ',
        # for other_line in last_line.crossing_lines:
        #     print other_line.number, ', ',

        # Update all lines previously crossed by last_line
        for current_line in last_line.crossing_lines:
            current_line.num_crosses -= 1
            assert current_line.num_crosses >= 0

            # Remove reference to last_line
            for i, test_line in enumerate(current_line.crossing_lines):
                if test_line is last_line:
                    current_line.crossing_lines.pop(i)
                    break
            else:
                # Should never get here
                raise Exception("should never get here")


def draw_line_between_contours(low_contour, high_contour, last_pos, current_pos):
    """
    Interpolates line from low contour to high_contour based on last_pos and current_pos
    :param low_contour: ADPolyline for lower elevation contour
    :param high_contour: ADPolyline for higher elevation contour
    :param last_pos: float - position to begin at (first vertex) between high and low contour. Varies between 0.0 and
                    1.0. 0 indicates begin at lower contour, 0.999 is almost at high contour
    :param current_pos: float - position to end at (last vertex) between high and low contour
    :return: ADPolyline object
    """
    if DEBUG1:
        low_contour.vertices[0].plot(marker='o', color='black')
        high_contour.vertices[0].plot(marker='x', color='red')
        print 'contour1_lenght=', low_contour.length
        print 'contour2_lenght=', high_contour.length
        if low_contour.first_point.X > low_contour.last_point.X:
            print 'contour1 points west'
        else:
            print 'contour1 points east'
        if high_contour.first_point.X > high_contour.last_point.X:
            print 'contour2 points west'
        else:
            print 'contour2 points east'
    if DEBUG_draw_contour:
        high_contour.plot()
        low_contour.plot()

    # create perpendicular (crossing) lines from contour1 to contour2
    x_lines1 = []
    for vertex in low_contour.vertices:
        closest_point = vertex.closest_point(high_contour)
        temp_line = ADPolyline(vertices=[vertex, closest_point])
        x_lines1.append(temp_line)
    x_lines1 = _remove_intersecting_lines(x_lines1, low_contour)
    assert x_lines1 != []

    if DEBUG_X_LINES_1_N_2:
        print 'len x_lines1=', len(x_lines1)
        for line in x_lines1:
            pyplot.plot(line.shapely_geo.xy[0], line.shapely_geo.xy[1], color='blue', linewidth=3)
        #pyplot.plot(x_lines1[0].shapely_geo.xy[0], x_lines1[0].shapely_geo.xy[1], color='cyan', linewidth=3, marker='>')
    if DEBUG2:
        for line in x_lines1:
            print low_contour.project(line.first_point)

    # create perpendicular (crossing) lines from contour2 to contour1
    x_lines2 = []
    for vertex in high_contour.vertices:
        closest_point = vertex.closest_point(low_contour)
        temp_line = ADPolyline(vertices=[closest_point, vertex])
        x_lines2.append(temp_line)
    x_lines2 = _remove_intersecting_lines(x_lines2, high_contour)
    assert x_lines2 != []

    if DEBUG_X_LINES_1_N_2:
        print 'len x_lines2=', len(x_lines2)
        for line in x_lines2:
            pyplot.plot(line.shapely_geo.xy[0], line.shapely_geo.xy[1], 'g', linewidth=3)
        pyplot.plot(x_lines2[0].shapely_geo.xy[0], x_lines2[0].shapely_geo.xy[1], color='green', linewidth=3, marker='8')
    if DEBUG2:
        for line in x_lines2:
            print low_contour.project(line.first_point)

    # Combine both lists
    crossing_lines = _sort_lines(x_lines1, x_lines2, low_contour, high_contour)

    # Create last crossing line at BFE intercept on contour2
    temp_line = ADPolyline(vertices=[low_contour.last_point, high_contour.last_point])
    if not temp_line.is_same_as(crossing_lines[-1]):
        crossing_lines.append(temp_line)

    # Create first crossing line
    temp_line = ADPolyline(vertices=[low_contour.first_point, high_contour.first_point])
    if not temp_line.is_same_as(crossing_lines[0]):
        crossing_lines.insert(0, temp_line)

    if DEBUG_draw_xlines:
        for i, line in enumerate(crossing_lines):
            pyplot.plot(line.shapely_geo.xy[0], line.shapely_geo.xy[1], color='orange', linewidth=1, marker='^')
            midpoint = line.mid_point()
            midpoint.label(text=i)

    # Fix zip-zags in boundary -----------------------------------------------------------
    # crossing_lines = _fix_zig_zags(crossing_lines, low_contour, 'first_point')
    # crossing_lines = _fix_zig_zags(crossing_lines, high_contour, 'last_point')

    # Add distances along contour1 to crossing lines --------------------------------------
    # Lines should already be sorted
    if DEBUG_x_line_dist:
        print 'calcing crossing_lines distances for ', len(crossing_lines), 'lines'
    total_distance = 0
    for line in crossing_lines:
        line.distance = low_contour.project(line.first_point)
        if DEBUG_x_line_dist:
            print 'line.distance = ', line.distance
        # Hack, I only care about the distance at the last line
        total_distance = line.distance
    if DEBUG_x_line_dist:
        print '     total_distance = ', total_distance
        print 'normal distances:'
    # assert _distance_always_increases(crossing_lines)

    # Normalize distance based on position
    m = (current_pos - last_pos)/total_distance
    b = last_pos
    for line in crossing_lines:
        line.normal_distance = m*line.distance + b
        if DEBUG_x_line_dist:
            print 'normal distance = ', line.normal_distance

    # Correct first and last lines for rounding issues
    # assert round(crossing_lines[0], 1) == 0.0
    # assert round(crossing_lines[-1], 1) == 1.0
    crossing_lines[0].normal_distance = last_pos
    crossing_lines[-1].normal_distance = current_pos

    # Iteratively recalculate distances based on interpolated line -----------------------------
    # The number of iterations should be an option or based on some error check, this is slow however
    for i in range(3):
        # Create test points
        for line in crossing_lines:
            line.test_point = line.point_at_distance(line.normal_distance, normalize=True)

        # recalculate distances based on test points
        total_distance = 0
        last_point = crossing_lines[0].test_point
        for line in crossing_lines[1:]:
            temp_dist = last_point.distance_to(line.test_point)
            total_distance += temp_dist
            line.distance = total_distance
            last_point = line.test_point
        m = (current_pos - last_pos)/total_distance
        b = last_pos
        for line in crossing_lines:
            line.normal_distance = m*line.distance + b

        crossing_lines[0].normal_distance = last_pos
        crossing_lines[-1].normal_distance = current_pos

    if DEBUG_draw_xlines_B:
        for i, line in enumerate(crossing_lines):
            pyplot.plot(line.shapely_geo.xy[0], line.shapely_geo.xy[1], color='orange', linewidth=1, marker='^')
            midpoint = line.mid_point()
            midpoint.label(text=i)

    # Interpolate line --------------------------------------------------------------
    interpolated_points = []
    for line in crossing_lines:
        new_point = line.point_at_distance(line.normal_distance, normalize=True)
        interpolated_points.append(new_point)

    return ADPolyline(vertices=interpolated_points)


def _fix_zig_zags(crossing_lines, contour, point):
    """
    Attempts to fix zig-zags in crossing_lines by sorting based on the distance of point along contour
    :param crossing_lines: list of ADPolylines
    :param contour: ADPolyline - contour to sort against
    :param point: string - 'first_point' or 'last_point'
    :return: list of ADPolylines - sorted crossing_lines if zig-zag detected, otherwise original list
    """
    new_line_order = []
    last_line = crossing_lines[0]
    last_dist = contour.project(getattr(last_line, point))
    swap_flag = False
    for current_line in crossing_lines[1:]:
        current_dist = contour.project(getattr(current_line, point))
        if current_dist < last_dist:  # lines are out of order, swap them
            new_line_order.append(current_line)
            # Next two commented lines are automatic
            # last_line = last_line
            # last_dist = last_dist
            swap_flag = True
        else:
            new_line_order.append(last_line)
            last_line = current_line
            last_dist = current_dist
    if swap_flag:
        new_line_order.append(last_line)
        return new_line_order
    else:
        return crossing_lines


def _sort_lines(x_lines1, x_lines2, low_contour, high_contour):
    """
    Merges x_lines1 and x_lines2 by distance along center line
    :param x_lines1: list of ADPolyline
    :param x_lines2: list of ADPolyline
    :return: list of ADPolylines
    """
    if not True:
        for i, line in enumerate(sorted_lines):
            pyplot.plot(line.shapely_geo.xy[0], line.shapely_geo.xy[1], color='black', linewidth=1, marker='^')
            midpoint = line.mid_point()
            midpoint.label(text=i)

    # Merge and sort x_lines1 and x_lines2
    sorted_lines = x_lines1 + x_lines2

    # Removing intersecting crossing lines
    my_filter = FilterCrossingLines(sorted_lines)
    sorted_lines = my_filter.filter()

    sorted_lines.sort(key=lambda x: low_contour.project(x.first_point))
    sorted_lines.sort(key=lambda x: high_contour.project(x.last_point))

    if not True:
        for i, line in enumerate(sorted_lines):
            pyplot.plot(line.shapely_geo.xy[0], line.shapely_geo.xy[1], color='orange', linewidth=1.5, marker='^')
            # midpoint = line.mid_point()
            # midpoint.label(text=i)
    return sorted_lines


def _remove_intersecting_lines(crossing_lines, contour):
    """
    Returns all lines from crossing_lines that intersect contour and returns them
    :param crossing_lines: list of ADPolyline objects
    :param contour: ADPolyline
    :return: list of ADPolyline objects
    """
    new_lines = []
    for line in crossing_lines:
        if not line.crosses(contour):
            new_lines.append(line)
    return new_lines


def _distance_always_increases(lines):
    last_line = lines[0]
    for line in lines:
        if line.distance < last_line.distance:
            return False
        last_line = line
    return True

