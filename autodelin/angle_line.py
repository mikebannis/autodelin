from numpy import arange
import geo_tools
from math import pi, radians, cos, sin, degrees

tolerance = 0.001  # tolerance for determining if points are on line


class NoIntersect(Exception):
    pass


def optimized_x_line(left_line, right_line, start_pt, length, spread=0.75*pi, initial_tests=7):
    """
    Creates angle optimized crossing line between left_line and right_line, starting at start_pt. start_pt must be
    on right or left_line.
    :param left_line: ADPolyline
    :param right_line: ADPolyline
    :param start_pt: ADPoint
    :param length: float - length of x_line
    :param spread: float - width of fan for initial search
    :param initial_tests - number of lines for initial search. this is rounded up if even to an odd number
    :return: ADPolyline
    """
    if abs(left_line.distance_to(start_pt)) < tolerance:
        side = 'left'
    elif abs(right_line.distance_to(start_pt)) < tolerance:
        side = 'right'
    else:
        raise AttributeError('start_pt is not on left_line or right_line')

    # Create perpendicular (first) line
    if side == 'left':
        perp_line, perp_angle = perpendicular_line(start_pt, left_line, length, direction='right', return_angle=True)
    else:
        perp_line, perp_angle = perpendicular_line(start_pt, right_line, length, direction='left', return_angle=True,
                                                   back_length=1)

    # Ensure initial tests is odd
    if initial_tests % 2 == 0:
        initial_tests += 1

    # --------- Create initial lines
    angle_step = spread / (initial_tests - 1)
    start = perp_angle - spread/2.0
    end = perp_angle + spread/2.0 + angle_step
    test_lines = []
    # Create lines clockwise of perp line
    for angle in arange(start, perp_angle, angle_step):
        temp_line = line_at_angle(start_pt, angle, length, back_length=1)
        test_lines.append(temp_line)
    # Add perp line
    test_lines.append(perp_line)
    # Create lines CCW of perp_line
    for angle in arange(perp_angle+angle_step, end, angle_step):
        temp_line = line_at_angle(start_pt, angle, length, back_length=1)
        test_lines.append(temp_line)

    for i, line in enumerate(test_lines):
        print 'test line:', i
        score = rate_line(left_line, right_line, line)
        line.label(text=str(i)+'/'+str(round(degrees(score), 0)), reverse=True)
        line.plot()

    # iterate until line is optimized


def rate_line(left_line, right_line, test_line):
    """
    
    :param left_line:
    :param right_line:
    :param test_line:
    :return:
    """
    try:
        a, b = intersect_angles(left_line, right_line, test_line)
        print degrees(a), degrees(b)
    except NoIntersect as e:
        print 'no intersect', e
        return radians(999)
    return a - b


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
