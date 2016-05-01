import autodelin.interface as ad
import autodelin.logic as logic
from datetime import datetime as dt


def main():
    d = ad.Delineate()
    d.bfe_file = 'GHC/carp_bfe.shp'
    d.contour_file = 'GHC/middle_contour.shp'
    d.contour_elev_field = 'ContourEle'
    d.ext_file = 'GHC/all_extents.shp'
    d.ext_profile = '100-yr'
    d.river_file = 'GHC/ghc_mainstem.shp'
    d.xs_file = 'GHC/carp_XS.shp'

    crs = d.get_crs(d.contour_file)

    now = dt.now()
    combo_list, contours = d.import_all()
    combo_list = d.trim_bfe_xs(combo_list, start=5140, end=5100)
    print 'Drew', len(combo_list), 'segements in ', (dt.now() - now)/len(combo_list), ' per segemnt'

    l, r = logic.delineate(combo_list, contours)
    #d.plot_boundary(l, r)

    boundary = l + r
    d.export_boundary(boundary, 'out.shp', crs)


if __name__ == '__main__':
    main()
