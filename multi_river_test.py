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
    mgr.import_contours('GHC/GHC_full_contours.shp', 'ContourEle', chatty=True)

    rivers = [('South Trib', 'South Trib'), ('Mainstem', 'Carpenter'), ('Mainstem', 'Middle')]

    boundary = []
    for river, reach in rivers:
        mgr.select_river(river, reach)
        mgr.merge_bfe_and_xs()
        mgr.select_bfe_xs()
        mgr.calc_stations()
        mgr.sort_bfe_and_xs()
        l, r = mgr.run_single_reach()
        boundary += l
        boundary += r
        mgr.reset_combo_list()

    print 'Imports and delineation in ', (dt.now() - first_now)

    mgr.export_boundary(boundary, 'out.shp')


if __name__ == '__main__':
    main()
# if True:
    #     print 'combo_list contains:'
    #     for item in mgr.combo_list:
    #         print 'name=', item.name, '

    # mgr.trim_bfe_xs(start=5140, end=5100)
    # #combo_list = d.trim_bfe_xs(combo_list, start=5128, end=5130)
    #
    # if False:
    #     for item in combo_list:
    #         if type(item) is logic.BFE:
    #             item.geo.plot(color='red')
    #             item.river_intersect.plot(marker='o')
    #