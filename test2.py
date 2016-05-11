import autodelin.interface as ad
import autodelin.logic as logic
from datetime import datetime as dt
from matplotlib import pyplot


def main():
    first_now = dt.now()
    mgr = ad.Manager()

    # Import all values
    mgr.import_bfes('GHC/carp_bfe.shp')
    mgr.import_xs('GHC/carp_XS.shp')
    mgr.import_contours('GHC/GHC_full_contours.shp', 'ContourEle')
    mgr.import_extents('GHC/all_extents.shp', '100-yr')
    mgr.import_single_river('GHC/ghc_mainstem.shp')
    mgr.calc_bfe_stations()
    mgr.calc_xs_stations()
    mgr.merge_bfe_and_xs()

    mgr.trim_bfe_xs(start=5140, end=5100)
    #combo_list = d.trim_bfe_xs(combo_list, start=5128, end=5130)

    if False:
        for item in combo_list:
            if type(item) is logic.BFE:
                item.geo.plot(color='red')
                item.river_intersect.plot(marker='o')
                item.river_intersect.label(str(item.elevation))

    now = dt.now()
    l, r = mgr.run_single_reach()
    print 'Drew', len(mgr.combo_list), 'segements in ', (dt.now() - now)/len(mgr.combo_list), ' per segemnt'
    #d.plot_boundary(l, r)
    print 'Imports and delineation in ', (dt.now() - first_now)

    boundary = l + r
    mgr.export_boundary(boundary, 'out.shp')
    #pyplot.show()


if __name__ == '__main__':
    main()
