import logic
import geo_tools as gt
import fiona
from shapely.geometry import shape, MultiLineString, LineString, MultiPoint, Point, mapping
from matplotlib import pyplot
from collections import namedtuple


# CacheTracker = namedtuple('CachedTracker', 'geo age')
class CacheTracker(object):
    def __init__(self, age=None, geo=None):
        self.age = age
        self.geo = geo

class ShapefileError (Exception):
    pass


# Old style contours 2.18 GB, 1.36/segment
# New: 500MB, 6.3 sec/segment, 5:48 total
# Cache as needed 900MB 1.5/seg, 1:24 total
# Cache as needed, remove from cache with age 530MB 1.8sec/seg, 1:39 total

class Contours(object):
    """
    Holds a dictionary of fiona features (contours) by elevaiton. get() converts feature to Contour. Doing this on-
    the-fly is less memory intensive and faster to load, but slower to delineate.
    """
    def __init__(self, cache_age=4):
        # dictionary of either Contour or fiona feature objects keyed by elevation
        self.contours = {}
        # dictionary of CacheTrackers keyed by elevation
        self.tracker = {}
        self.cache_age = cache_age

    def get(self, elevation):
        """
        returns Contour object with elevation.
        :param elevation: int
        :return: Contour object
        """
        temp_geo = self.contours[elevation]

        # Check if cached
        if type(temp_geo) is Contour:
            return temp_geo

        # Age cache and create tracker
        self._age_cache()
        tracker = CacheTracker(age=self.cache_age, geo=temp_geo)
        self.tracker.update({elevation: tracker})

        # Force to list
        temp_geo = shape(temp_geo)
        if type(temp_geo) is MultiLineString:
            geos = list(temp_geo)
        elif type(temp_geo) is LineString:
            geos = list(MultiLineString([temp_geo]))
        else:
            raise ShapefileError('Contour file does not appear to contain lines.')

        # Convert to ADPolylines
        lines = []
        for geo in geos:
            temp_poly = gt.ADPolyline(shapely_geo=geo)
            lines.append(temp_poly)

        # Make a contour
        temp_contour = Contour(lines, elevation)

        # Cache it
        self.contours[elevation] = temp_contour
        return temp_contour

    def add(self, geo, elev):
        self.contours.update({elev: geo})

    def length(self):
        return len(self.contours)

    def _age_cache(self):
        for elev, contour in self.tracker.items():
            if contour.age == 0:
                # Remove from cache, reset fiona geo in contours
                self.contours[elev] = contour.geo
                self.tracker.pop(elev)
            contour.age -= 1


class Contour(object):
    def __init__(self, line_list, elevation):
        """
        :param line_list: list of ADPolyline objects representing a dissolved contour
        :param elevation: contour elevation
        :return: None
        """
        self.line_list = line_list
        self.elevation = elevation

        if len(line_list) == 1:
            self.multipart = False
        else:
            self.multipart = True

    def plot(self, *args, **kwargs):
        for line in self.line_list:
            line.plot(*args, **kwargs)

    def __str__(self):
        s = '['
        for line in self.line_list:
            s += '[' + str(line) + '], '
        return s[:-2]+']'

    def __repr__(self):
        return str(self)


class CrossSection(object):
    """
    Contains hec-ras cross section cutlines in ADPolyline format and water surface extents in ADPoint format
    """
    def __init__(self, geo, id):
        self.geo = geo
        self.id = id
        self.name = id
        # The following attributes are populated by module methods
        self.left_extent = None
        self.right_extent = None
        self.elevation = None
        self.station = None
        self.river_intersect = None

    def plot(self, *args, **kwargs):
        X = self.geo.first_point.X
        Y = self.geo.first_point.Y
        pyplot.annotate(str(int(self.id)), xy=(X, Y))
        self.geo.plot(*args, **kwargs)


class Delineate(object):
    def __init__(self):
        self.river_file = None

        self.xs_file = None
        self.xs_id_field = 'ProfileM'

        self.bfe_file = None
        self.bfe_elev_field = 'Elevation'

        self.ext_file = None
        self.ext_id_field = 'XS_ID'
        self.ext_pos_field = 'Position'
        self.ext_profile_field = 'Profile'
        self.ext_profile = None
        self.ext_elev_field = 'Elevation'
        self.left = 'left'
        self.right = 'right'

        self.contour_file = None
        self.contour_elev_field = 'Elevation'

        self.outfile = None

    def import_all(self):
        river = self.single_river_import()
        cross_sections = self._ez_xs_import()
        self._ez_extents_import(cross_sections)

        bfes = self._ez_bfe_import()

        contours = self._import_contours(chatty=True)

        self._calc_bfe_stations(bfes, river)
        self._calc_xs_stations(cross_sections, river)
        combo_list = self._merge_bfe_and_xs(bfes, cross_sections)

        return combo_list, contours

    def run_single_reach(self):
        """
        Delinate single reach. Assumed all features in shapefiles belong to the same reach
        :return: left list of ADpolyline boundaries, right list of Adpolyine boundaries
        """
        combo_list, contours = self.import_all()

        left_bound, right_bound = logic.delineate(combo_list, contours)
        return left_bound, right_bound

    def get_crs(self, filename):
        with fiona.collection(filename, 'r') as in_file:
            return in_file.crs

    def plot_boundary(self, left, right, color='blue'):
        for line in left:
            line.plot(color=color)
        for line in right:
            line.plot(color=color)
        pyplot.axes().set_aspect('equal', 'datalim')
        pyplot.show()

    def trim_bfe_xs(self, bfe_xs_list, start=None, end=None):
        """
        Removes BFE/cross sections that are not in between start and end
        :param bfe_xs_list:
        :param start: highest elevation bfe/cross section to use
        :param end: lowest elevation bfe to use
        :return: lists of left and right boundary
        """
        # Check for proper order
        if bfe_xs_list[0].elevation > bfe_xs_list[-1].elevation:
            # print 'BFE/cross section list appears to be in reverse order. Reversing.'
            bfe_xs_list = bfe_xs_list[::-1]

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
                # print 'bfe_xs.name=', bfe_xs.name,'start=', start,'end=', end
        return new_bfe_xs_list

    @staticmethod
    def export_boundary(boundary, out_file, crs):
        """
        Export lines in boundary to out_file
        :param boundary: list of ADPolylines
        :param out_file: name of shapefile to write
        :param crs: fiona coordinate reference system
        """
        # Check for extension
        if out_file[-4:] != '.shp':
            out_file += '.shp'

        # Export to shapefile
        schema = {'geometry': 'LineString', 'properties': {'status': 'str:25'}}
        with fiona.open(out_file, 'w', driver='ESRI Shapefile', crs=crs, schema=schema) as out:
            for line in boundary:
                out.write({'geometry': mapping(line.shapely_geo), 'properties': {'status': 'none'}})

    def _calc_bfe_stations(self, bfes, river):
        """
        Calculates BFE.stations for bfe's along river
        :param bfes: list of BFE objects
        :param river: ADPolyline object
        :return: None
        """
        for bfe in bfes:
            temp_point = river.intersection(bfe.geo)
            if type(temp_point) is MultiPoint:
                print 'BFE', bfe.elevation, 'crosses channel alignment multiple times. Aborting'
                raise
            elif temp_point is None:
                print 'BFE', bfe.elevation, 'does not cross channel alignment. Aborting.'
                raise
            bfe.river_intersect = temp_point
            bfe.station = river.project(bfe.river_intersect)

    def _calc_xs_stations(self, cross_sections, river):
        """
        Calculates CrossSection.stations for cross section along river
        :param cross_sections: list of CrossSection objects
        :param river: ADPolyline object
        :return: None
        """
        for xs in cross_sections:
            temp_point = river.intersection(xs.geo)
            if type(temp_point) is MultiPoint:
                raise ShapefileError('Cross section'+str(xs.id)+'crosses channel alignment multiple times.')
            elif temp_point is None:
                raise ShapefileError('Cross section '+str(xs.id)+' does not cross channel alignment.')
            xs.river_intersect = temp_point
            xs.station = river.project(xs.river_intersect)

    # This is hypothetical
    def _calc_xs_stations_NEW(self, cross_sections, river):
        """
        Calculates CrossSection.stations for cross section along river
        :param cross_sections: list of CrossSection objects
        :param river: ADPolyline object
        :return: None
        """
        valid_xs = []
        for xs in cross_sections:
            temp_point = river.intersection(xs.geo)
            if type(temp_point) is MultiPoint:
                raise ChannelCrossingError('Cross section'+str(xs.id)+'crosses channel alignment multiple times. Aborting')
            elif temp_point is None:
                print 'Cross section '+str(xs.id)+' does not cross channel alignment. Aborting'
                continue
            xs.river_intersect = temp_point
            xs.station = river.project(xs.river_intersect)
            valid_xs.append(xs)
        return

    def _ez_bfe_import(self):
        """
        Imports bfes from shapefile, assumes all bfes are on the same river/reach
        :return: list of BFE objects
        """
        if self.bfe_file is None:
            raise ValueError('self.river_file must be set to name of shapefile')

        bfes = []
        with fiona.collection(self.bfe_file, 'r') as input_file:
            for feature in input_file:
                elev = feature['properties'][self.bfe_elev_field]

                # Look out for duplicate BFE's
                ### REMOVE WHEN CODE IS UPDATED TO HANDLE MORE XS'S THAN NEEDED
                if any(bfe.elevation == elev for bfe in bfes):
                    continue

                # Import geometry, check for multipart features
                geo = shape(feature['geometry'])
                if type(geo) is MultiLineString:
                    raise ShapefileError( 'bfe' + str(elev) + 'appears to be a multipart feature.')
                temp_poly = gt.ADPolyline(shapely_geo=geo)
                temp_bfe = logic.BFE(temp_poly, elev)
                bfes.append(temp_bfe)
        bfes.sort(key=lambda x: x.elevation, reverse=True)
        return bfes

    def _ez_extents_import(self, cross_sections):
        """
        Imports extents with 'profile' and appends them to appropriate cross_sections
        """
        def get_xs(temp_id):
            for temp_xs in cross_sections:
                if temp_xs.id == temp_id:
                    return temp_xs

        if self.ext_file is None:
            raise ValueError('self.ext_file must be set to name of shapefile')
        if self.ext_profile is None:
            raise ValueError('self.ext_profile must be set to a RAS profile name')

        with fiona.collection(self.ext_file, 'r') as input_file:
            for feature in input_file:
                # Verify proper profile
                if feature['properties'][self.ext_profile_field] != self.ext_profile:
                    continue

                xs_id = feature['properties'][self.ext_id_field]
                position = feature['properties'][self.ext_pos_field]
                elevation = feature['properties'][self.ext_elev_field]
                temp_geo = shape(feature['geometry'])

                if type(temp_geo) is not Point:
                    print 'Extent for cross section', xs_id, 'is type', type(temp_geo), ', should be Point. Ignoring.'
                    continue

                geo = gt.ADPoint(shapely_geo=temp_geo)
                xs = get_xs(xs_id)
                if xs is None:
                    continue
                xs.elevation = elevation
                if position == self.left:
                    xs.left_extent = geo
                elif position == self.right:
                    xs.right_extent = geo
                else:
                    print 'Extent for cross section', xs_id, 'has position', position, 'which is neither', self.left, \
                        'nor', self.right, 'Ignoring.'

    def _ez_xs_import(self):
        """
        Imports hec-ras cross section cut lines from self.xs_file.
        :return: list of CrossSection objects
        """
        if self.xs_file is None:
            raise ValueError('self.river_file must be set to name of shapefile')

        cross_sections = []
        with fiona.collection(self.xs_file, 'r') as input_file:
            for feature in input_file:
                xs_id = feature['properties'][self.xs_id_field]

                # Look out and ignore duplicate XS's
                if any(xs.id == xs_id for xs in cross_sections):
                    continue

                # Fiona might give a Linestring or a MultiLineString, handle both cases
                temp_geo = shape(feature['geometry'])
                if type(temp_geo) is not LineString:
                    raise ShapefileError('Cross section' + str(xs_id) + 'is type' + str(type(temp_geo)) +
                                         ', should be LineString.')

                geo = gt.ADPolyline(shapely_geo=temp_geo)
                cross_sections.append(CrossSection(geo, xs_id))
        return cross_sections

    def _import_contours(self, chatty=False):
        """
        Imports contours from contour file, stores as list of Contour objects
        :return: list of Contour objects
        """
        if self.contour_file is None:
            raise ValueError('self.contour_file must be set to name of shapefile')

        contours = Contours()
        with fiona.collection(self.contour_file, 'r') as input_file:
            for feature in input_file:
                elev = feature['properties'][self.contour_elev_field]
                temp_geo = feature['geometry']

                # Make a contour
                contours.add(temp_geo, elev)
                if chatty:
                    if contours.length() % 25 == 0:
                        print contours.length(), 'contours imported...'
        return contours

    def _import_contours_OLD(self, chatty=False):
        """
        Imports contours from contour file, stores as list of Contour objects
        :return: list of Contour objects
        """
        if self.contour_file is None:
            raise ValueError('self.contour_file must be set to name of shapefile')

        contours = Contours()
        with fiona.collection(self.contour_file, 'r') as input_file:
            for feature in input_file:
                elev = feature['properties'][self.contour_elev_field]
                # print elev

                # Fiona might give a Linestring or a MultiLineString, handle both cases
                temp_geo = shape(feature['geometry'])
                if type(temp_geo) is MultiLineString:
                    geos = list(temp_geo)
                elif type(temp_geo) is LineString:
                    geos = list(MultiLineString([temp_geo]))
                else:
                    raise ShapefileError('Contour file does not appear to contain lines.')

                # Convert to ADPolylines
                lines = []
                for geo in geos:
                    temp_poly = gt.ADPolyline(shapely_geo=geo)
                    lines.append(temp_poly)

                #Make a contour
                temp_contour = Contour(lines, elev)
                contours.add(temp_contour)
                if chatty:
                    if contours.length() % 25 == 0:
                        print contours.length(), 'contours imported...'
        return contours

    def _merge_bfe_and_xs(self, bfes, cross_sections):
        """
        Combines list of bfes and cross sections into one list sorted by station
        :param bfes: list of BFE objects
        :param cross_sections: list of CrossSection objects
        :return: combined, sorted list of bfes and cross sections
        """
        combo_list = bfes + cross_sections
        combo_list.sort(key=lambda x: x.station)
        return combo_list

    def single_river_import(self):
        """
        imports river from river_file shapefile and returns ADPolyline
        raises exception if file has more than one feature or is not Linestring
        :return: ADPolyline
        """
        if self.river_file is None:
            raise ValueError('self.river_file must be set to name of shapefile')

        with fiona.collection(self.river_file, 'r') as input_file:
            feature = list(input_file)

            if len(feature) > 1:
                raise ShapefileError('More than one feature in river shapefile' + self.river_file)

            # Fiona might give a Linestring or a MultiLineString, handle both cases
            temp_geo = shape(feature[0]['geometry'])
            if type(temp_geo) is MultiLineString:
                raise ShapefileError('Feature in ' + str(self.river_file) + ' is MultiLineString.' +
                                     ' This is likely an error.')
            elif type(temp_geo) is LineString:
                return gt.ADPolyline(shapely_geo=temp_geo)
            else:
                raise ShapefileError('Feature in ' + self.river_file + ' is not a Linestring.')



def my_func(xs_filename, xs_id_field, bfe_filename, bfe_elev_filed, ):
    # first_time = dt.now()
    #
    # out_filename = 'GHC/carp_boundary.shp'
    # river = ad.ez_river_import('GHC/ghc_mainstem.shp')
    #
    # xss = ad.ez_xs_import('GHC/carp_XS.shp', 'ProfileM')
    # bfes = ad.ez_bfe_import('GHC/carp_bfe.shp', 'Elevation')



    # contour_filename = 'shapes/carp_contour_clip.shp'
    # contour_filename = 'GHC/middle_contour.shp'

    # print 'Contours imported. Drawing'
    # if not True:
    #     for contour in contours:
    #         contour.plot(color='grey')
    # print 'Done drawing contours'
    #
    # for bfe in bfes:
    #     bfe.geo.plot(color='red')
    #     bfe.river_intersect.plot(marker='o')
    #     bfe.river_intersect.label(str(bfe.elevation))



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