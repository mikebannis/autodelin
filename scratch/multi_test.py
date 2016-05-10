from shapely.geometry import MultiPoint, LineString

line1 = LineString([(0,0),(1,0)])
line2 = LineString([(0,0), (0,1), (1,0)])
line3 = LineString([(0.5, 0), (0.5, 1)])
x = line1.intersection(line2)