import logic
import geo_tools as gt
import fiona
from shapely.geometry import shape, MultiLineString, LineString, MultiPoint, Point, mapping
from matplotlib import pyplot
import pathos.multiprocessing as mp


class ShapefileError (Exception):
    pass

# Old style contours 2.18 GB, 1.36/segment
# New: 500MB, 6.3 sec/segment, 5:48 total
# Cache as needed 900MB 1.5/seg, 1:24 total
# Cache as needed, remove from cache with age 530MB 1.8sec/seg, 1:39 total


class Contours(object):
    """
    Holds a dictionary of fiona features (contours) by elevaiton. get() converts feature to Contour. Doing this on-
    the-fly is less memory intensive and faster to load, but slower to delineate. Includes caching with cache aging
    """
    def __init__(self, cache_age=4):
        # dictionary of either Contour or fiona feature objects keyed by elevation
        self.contours = {}
        # dictionary of CacheTrackers keyed by elevation
        self.tracker = {}
        # Number of self.get()'s that can run w/o accessing the contour before it's kicked from cache
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

        # Make a contour and cache it
        temp_contour = Contour(lines, elevation)
        self.contours[elevation] = temp_contour

        return temp_contour

    def add(self, geo, elev):
        """ adds fiona geometry to contour list"""
        self.contours.update({elev: geo})

    def length(self):
        return len(self.contours)

    def _age_cache(self):
        """ Ages all cached contours. Kicks old contours out of cache and restores fiona geo to contour list. """
        for elev, contour in self.tracker.items():
            if contour.age == 0:
                # Remove from cache, reset fiona geo in contours
                self.contours[elev] = contour.geo
                self.tracker.pop(elev)
            contour.age -= 1


class CacheTracker(object):
    """ Holds fiona geo and age of cached contour for Contours class"""
    def __init__(self, age=None, geo=None):
        """ Age and geo should NEVER be none. I'm being lazy by not checking values. """
        self.age = age
        self.geo = geo


class Contour(object):
    def __init__(self, line_list, elevation):
        """
        :param line_list: list of ADPolyline objects representing a dissolved contour
        :param elevation: contour elevation
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

    def __str__(self):
        return 'cross section-' + str(self.name)

    def __repr__(self):
        return str(self)


class River(object):
    """
    Holds river geometry and name of HEC-RAS river and reach for a single reach.
    """
    def __init__(self, geo, river, reach):
        """
        :param geo: ADPolyline - river geometry
        :param river: string - RAS river name
        :param reach: string - RAS reach name
        """
        self.geo = geo
        self.river = river
        self.reach = reach

    def matches(self, river, reach):
        if self.river == river and self.reach == reach:
            return True
        else:
            return False


class Rivers(object):
    def __init__(self):
        self.reaches = []

    def get_reach(self, river, reach):
        """
        Returns reach from self.reaches that matches river/reach
        :param river: string - name of RAS river
        :param reach: string - name of RAS reach
        :return: River object if success, else None
        """
        for test_river in self.reaches:
            if test_river.matches(river, reach):
                return test_river
                

class Manager(object):
    """
    Imports shapfiles, processes XS and BFEs. Runs the delineation code.

    INSERT EXAMPLE CODE HERE - ME!!!!!

    """
    # TODO - add example code to docstring
    def __init__(self):
        # Extent position indicators for shapefile
        # TODO - make global constant (I think)
        self.left = 'left'
        self.right = 'right'

        # Initialized in methods
        self.river = None           # River object - used with single reach
        self.rivers = None          # Rivers object - used with multiple reaches
        #self.cross_sections = None  # list of CrossSection objects
        #self.bfes = None            # list of logic.BFE objects
        self.contours = None        # Contours object
        self.crs = None             # fiona.crs object, from contours
        self.combo_list = None      # partial list of CrossSection and logic.BFE objects for the current reach
        self.full_combo_list = []  # Full list of logic.BFE and CrossSection objects

        self.workers = 0            # Number of works for SMP, 0 = no SMP

    def import_bfes(self, bfe_file, elev_field='Elevation'):
        """
        Imports bfes from shapefile,
        :param bfe_file: string - name of bfe shapefile
        :param elev_field: string - attribute field with bfe elevations
        """
        with fiona.collection(bfe_file, 'r') as input_file:
            for feature in input_file:
                elev = feature['properties'][elev_field]
                # Import geometry, check for multipart features
                geo = shape(feature['geometry'])
                if type(geo) is MultiLineString:
                    raise ShapefileError('bfe ' + str(elev) + ' appears to be a multipart feature.')
                temp_poly = gt.ADPolyline(shapely_geo=geo)
                temp_bfe = logic.BFE(temp_poly, elev)
                self.full_combo_list.append(temp_bfe)
        #self.bfes.sort(key=lambda x: x.elevation, reverse=True)

    def import_contours(self, contour_file, elev_field, chatty=False):
        """
        Imports contours from contour file. Contours are assumed to be dissolved by elevation
        :param contour_file: string - name of contour shapefile
        :param elev_field: string - attribute field with contour elevations
        :param chatty: boolean - True prints import updates to stdout
        :return: list of Contour objects
        """
        self.contours = Contours()
        with fiona.collection(contour_file, 'r') as input_file:
            # Grab coordinate reference system
            self.crs = input_file.crs
            for feature in input_file:
                elev = feature['properties'][elev_field]
                temp_geo = feature['geometry']

                # Make a contour
                self.contours.add(temp_geo, elev)
                if chatty:
                    if self.contours.length() % 25 == 0:
                        print self.contours.length(), 'contours imported...'

    def import_extents(self, ext_file, profile, id_field='XS_ID', profile_field='Profile', elev_field='Elevation',
                       pos_field='Position'):
        """
        Imports extents with 'profile' and appends them to appropriate cross_sections
        :param ext_file: string - extents shapefile name
        :param profile: string - name of profile to import
        :param id_field: string - attribute field with XS id
        :param profile_field: string - attribute field with profile
        :param elev_field: string - attribute field with XS elevation
        :param pos_field: string - attribute field with extent position
        """
        def get_xs(temp_id):
            for temp_xs in self.full_combo_list:
                if type(temp_xs) is CrossSection:
                    if temp_xs.id == temp_id:
                        return temp_xs

        with fiona.collection(ext_file, 'r') as input_file:
            for feature in input_file:
                # Verify proper profile
                if feature['properties'][profile_field] != profile:
                    continue

                xs_id = feature['properties'][id_field]
                position = feature['properties'][pos_field]
                elevation = feature['properties'][elev_field]
                temp_geo = shape(feature['geometry'])

                if type(temp_geo) is not Point:
                    print 'Extent for cross section', xs_id, 'is type', type(temp_geo), ', should be Point. Ignoring.'
                    continue

                geo = gt.ADPoint(shapely_geo=temp_geo)
                xs = get_xs(xs_id)
                # If the cross section doesn't exist, ignore the extent
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

    def import_multi_river(self, river_file, river_field, reach_field):
        """
        Reads multiple reaches from self.river_file. river_field and reach_field are the name of attributes in the
        self.river_file shapefile. Saves Rivers object to self.rivers

        :param river_file: string - river shapefile
        :param river_field: string - name of rivercode attribute field
        :param reach_field: string - name of reachcode attribute filed
        """
        self.rivers = Rivers()
        with fiona.collection(river_file, 'r') as input_file:
            for feature in input_file:
                # Fiona might give a Linestring or a MultiLineString, handle both cases
                temp_geo = shape(feature['geometry'])
                if type(temp_geo) is MultiLineString:
                    raise ShapefileError('Feature in ' + river_file + ' is MultiLineString.' +
                                         ' This is likely an error.')
                elif type(temp_geo) is LineString:
                    geo = gt.ADPolyline(shapely_geo=temp_geo)
                    river_name = feature['properties'][river_field]
                    reach_name = feature['properties'][reach_field]
                    temp_river = River(geo, river_name, reach_name)
                    self.rivers.reaches.append(temp_river)
                else:
                    raise ShapefileError('Feature in ' + river_file + ' is not a Linestring.')

    def import_single_river(self, river_file):
        """
        imports river from river_file shapefile
        raises exception if file has more than one feature or is not Linestring
        :param river_file: string - name of river shapefile
        """
        with fiona.collection(river_file, 'r') as input_file:
            feature = list(input_file)

            if len(feature) > 1:
                raise ShapefileError('More than one feature in river shapefile' + river_file)

            # Fiona might give a Linestring or a MultiLineString, handle both cases
            temp_geo = shape(feature[0]['geometry'])
            if type(temp_geo) is MultiLineString:
                raise ShapefileError('Feature in ' + str(river_file) + ' is MultiLineString.' +
                                     ' This is likely an error.')
            elif type(temp_geo) is LineString:
                geo = gt.ADPolyline(shapely_geo=temp_geo)
                self.river = River(geo, None, None)
            else:
                raise ShapefileError('Feature in ' + river_file + ' is not a Linestring.')

    def import_xs(self, xs_file, xs_id_field='ProfileM'):
        """
        Imports hec-ras cross section cut lines from self.xs_file.
        :param xs_id_field: string - attribute field with XS names
        :param xs_file: string - name of cross section shapefile
        """
        if xs_file is None:
            raise ValueError('xs_file must be set to name of shapefile')

        with fiona.collection(xs_file, 'r') as input_file:
            for feature in input_file:
                xs_id = feature['properties'][xs_id_field]

                # Fiona might give a Linestring or a MultiLineString, handle both cases
                temp_geo = shape(feature['geometry'])
                if type(temp_geo) is not LineString:
                    raise ShapefileError('Cross section' + str(xs_id) + 'is type' + str(type(temp_geo)) +
                                         ', should be LineString.')
                geo = gt.ADPolyline(shapely_geo=temp_geo)
                self.full_combo_list.append(CrossSection(geo, xs_id))

    def run_all_reaches(self):
        """
        Delineates all reaches in self.rivers
        :return: list of ADPolylines
        """
        river_list = []
        for river in self.rivers.reaches:
            temp = (river.river, river.reach)
            river_list.append(temp)
        return self.run_multi_reach(river_list)

    def run_multi_reach(self, river_reach_list):
        """
        Delineates river/reach combos in river_reach_list. Returns boundary
        :param river_reach_list: list of tuples: (river, reach)
        :return: list of ADPolylines
        """
        boundary = []
        for i, river_reach in enumerate(river_reach_list):
            print 'Processing reaching number', i+1, 'of', len(river_reach_list)+1
            b = self.run_named_reach(river_reach)
            boundary += b
        return boundary

    def run_named_reach(self, river_reach):
        """
        Delineates river/reach in river_reach. Returns boundary
        :param river_reach: tuple: (river, reach)
        :return: list of ADPolyline boundaries
        """
        river, reach = river_reach
        self._select_river(river, reach)
        #self.merge_bfe_and_xs()
        self._select_bfe_xs()
        self._calc_stations()
        self._sort_bfe_and_xs()
        print '============= Delineating reach:', river_reach
        bound = self.run_single_reach()
        print '============= Finished delineating:', river_reach
#        self._reset_combo_list()
        return bound

    def run_single_reach(self):
        """
        Delinate single reach. Assumed all features in shapefiles belong to the same reach or have been properly
        selected.
        :return: list of Adpolyine boundaries
        """
        boundary = logic.delineate(self.combo_list, self.contours, workers=self.workers)
        return boundary

    # def run_multi_reach_smp(self, river_reach, workers=4):
    #     """
    #     Delineates river/reach combos in river_reach using multiple processes. Returns boundary
    #     :param river_reach: list of tuples: (river, reach)
    #     :param workers: number of processes to use
    #     :return: left, right - two lists of ADPolylines
    #     """
    #     print 'creating pool'
    #     pool = mp.ProcessingPool(workers)
    #     print ' running pool.map'
    #     results = list(pool.map(self.run_named_reach, river_reach))
    #     return results

    def export_boundary(self, boundary, out_file):
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
        with fiona.open(out_file, 'w', driver='ESRI Shapefile', crs=self.crs, schema=schema) as out:
            for line in boundary:
                out.write({'geometry': mapping(line.shapely_geo), 'properties': {'status': line.status}})

    @staticmethod
    def plot_boundary(boundary, color='blue'):
        for line in boundary:
            line.plot(color=color)
        pyplot.axes().set_aspect('equal', 'datalim')
        pyplot.show()

    def trim_bfe_xs(self, start=None, end=None):
        """
        Removes BFE/cross sections that are not in between start and end
        :param bfe_xs_list:
        :param start: highest elevation bfe/cross section to use
        :param end: lowest elevation bfe to use
        """
        # Check for proper order
        if self.combo_list[0].elevation > self.combo_list[-1].elevation:
            # print 'BFE/cross section list appears to be in reverse order. Reversing.'
            self.combo_list = self.combo_list[::-1]

        new_bfe_xs_list = []
        flag = 'out'
        for bfe_xs in self.combo_list:
            if bfe_xs.name == start:
                flag = 'in'
                new_bfe_xs_list.append(bfe_xs)
            elif flag == 'in' and bfe_xs.name != end:
                new_bfe_xs_list.append(bfe_xs)
            elif bfe_xs.name == end:
                new_bfe_xs_list.append(bfe_xs)
                break
                # print 'bfe_xs.name=', bfe_xs.name,'start=', start,'end=', end
        self.combo_list = new_bfe_xs_list

    def _calc_stations(self):
        # TODO - this appears to be redundant to _calc_bfe_stations and _calc_xs_stations
        """
        Calculates stations for BFEs/XSs in self.combo_list
        """
        if self.river is None:
            raise ValueError('self.river has not been defined yet')

        for item in self.combo_list:
            temp_point = self.river.geo.intersection(item.geo)
            if type(temp_point) is MultiPoint:
                raise ShapefileError('BFE/XS' + str(item.name) + 'crosses channel alignment multiple times.')
            elif temp_point is None:
                raise ShapefileError('BFE/XS' + str(item.name) + 'does not cross channel alignment. Does ' +
                                     'select_xs_bfe() need to be run?')

            item.river_intersect = temp_point
            item.station = self.river.geo.project(item.river_intersect)

    def _select_river(self, river_code, reach_code):
        """
        returns ADPolyline from rivers with river_code and reach_code
        :param rivers: list of ADPolyline Objects from self.multi_river_import
        :param river_code: string
        :param reach_code: string
        :return: ADPolyine
        """
        x = self.rivers.get_reach(river_code, reach_code)
        if x is not None:
            self.river = x
        else:
            raise ValueError('River/reach '+river_code+'/'+reach_code+' not found in rivers')
        print 'Successfully selected', river_code, '/', reach_code

    def _select_bfe_xs(self):
        """
        Creates partial list of BFE/XS in self.combo_list. Full BFE/XS list is stored in self.full_combo_list
        :param river: ADPolyline - river
        :param combo_list: list of ADPolyline - bfes and cross sections
        """
        self.combo_list = []
        for item in self.full_combo_list:
            if item.geo.crosses(self.river.geo):
                if type(item) is logic.BFE:
                    self.combo_list.append(item)
                else:
                    # Only include cross sections with extents
                    if item.left_extent is not None and item.right_extent is not None:
                        self.combo_list.append(item)

    def _sort_bfe_and_xs(self):
        self.combo_list.sort(key=lambda x: x.station)

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
