import fiona
from shapely.geometry import shape
from matplotlib import pyplot
from math import degrees

import sys
sys.path.insert(0, './..')
import autodelin.angle_line as al
import autodelin.geo_tools as gt

print 'past imports'

def main():
    left_filename = 'shapes/left.shp'
    right_filename = 'shapes/right.shp'
    start_filename = 'shapes/start.shp'
    test1_filename = 'shapes/test1.shp'

    with fiona.collection(left_filename, 'r') as input_file:
        for feature in input_file:
            geo = shape(feature['geometry'])
            #            if type(geo) is MulthiLineString:
            #                raise ShapefileError('bfe ' + str(elev) + ' appears to be a multipart feature.')
            left_line = gt.ADPolyline(shapely_geo=geo)

    with fiona.collection(right_filename) as input_file:
        for feature in input_file:
            geo = shape(feature['geometry'])
            right_line = gt.ADPolyline(shapely_geo=geo)

    start_pts = []
    with fiona.collection(start_filename) as input_file:
        for feature in input_file:
            geo = shape(feature['geometry'])
            start_pt = gt.ADPoint(shapely_geo=geo)
            print str(start_pt)
            start_pts.append(start_pt)

    with fiona.collection(test1_filename) as input_file:
        for feature in input_file:
            geo = shape(feature['geometry'])
            test1_line = gt.ADPolyline(shapely_geo=geo)

    print 'left line=', left_line
    print 'right line = ', right_line
    print 'test line = ', test1_line


   # l_intersect = left_line.intersection(test1_line)
   # pointa, pointb = left_line.bracket(l_intersect)
   # pointa.plot(marker='x')
   # pointb.plot(marker='o')

   # r_intersect = right_line.intersection(test1_line)
   # pointa, pointb = right_line.bracket(r_intersect)
   # pointa.plot(marker='x')
   # pointb.plot(marker='o')

    left_line.plot(color='red')
    right_line.plot(color='blue')
    #r_intersect.plot(marker='o')
    #l_intersect.plot(marker='o')
    # test1_line.plot(color='black')
   # test = al.perpendicular_line(start_pt, right_line, 2000, direction='right')
   # test2 = al.perpendicular_line(start_pt, right_line, 2000, direction='left')
   # test.plot()
   # test2.plot()


    #theta_l, theta_r = al.intersect_angles(left_line, right_line, test1_line)
    #print degrees(theta_l), degrees(theta_r)
    print 'start_pts is this many', len(start_pts)
    for start_pt in start_pts:
        al.optimized_x_line(left_line, right_line, start_pt, 1000)
        start_pt.plot(marker='o')

    pyplot.axes().set_aspect('equal', 'datalim')
    pyplot.show()


if __name__ == '__main__':
    main()
