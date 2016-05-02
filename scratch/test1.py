import autodelin.logic as ad
from matplotlib import pyplot
from datetime import datetime as dt
import fiona
from shapely.geometry import mapping


def trim_bfe_xs(bfe_xs_list, start=None, end=None):
    """

    :param bfe_xs_list:
    :param contours:
    :param start: highest elevation bfe to use
    :param end: lowest elevation bfe to use
    :return: lists of left and right boundary
    """
    new_bfe_xs_list = []
    flag = 'out'
    for bfe_xs in bfe_xs_list:
        if bfe_xs.name == start:
            flag = 'in'
            new_bfe_xs_list.append(bfe_xs)
        elif flag == 'in' and bfe_xs.name != end:
            new_bfe_xs_list.append(bfe_xs)
        elif bfe_xs.name == end:
            new_bfe_xs_list.append(bfe_xs)
            break
        #print 'bfe_xs.name=', bfe_xs.name,'start=', start,'end=', end
    return new_bfe_xs_list


def main():
    first_time = dt.now()

    out_filename = 'GHC/carp_boundary.shp'
    river = ad.ez_river_import('GHC/ghc_mainstem.shp')

    xss = ad.ez_xs_import('GHC/carp_XS.shp', 'ProfileM')
    bfes = ad.ez_bfe_import('GHC/carp_bfe.shp', 'Elevation')

    ad.calc_xs_stations(xss, river)
    ad.ez_extents_import('GHC/all_extents.shp', 'XS_ID', 'Position', 'Profile', '100-yr', 'Elevation', xss)
    ad.calc_bfe_stations(bfes, river)

    print 'importing contours... '

    # contour_filename = 'shapes/carp_contour_clip.shp'
    contour_filename = 'GHC/middle_contour.shp'
    contours = ad.import_contours(contour_filename, 'ContourEle', chatty=True)
    crs = ad.get_crs(contour_filename)
    print 'Contours imported. Drawing'
    if not True:
        for contour in contours:
            contour.plot(color='grey')
    print 'Done drawing contours'

    for bfe in bfes:
        bfe.geo.plot(color='red')
        bfe.river_intersect.plot(marker='o')
        bfe.river_intersect.label(str(bfe.elevation))

    combo_list = ad.merge_bfe_and_xs(bfes, xss)


    # for x in combo_list:
    #     print x.station, type(x), x.elevation

    for xs in combo_list:
        if type(xs) is not ad.CrossSection:
            continue
        #print xs.id
        xs.geo.plot(color='black')
        xs.river_intersect.plot(marker='o')
        xs.river_intersect.label(str(xs.id))
        xs.left_extent.plot(marker='o')
        xs.right_extent.plot(marker='^')
        # posi, _, _ = ad._calc_extent_position(xs, xs.left_extent, contours)
        # xs.left_extent.label(str(round(posi, 2)))
        # posi, _, _ = ad._calc_extent_position(xs, xs.right_extent, contours)
        # xs.right_extent.label(str(round(posi, 2)))

    combo_list = combo_list[::-1]

    # ------------------------ Delineate boundary -----------------------------------
    now = dt.now()
    combo_list = trim_bfe_xs(combo_list, start=5140, end=5156)
    # combo_list = trim_bfe_xs(combo_list, start=114934, end=5150)
    left_bound, right_bound = ad.delineate(combo_list, contours)
    time = dt.now() - now
    print 'done in', time
    print len(combo_list), 'BFE/XS completed in ', (time/len(combo_list)), 'per item'


    # print len(left_bound)
    for i, line in enumerate(left_bound):
         if i % 2 == 0:
             line.plot(color='blue', linewidth=2)
         else:
             line.plot(color='pink', linewidth=2)

    # print len(right_bound)
    for i, line in enumerate(right_bound):
         if i % 2 == 0:
             line.plot(color='blue', linewidth=2)
         else:
             line.plot(color='pink', linewidth=2)

    print 'total process complete in', (dt.now() - first_time)

    pyplot.axes().set_aspect('equal', 'datalim')
    #river.plot()
    pyplot.show()

    # Export to shapefile
    print 'Exporting to shapefile'
    schema = {'geometry': 'LineString', 'properties': {'status': 'str:25'}}
    with fiona.open(out_filename, 'w', driver='ESRI Shapefile', crs=crs, schema=schema) as out:
        for left in left_bound:
            out.write({'geometry': mapping(left.shapely_geo), 'properties': {'status': 'asdf'}})
        for right in right_bound:
            out.write({'geometry': mapping(right.shapely_geo), 'properties': {'status': 'asdf'}})
    print 'Finished exporting to shapefile'

if __name__ == '__main__':
    main()
