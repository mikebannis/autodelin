import fiona
from shapely.geometry import shape
from matplotlib import pyplot
from math import degrees

import sys
sys.path.insert(0, './..')
import autodelin.angle_line as al
import autodelin.geo_tools as gt


def main():
    left_filename = 'shapes/left2A.shp'
    right_filename = 'shapes/right2A.shp'
    start_filename = 'shapes/start.shp'
    test1_filename = 'shapes/test1.shp'

    print 'importing shapefiles...',

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
            #print str(start_pt)
            start_pts.append(start_pt)

    with fiona.collection(test1_filename) as input_file:
        for feature in input_file:
            geo = shape(feature['geometry'])
            test1_line = gt.ADPolyline(shapely_geo=geo)
    
    print 'Done.'

    if not True:
        print 'left line=', left_line
        print 'right line = ', right_line
        print 'test line = ', test1_line

    left_line.plot(color='red')
    right_line.plot(color='blue')

    test2(left_line, right_line)


def test3(left_line, right_line):
    print '-'*20+' left line vertices'

    vertex = left_line.vertices[9]
    vertex.plot(marker='o')
    bxl = al.BetterXLine(left_line, right_line, vertex)
    bxl.length = 4000
    best_line = bxl.create()

    best_line.plot(color='yellow')
    pyplot.axes().set_aspect('equal', 'datalim')
    pyplot.show()


def test2(left_line, right_line):
    """
    Draw all xlines from vertices on both contours
    """
    if True:

        print '-'*20+' right line vertices', len(right_line.vertices)
        for i, vertex in enumerate(right_line.vertices[:500]):
            print 'processing #', i
            bxl = al.BetterXLine(left_line, right_line, vertex)
            bxl.length = 4000
            try:
                best_line = bxl.create()
            except Exception as e:
                print 'EXCEPTION at vertex', i, e
                vertex.plot(marker='o')
                vertex.label(str(i))
            except AssertionError as e:
                print 'ASSERTION ERROR at vertex', i, e
                vertex.plot(marker='o')
                vertex.label(str(i))
            else:
                best_line.plot(color='black')

    if not True:
        print '-'*20+' left line vertices'
        for i, vertex in enumerate(left_line.vertices):
            bxl = al.BetterXLine(left_line, right_line, vertex)
            bxl.length = 4000
            try:
                best_line = bxl.create()
            except Exception as e:
                print 'EXCEPTION at vertex', i, e
                vertex.plot(marker='o')
                vertex.label(str(i))
            else:
                best_line.plot(color='orange')
    pyplot.axes().set_aspect('equal', 'datalim')
    pyplot.show()


def test1(left_line, right_line, start_pts):
    print 'start_pts is this many', len(start_pts)
    #skip_list = [0, 2, 4, 5]
    skip_list = []
    do_list = [0, 1, 2, 3, 4, 5,6,7,8]
    do_list = [ 6 ]
    for i, start_pt in enumerate(start_pts):
        if i in skip_list:
            continue
        if i not in do_list:
            continue
        start_pt.plot(marker='o')
        start_pt.label(str(i))
        print '-'*30+'start_ptn #', i

        bxl = al.BetterXLine(left_line, right_line, start_pt)
        bxl.length = 4000
        bxl.max_iters = 20
        if not True:
            best_line = bxl.create()
            print 'best_line successfully created'
            best_line.plot(color='black')
        else:
            try:
                best_line = bxl.create()
                print 'best_line successfully created'
                best_line.plot(color='black')
            except Exception as e:
                print 'caught execption in test1:', e
    pyplot.axes().set_aspect('equal', 'datalim')
    pyplot.show()

if __name__ == '__main__':
    main()

    # l_intersect = left_line.intersection(test1_line)
    # pointa, pointb = left_line.bracket(l_intersect)
    # pointa.plot(marker='x')
    # pointb.plot(marker='o')

    # r_intersect = right_line.intersection(test1_line)
    # pointa, pointb = right_line.bracket(r_intersect)
    # pointa.plot(marker='x')
    # pointb.plot(marker='o')

    #r_intersect.plot(marker='o')
    #l_intersect.plot(marker='o')
    # test1_line.plot(color='black')
    # test = al.perpendicular_line(start_pt, right_line, 2000, direction='right')
    # test2 = al.perpendicular_line(start_pt, right_line, 2000, direction='left')
    # test.plot()
    # test2.plot()


    #theta_l, theta_r = al.intersect_angles(left_line, right_line, test1_line)
    #print degrees(theta_l), degrees(theta_r)
