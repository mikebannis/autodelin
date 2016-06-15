import autodelin.interface as ad
import autodelin.logic as logic
from datetime import datetime as dt
from matplotlib import pyplot

def main():
    first_now = dt.now()
    mgr = ad.Manager()


    # Import all values
    mgr.workers = 2
    mgr.import_bfes('GHC/GHC_bfe.shp')
    mgr.import_xs('GHC/GHC_XS.shp')
    mgr.import_extents('GHC/all_extents.shp', '100-yr')
    mgr.import_multi_river('GHC/GHC_all_rivers.shp', 'RiverCode', 'ReachCode')
    mgr.import_contours('GHC/GHC_full_contours.shp', 'ContourEle', chatty=True)

    # rivers = [('South Trib', 'South Trib'), ('Mainstem', 'Carpenter'), ('Mainstem', 'Middle')]
    rivers = [('Mainstem', 'Carpenter'), ('Mainstem', 'Middle')]
    #rivers = ('Mainstem', 'Valente')
    rivers = [('Mainstem', 'Middle')]
    boundary = mgr.run_multi_reach(rivers)
    #boundary = mgr.run_named_reach_trim(rivers, start=5105, end=5108)
    #boundary = mgr.run_all_reaches()

    print 'length results=', len(boundary)
    print boundary

    print 'Imports and delineation in ', (dt.now() - first_now)

#    boundary = [x for single_result in results for x in single_result]
    mgr.export_boundary(boundary, 'out.shp')
    #pyplot.show()

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