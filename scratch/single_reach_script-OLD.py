import autodelin as ad
from matplotlib import pyplot
from datetime import datetime as dt
from shapely.geometry import mapping
import fiona


def delineate(bfe_filename, bfe_elev_field, contour_filename, contour_elev_field, out_filename):
    # Import contours ------------------------------------
    print 'Importing contours... '
    now = dt.now()
    contours = ad.import_contours(contour_filename, contour_elev_field, chatty=True)
    crs = ad.get_crs(contour_filename)
    time_diff = dt.now() - now
    print 'Imported', len(contours), 'contours in', time_diff, 'seconds'

    # Import BFEs ----------------------------------------------
    bfes = ad.ez_bfe_import(bfe_filename, bfe_elev_field)
    num_bfes = len(bfes)-1
    print 'Imported bfes from', bfes[0].elevation, 'to', bfes[-1].elevation

    # Delineate ---------------------------------------------
    now = dt.now()
    left_lines, right_lines = ad.delineate_by_bfes(bfes, contours)
    time_diff = dt.now() - now
    print num_bfes, 'bfe pairs completed in ',  time_diff
    print time_diff/(num_bfes), 'seconds per bfe pair'

    # Export to shapefile
    schema = {'geometry': 'LineString', 'properties': {'status': 'str:25'}}
    with fiona.open(out_filename, 'w', driver='ESRI Shapefile', crs=crs, schema=schema) as out:
        for left in left_lines:
            out.write({'geometry': mapping(left.shapely_geo), 'properties': {'status': left.status}})
        for right in right_lines:
            out.write({'geometry': mapping(right.shapely_geo), 'properties': {'status': right.status}})
    print 'Finished exporting to shapefile'


def main():
    bfe_filename = 'GHC/riverdale_bfe.shp'
    contour_filename = 'GHC/middle_contour.shp'
    out_filename = 'GHC/riverdale_100yr_20160322C.shp'

    bfe_elev_field = 'Elevation'
    contour_elev_field = 'ContourEle'
    bfe_filename = 'BDC/nobles_bfe.shp'
    contour_filename = 'BDC/nobles_contour.shp'
    out_filename = 'BDC/nobles_test.shp'
    bfe_elev_field = 'Elevation'
    contour_elev_field = 'Elevation'

    delineate(bfe_filename, bfe_elev_field, contour_filename, contour_elev_field, out_filename)

if __name__ == '__main__':
    main()

