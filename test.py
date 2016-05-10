import autodelin.interface as ad
import autodelin.logic as logic
from datetime import datetime as dt
from matplotlib import pyplot


def main():
    first_now = dt.now()
    mgr= ad.Manager()
    mgr.bfe_file = 'GHC/carp_bfe.shp'
    mgr.contour_file = 'GHC/middle_contour.shp'
    mgr.contour_elev_field = 'ContourEle'
    mgr.ext_file = 'GHC/all_extents.shp'
    mgr.ext_profile = '100-yr'
    mgr.river_file = 'GHC/ghc_mainstem.shp'
    mgr.xs_file = 'GHC/carp_XS.shp'

    crs = mgr.get_crs(mgr.contour_file)

    combo_list, contours = mgr.import_all()
    #combo_list = d.trim_bfe_xs(combo_list, start=5140, end=5100)
    #combo_list = d.trim_bfe_xs(combo_list, start=5128, end=5130)

    if False:
        for item in combo_list:
            if type(item) is logic.BFE:
                item.geo.plot(color='red')
                item.river_intersect.plot(marker='o')
                item.river_intersect.label(str(item.elevation))

    now = dt.now()
    l, r = logic.delineate(combo_list, contours)
    print 'Drew', len(combo_list), 'segements in ', (dt.now() - now)/len(combo_list), ' per segemnt'
    #d.plot_boundary(l, r)
    print 'Imports and delineation in ', (dt.now() - first_now)

    boundary = l + r
    mgr.export_boundary(boundary, 'out.shp', crs)
    pyplot.show()


if __name__ == '__main__':
    main()
