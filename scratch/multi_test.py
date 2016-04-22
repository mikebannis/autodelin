from shapely.geometry import MultiPoint, LineString

line1 = LineString([(0,0),(1,0)])
line2 = LineString([(0,0), (0,1), (1,0)])
inter = line1.intersection(line2)
print inter
x = list(inter)

for i in x:
    print i