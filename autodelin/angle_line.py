from numpy import arange
import geo_tools
from math import pi, radians, cos, sin, degrees
from matplotlib import pyplot
import sys

tolerance = 0.001  # tolerance for determining if points are on line
angle_tol = radians(1)  # tolerance for determining angles are balanced
BADSCORE = 999


class NoIntersect(Exception):
    pass


class BetterXLine(object):
    """
    Creates and returns angle optimized crossing line between left_line and right_line starting at start_pt.
    """

    def __init__(self, left_line, right_line, start_pt):
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
        :param left_line: ADPolyline
        :param right_line: ADPolyline
        :param start_pt: ADPoint
        :param length: float - length of x_line
        :param spread: float - width of fan for initial search, in radians
        :param initial_tests - number of lines for initial search. this is rounded up if even to an odd number
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

        if True:  # DEBUG
            for i, line in enumerate(test_lines):
                print 'test line:', i
                score = self._rate_line(line)
                line.label(text=str(i)+'/'+str(round(degrees(score), 0)), reverse=True)
                line.plot()

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

        return self._optimize(last_line, line)

    def _rate_line(self, test_line):
        """
        Calculates score for test_line between right and left contours
        :param test_line: ADPolyline
        :return: score - float (radians)
        """
        try:
            a, b = intersect_angles(self.left_line, self.right_line, test_line)
            #print degrees(a), degrees(b)
        except NoIntersect as e:
            print 'No intersect:', e
            return radians(BADSCORE)
        return a - b

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
        if self.iterations > 10:
            sys.exit('exceeded iterations')

        new_angle = (x_line2.angle + x_line1.angle)/2
        test_line = line_at_angle(self.start_pt, new_angle, self.length, back_length=self.back_length)
        test_line.angle = new_angle
        test_line.score = self._rate_line(test_line)

        #print 'angle=', degrees(test_line.angle), 'score=', degrees(test_line.score)

        #x_line1.plot(color='red')
        #x_line1.label(text=str(round(degrees(x_line1.angle), 0)), reverse=True)
        #x_line2.plot(color='red')
        #x_line2.label(text=str(round(degrees(x_line2.angle), 0)), reverse=True)
        test_line.plot(color='black')
        test_line.label(text=str(round(degrees(test_line.angle), 0)), reverse=True)
        #pyplot.show()

        # See if the line is good
        if abs(test_line.score) < angle_tol:
            test_line.plot(color='black')
            test_line.label(text='*********', reverse=True)
            return test_line

        # Pick best pair and recurse
        if opposite_signs(x_line1.score, test_line.score):
            return self._optimize(x_line1, test_line)
        else:
            return self._optimize(test_line, x_line2)


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

    start_pt = geo_tools.ADPoint(X=start_x, Y=start_y)
    end_pt = geo_tools.ADPoint(X=end_x, Y=end_y)
    return geo_tools.ADPolyline(vertices=[start_pt, end_pt])


def intersect_angles(left_line, right_line, x_line):
    """
    Returns the interior, "downstream", angles formed by left_line/x_line and right_line/x_line
    Raises NoIntersect if a line doesn't cross
    :param left_line: ADPolyline - river left contour
    :param right_line:  ADPolyline - river right contour
    :param x_line: ADPolyline - line crossing both contours
    :return:  (float, float) - left angle (radians), right angle (radians)
    """
    def positive(angle):
        if angle < 0.0:
            return angle + 2*pi
        else:
            return angle

    # TODO: handle multiple intersects
    right_inter_pt = right_line.intersection(x_line)
    if right_inter_pt is None:
        raise NoIntersect('right_line does not intersect x_line')
    left_inter_pt = left_line.intersection(x_line)
    if left_inter_pt is None:
        raise NoIntersect('left_line does not intersect x_line')

    _, left_br_point = left_line.bracket(left_inter_pt)
    _, right_br_point = right_line.bracket(right_inter_pt)

    # left_angle
    theta1 = left_inter_pt.angle(left_br_point)
    theta2 = left_inter_pt.angle(right_inter_pt)
    theta_left = positive(theta1 - theta2)

    # right_angle
    theta1 = right_inter_pt.angle(right_br_point)
    theta2 = right_inter_pt.angle(left_inter_pt)
    theta_right = positive(theta2 - theta1)
    return theta_left, theta_right


def main():
    import fiona
    from shapely.geometry import mapping

    outfile = '../scratch/angle_test_out.shp'

    origin = geo_tools.ADPoint(X=0, Y=0)
    lines = []
    for angle in range(0, 360, 15):
        new_line = line_at_angle(origin, angle, 10000)
        lines.append(new_line)

    # Export to shapefile
    schema = {'geometry': 'LineString', 'properties': {'status': 'str:25'}}
    with fiona.open(outfile, 'w', driver='ESRI Shapefile', crs=None, schema=schema) as out:
        for line in lines:
            out.write({'geometry': mapping(line.shapely_geo), 'properties': {'status': 'nada'}})

if __name__ == '__main__':
    main()
