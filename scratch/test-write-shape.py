import autodelin as ad
from matplotlib import pyplot
from datetime import datetime as dt
from shapely.geometry import mapping
import fiona


def get_bfe(bfes, contours, start=None, end=None):
    """
    Run ad.delineate_by_bfes for all bfes between elevations start and end (inclusive)
    Ignores reaches and rivers.
    :param bfes:
    :param contours:
    :param start: highest elevation bfe to use
    :param end: lowest elevation bfe to use
    :return: lists of left and right boundary
    """
    if start is None and end is None:
        left_bound, right_bound = ad.delineate_by_bfes(bfes, contours)
    else:
        new_bfes = []
        for bfe in bfes:
            if start >= bfe.elevation >= end:
                new_bfes.append(bfe)
        left_bound, right_bound = ad.delineate_by_bfes(new_bfes, contours)
    return left_bound, right_bound


def main():
    pyplot.figure(figsize=(15, 9))

    # contour_file = 'shapes/contour_dislv.shp'
    bfe_filename = 'GHC/riverdale_bfe.shp'
    contour_filename = 'GHC/middle_contour.shp'
    out_filename = 'GHC/test_riverdale2.shp'

    bfe_elev_field = 'Elevation'
    contour_elev_field = 'ContourEle'

    bfe_filename = 'BDC/nobles_bfe.shp'
    contour_filename = 'BDC/nobles_contour.shp'
    out_filename = 'BDC/nobles_test.shp'
    bfe_elev_field = 'Elevation'
    contour_elev_field = 'Elevation'

    print 'importing contours... '
    now = dt.now()
    contours = ad.import_contours(contour_filename, contour_elev_field)
    crs = ad.get_crs(contour_filename)
    print crs

    time_diff = dt.now() - now
    print 'Imported', len(contours), 'contours in', time_diff, 'seconds'

    bfes = ad.ez_bfe_import(bfe_filename, bfe_elev_field)

    if True:
        for contour in contours:
            contour.plot(color='grey')
    for bfe in bfes:
        bfe.plot(color='red')

    start = 5150
    end = 5140
    now = dt.now()
    if True:
        left_lines, right_lines = ad.delineate_by_bfes(bfes, contours)
    else:
        left_lines, right_lines = get_bfe(bfes, contours, start=start, end=end)
    time_diff = dt.now() - now

    for i in left_lines:
        i.plot('blue')
    for j in right_lines:
        j.plot('blue')

    print str(start-end), 'bfe pairs completed in ',  time_diff
    print time_diff/(start-end), 'seconds per bfe pair'

    pyplot.axes().set_aspect('equal', 'datalim')
    #pyplot.ylim([1202000, 1203000])
    pyplot.show()

    if not True:
        schema = {'geometry': 'LineString', 'properties': {'status': 'str:25'}}
        with fiona.open(out_filename, 'w', driver='ESRI Shapefile', crs=crs, schema=schema) as out:
            for left in left_lines:
                out.write({'geometry': mapping(left.shapely_geo), 'properties': {'status': left.status}})
            for right in right_lines:
                out.write({'geometry': mapping(right.shapely_geo), 'properties': {'status': right.status}})


if __name__ == '__main__':
    main()

