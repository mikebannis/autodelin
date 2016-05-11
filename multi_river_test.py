import autodelin.interface as ad
import autodelin.logic as logic
from datetime import datetime as dt
from matplotlib import pyplot


def main():
    first_now = dt.now()
    mgr = ad.Manager()

    # Import all values
    mgr.import_bfes('GHC/GHC_bfe.shp')
    mgr.import_xs('GHC/GHC_XS.shp')
    mgr.import_extents('GHC/all_extents.shp', '100-yr')
    mgr.import_multi_river('GHC/GHC_all_rivers.shp', 'RiverCode', 'ReachCode')

    mgr.select_river('Mainstem', 'Carpenter')
    mgr.merge_bfe_and_xs()
    mgr.select_bfe_xs()
    mgr.calc_stations()
    mgr.sort_bfe_and_xs()

    mgr.import_contours('GHC/GHC_full_contours.shp', 'ContourEle', chatty=True)

    #mgr.trim_bfe_xs(start=5140, end=5100)
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
