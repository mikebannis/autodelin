from numpy import arange
import geo_tools as gt
from math import pi, radians, cos, sin, degrees

tolerance = 0.001  # tolerance for determining if points are on line
angle_tol = radians(1)  # tolerance for determining angles are balanced
BADSCORE = 999
DEBUG_FAN = False
DEBUG_OPTIMIZE = False
DEBUG_RATE_LINE = False

class NoIntersect(Exception):
    pass


class MaxIterations(Exception):
    pass


class ALException(Exception):
    pass


class BetterXLine(object):
    """
    Creates and returns angle optimized crossing line between left_line and right_line starting at start_pt.
    After initiating the object, self.create() should be called.
    """

    def __init__(self, left_line, right_line, start_pt):
        """

        :param left_line: ADPolyline - left contour (looking downstream)
        :param right_line: ADPolyline - right contour (looking downstream)
        :param start_pt: ADPoint - "anchor" point to begin drawing x-line from. must be on either contour
        """
        self.left_line = left_line  # ADPolyline - left contour
        self.right_line = right_line  # ADPolyline - right contour
        self.start_pt = start_pt    # ADPoint - must lie on either contour

        self.spread = 0.75*pi   # float - width of fan for inital search (radians)
        self.initial_tests = 7  # int - number of lines for initial search, rounded up if even
        self.iterations = 0  # current iteration - used in _optimize()
        self.back_length = 1  # used in _optimize()
        self.max_iters = 10  # max iterations -used in _optimize()
        # TODO - determine self.length automatically
        self.length = 1000  # length is determined automatically based on greatest width of left_line and right_line
        self.side = None  # Which side is start_pt on? determined below

        # Verify start_pt is on left or right_line
        if abs(self.left_line.distance_to(self.start_pt)) < tolerance:
            self.side = 'left'
        elif abs(self.right_line.distance_to(self.start_pt)) < tolerance:
            self.side = 'right'
        else:
            raise AttributeError('start_pt is not on left_line or right_line')

        # Ensure initial tests is odd
        if self.initial_tests % 2 == 0:
            self.initial_tests += 1

    def create(self):
        """
        Creates angle optimized crossing line between left_line and right_line, starting at start_pt. start_pt must be
        on right or left_line.
        :return: ADPolyline
        """
        # Create perpendicular (first) line
        if self.side == 'left':
            perp_line, perp_angle = perpendicular_line(self.start_pt, self.left_line, self.length, direction='right',
                                                       return_angle=True) # TODO - should this have back_length?
        else:
            perp_line, perp_angle = perpendicular_line(self.start_pt, self.right_line, self.length, direction='left',
                                                       return_angle=True, back_length=self.back_length)
        perp_line.angle = perp_angle

        # --------- Create initial lines
        angle_step = self.spread / (self.initial_tests - 1)
        start = perp_angle - self.spread/2.0
        end = perp_angle + self.spread/2.0 + angle_step
        test_lines = []
        # Create lines clockwise of perp line
        for angle in arange(start, perp_angle, angle_step):
            temp_line = line_at_angle(self.start_pt, angle, self.length, back_length=1)
            temp_line.angle = angle
            test_lines.append(temp_line)
        # Add perp line
        test_lines.append(perp_line)
        # Create lines CCW of perp_line
        for angle in arange(perp_angle+angle_step, end, angle_step):
            temp_line = line_at_angle(self.start_pt, angle, self.length, back_length=1)
            temp_line.angle = angle
            test_lines.append(temp_line)

        if DEBUG_FAN:
            for i, line in enumerate(test_lines):
                print 'test line:', i
                score =  self._rate_line(line)
                line.label(text=str(i)+'/'+str(round(degrees(score), 0)), reverse=True)
                line.plot(color='orange')


        # Score lines
        for line in test_lines:
            score = self._rate_line(line)
            line.score = score

        # Find best two lines to start with
        # TODO: check for line with "perfect" score

        for i, line in enumerate(test_lines):
            if line.score != BADSCORE:
                last_line = line
                test_lines = test_lines[i+1:]
                break
        else:
            raise NoIntersect('No test lines intersect both contours.')

        for line in test_lines:
            if opposite_signs(last_line.score, line.score):
                # Found it!
                break
            else:
                last_line = line
        else:
            raise ValueError('no good line pair found')

        #print '******** found it! angle 1/2 =', degrees(last_line.angle), degrees(line.angle)
        #print ' score 1,2 =', degrees(last_line.score), degrees(line.score)

        x_line = self._optimize(last_line, line)

        # trim line to contours
        iter_points = list(self._x_points(x_line))
        short_line = gt.ADPolyline(vertices=iter_points)
        return short_line

    def _optimize(self, x_line1, x_line2):
        """
        Recursively find best angle-balanced crossing line between self.left_line and self.right_line
        Global angle_tol is used to determine when the line is balanced enough
        :param x_line1: ADPolyline - crossing line (with x_line.score and x_line.angle)
        :param x_line2: ADPolyline - crossing line (with x_line.score and x_line.angle)
        :return:  ADPolyline
        """
        # Create and rate line betwen x_line1 and x_line2
        self.iterations += 1

        new_angle = (x_line2.angle + x_line1.angle)/2
        test_line = line_at_angle(self.start_pt, new_angle, self.length, back_length=self.back_length)
        test_line.angle = new_angle
        test_line.score = self._rate_line(test_line)

        #print 'angle=', degrees(test_line.angle), 'score=', degrees(test_line.score)

        if DEBUG_OPTIMIZE:
            test_line.plot(color='red')
            test_line.label(text=str(self.iterations)+'/'+str(round(degrees(test_line.score), 1)), reverse=True)

        # See if the line is good
        if abs(test_line.score) < angle_tol:
            #test_line.plot(color='black')
            #test_line.label(text='GOOD/' + str(round(degrees(test_line.score), 1)), reverse=True)
            return test_line

        # If past max iterations, return best line
        # TODO - while this is acceptable, there should be some check that things are converging around a point,
        # TODO - e.g. a test that enough iterations happened that the angular diff between lines is acceptable
        if self.iterations > self.max_iters:
            #raise MaxIterations('Exceeded ' + str(self.max_iters) + ' while optimizing.')
            scores = [x_line1, test_line, x_line2]
            scores.sort(key=lambda x: abs(x.score))
            return scores[0]

        # Pick best pair and recurse
        if opposite_signs(x_line1.score, test_line.score):
            return self._optimize(x_line1, test_line)
        else:
            return self._optimize(test_line, x_line2)

#    def _rate_line(self, test_line):
#        """
#        Calculates score for test_line between right and left contours
#        :param test_line: ADPolyline
#        :return: score - float (radians)
#        """
#        try:
#            a, b = self._intersect_angles(test_line)
#            if DEBUG_RATE_LINE:
#                print 'left/right angles:', round(degrees(a), 1), round(degrees(b), 1), 'at iterations', self.iterations
#                print 'score = ', round(degrees(a-b), 1)
#        except NoIntersect as e:
#            # print 'No intersect:', e
#            return radians(BADSCORE)
#        return a - b
#
#    def _intersect_angles(self, x_line):
#        """
#        Returns the interior, "downstream", angles formed by left_line/x_line and right_line/x_line
#        Raises NoIntersect if a line doesn't cross
#        :param x_line: ADPolyline - line crossing both contours
#        :return:  (float, float) - left angle (radians), right angle (radians)
#        """
#        def positive(angle):
#            """ Returns angle, adjusted to be positive"""
#            if angle < 0.0:
#                return angle + 2*pi
#            else:
#                return angle
#
#        left_inter_pt, right_inter_pt = self._x_points(x_line)
#
#        _, left_br_point = self.left_line.bracket(left_inter_pt)
#        _, right_br_point = self.right_line.bracket(right_inter_pt)
#
#        # left_angle
#        theta1 = left_inter_pt.angle(left_br_point)
#        theta2 = left_inter_pt.angle(right_inter_pt)
#        theta_left = positive(theta1 - theta2)
#
#        # right_angle
#        theta1 = right_inter_pt.angle(right_br_point)
#        theta2 = right_inter_pt.angle(left_inter_pt)
#        theta_right = positive(theta2 - theta1)
#        return theta_left, theta_right

    def _rate_line(self, test_line):
        """
        Calculates score for test_line between right and left contours
        :param test_line: ADPolyline
        :return: score - float (radians)
        """
        try:
            a, b = self._intersect_angles(test_line)
            if DEBUG_RATE_LINE:
                print 'left/right angles:', round(degrees(a), 1), round(degrees(b), 1), 'at iterations', self.iterations
                print 'score = ', round(degrees(a-b), 1)
        except NoIntersect as e:
            # print 'No intersect:', e
            return radians(BADSCORE)
        return a - b

    def _intersect_angles(self, x_line):
        """
        Returns the difference between interior "downstream" and "upstream" angles formed by left_line/x_line and
        right_line/x_line. Raises NoIntersect if a line doesn't cross
        :param x_line: ADPolyline - line crossing both contours
        :return:  (float, float) - left angle difference (radians), right angle difference (radians)
        """
        def positive(angle):
            """ Returns angle, adjusted to be positive"""
            if angle < 0.0:
                return angle + 2*pi
            else:
                return angle

        left_inter_pt, right_inter_pt = self._x_points(x_line)

        up_left_br_point , dn_left_br_point = self.left_line.bracket(left_inter_pt)
        up_right_br_point , dn_right_br_point = self.right_line.bracket(right_inter_pt)

        # left downstream angle
        theta1 = left_inter_pt.angle(dn_left_br_point)
        theta2 = left_inter_pt.angle(right_inter_pt)
        theta_left_dn = positive(theta1 - theta2)

        # left upstream angle
        theta1 = left_inter_pt.angle(right_inter_pt)
        theta2 = left_inter_pt.angle(up_left_br_point)
        theta_left_up = positive(theta1 - theta2)
        theta_left = theta_left_dn - theta_left_up

        # right downstream angle
        theta1 = right_inter_pt.angle(dn_right_br_point)
        theta2 = right_inter_pt.angle(left_inter_pt)
        theta_right_dn = positive(theta2 - theta1)

        # right upstream angle
        theta1 = right_inter_pt.angle(left_inter_pt)
        theta2 = right_inter_pt.angle(up_right_br_point)
        theta_right_up = positive(theta2 - theta1)
        theta_right = theta_right_dn - theta_right_up

        return theta_left, theta_right

    def _x_points(self, x_line):
        """
        Intersects x_line with left_contour and right contour and returns intersection points. If multiple intersects,
        determines correct points using self.start_pt
        :param x_line: ADPolyine
        :return: left_inter_pt, right_inter_pt - ADPoint, ADPoint
        """
        right_inter_pt = self.right_line.intersection(x_line)
        if right_inter_pt is None:
            raise NoIntersect('right_line does not intersect x_line')
        left_inter_pt = self.left_line.intersection(x_line)
        if left_inter_pt is None:
            raise NoIntersect('left_line does not intersect x_line')

        # check for multiple intersections
        if type(right_inter_pt) is list or type(left_inter_pt) is list:
            left_inter_pt, right_inter_pt = self._smart_intersect(left_inter_pt, right_inter_pt, x_line)
        return left_inter_pt, right_inter_pt

    def _smart_intersect(self, left_inters, right_inters, x_line):
        """
        Finds "best" intersections out of left_inters and right_inters. Called by self._x_points() in case of multiple
        intersections
        :param left_inters: ADPoint, or list of ADPoints - intersections between x_line and self.left_contour
        :param right_inters: ADPoint, or list of ADPoints - intersections between x_line and self.right_contour
        :param x_line: ADPolyline - crossing line that created left_inters and right_inters
        :return: ADPoint, ADPoint - left, rigtht
        """
        # Process left points and measure position along x_line
        points = []
        if type(left_inters) is list:
            for pt in left_inters:
                pt.pos = x_line.project(pt)
                pt.side = 'left'
                points.append(pt)
        elif type(left_inters) is gt.ADPoint:
            left_inters.pos = x_line.project(left_inters)
            left_inters.side = 'left'
            points.append(left_inters)
        elif type(left_inters) is gt.ADPolyline:
            raise ALException('_smart_intersect got ADPolyline passed for left_inters.')
        else:
            raise ALException('_smart_intersect got unknown type passed for left_inters.')

        # Process right points and measure position along x_line
        if type(right_inters) is list:
            # list of points
            for pt in right_inters:
                pt.pos = x_line.project(pt)
                pt.side = 'right'
                points.append(pt)
        elif type(right_inters) is gt.ADPoint:
            # single point
            right_inters.pos = x_line.project(right_inters)
            right_inters.side = 'right'
            points.append(right_inters)
        elif type(left_inters) is gt.ADPolyline:
            raise ALException('_smart_intersect got ADPolyline passed for left_inters.')
        else:
            raise ALException('_smart_intersect got unknown type passed for left_inters.')

        # Sort points by distance along x_line
        points.sort(key=lambda x: x.pos)

        if DEBUG_RATE_LINE:
            print len(points), ' points'
            for pt in points:
                print pt, pt.side

        pt1 = None; pt2 = None

        # Check if first point is self.start_pt
        if self.start_pt.distance_to(points[0]) < tolerance:
            pt1 = points[0]
            pt2 = points[1]
        # Check if last point is self.start_pt
        elif self.start_pt.distance_to(points[-1]) < tolerance:
            pt1 = points[-1]
            pt2 = points[-2]
        # Somewhere in the middle
        else:
            for i in range(1, len(points)-1):
                # find point at same spot as self.start_pt
                if points[i].distance_to(self.start_pt) < tolerance:
                    pt1 = points[i]
                    if points[i-1].side != self.side:
                        pt2 = points[i-1]
                    elif points[i+1].side != self.side:
                        pt2 = points[i+1]
                    else:
                        # Should never get here
                        raise ALException('should never get here, not right')

        # Look out for no intersect case, cause weird line angle and shapley behaving weirdly
        if pt1 is None and pt2 is None:
            raise NoIntersect('self.start_pt is not in intersects. Bad line.')

        assert pt1 is not None or pt2 is not None

        # Return points left first, then right
        if self.side == 'left':
            return pt1, pt2
        else:
            return pt2, pt1


def opposite_signs(a, b):
    """
    Returns True is a and b have opposite signs (+/-) otherwise false
    :param a: float or int
    :param b: float or int
    :return: boolean
    """
    if a < 0 < b:
        return True
    elif a > 0 > b:
        return True
    else:
        return False


# TODO: If start_pt is a vertex, don't use the bracketing vertices, use the angles of the segments adjacent to the
# start_pt
def perpendicular_line(start_pt, orig_line, length, direction='right', return_angle=False, back_length=0):
    """
    Returns a line starting at start_pt, perpendicular to 'line' at segment intersected by start_pt. If start_pt is
    at a vertex of orig_line, the angle between the vertices before and after start_pt is used to create the
    perpendicular line.
    :param start_pt: ADPoint - start of line
    :param orig_line: line that is drawn perpendicular to
    :param length:  length of new line
    :param direction: 'right' or 'left', direction perp line is drawn from orig, facing towards the end of orig_line
    :param return_angle:  bool - True, returns angle after ADPolyline
    :param back_length: float, passed to line_at_angle()
    :return: ADPolyline, (angle) - perpendicular line, (angle of line (radians))
    """
    direction = direction.lower()
    if direction.lower() != 'right' and direction.lower() != 'left':
        raise AttributeError("direction must be 'left' or 'right'")

    if abs(orig_line.distance_to(start_pt)) > tolerance:
        raise AttributeError('start_pt is not on orig_line')

    back_pt, front_pt = orig_line.bracket(start_pt)
    angle = back_pt.angle(front_pt)

    if direction == 'right':
        angle -= radians(90)
    else:
        angle += radians(90)

    if return_angle:
        return line_at_angle(start_pt, angle, length, back_length=back_length), angle
    else:
        return line_at_angle(start_pt, angle, length, back_length=back_length)


def line_at_angle(start_pt, angle, length, back_length=0):
    """
    Creates ADPolyline starting at start_pt, in direction, for length.
    Returned line goes past start_pt for a distance of back_length in the opposite of direction
    for intersection purposes
    :param start_pt: ADPoint
    :param angle: direction in radians. 0 is right, 90 is up
    :param length: length, float
    :return: ADPolyline
    """
    start_x = start_pt.X - cos(angle)*back_length
    start_y = start_pt.Y - sin(angle)*back_length
    end_x = cos(angle)*length + start_pt.X
    end_y = sin(angle)*length + start_pt.Y

    start_pt = gt.ADPoint(X=start_x, Y=start_y)
    end_pt = gt.ADPoint(X=end_x, Y=end_y)
    return gt.ADPolyline(vertices=[start_pt, end_pt])

