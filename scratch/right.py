# Do right side --------------------------------------------------------------------------
print '--' * 20 + 'right side'
right_boundary = []
# Find first valid bfe/cross_section
remaining_bfe_xs = None
for i, bfe_xs in enumerate(bfe_cross_sections):
    last_bfe_xs = bfe_xs
    if type(last_bfe_xs) is BFE:
        last_position = 0.0
        last_high_pt = last_bfe_xs.last_point
        last_low_pt = last_bfe_xs.last_point
        remaining_bfe_xs = bfe_cross_sections[i + 1:]
        break
    else:  # cross section
        last_position, last_high_pt, last_low_pt = _calc_extent_position(last_bfe_xs,
                                                                         last_bfe_xs.right_extent, contours)
        if last_position >= 0:
            remaining_bfe_xs = bfe_cross_sections[i + 1:]
            break
if remaining_bfe_xs is None:
    print 'Error finding valid BFE/cross section'
    raise

# Loop through all the remaining BFE/XS
for current_bfe_xs in remaining_bfe_xs:
    print 'R*******Working on last', last_bfe_xs.name, 'to current', current_bfe_xs.name
    try:
        orig_low_contour = contours.get(math.floor(last_bfe_xs.elevation))
        orig_high_contour = contours.get(math.ceil(current_bfe_xs.elevation))
        # Determine high and low points at current BFE/XS for clipping contours
        if type(current_bfe_xs) is BFE:
            current_position = 1
            # high clip point is end of BFE line
            current_high_pt = current_bfe_xs.last_point
            temp_low_contour = _closest_contour_segment(orig_low_contour, current_bfe_xs.last_point)
            # temp_low_contour.plot()
            # current_bfe_xs.geo.plot(color='orange')
            # print 'orig_low_elevation=', orig_low_contour.elevation
            current_low_pt = current_bfe_xs.geo.nearest_intersection(temp_low_contour, current_bfe_xs.last_point)
        else:  # CrossSection
            current_position, current_high_pt, current_low_pt = \
                _calc_extent_position(current_bfe_xs, current_bfe_xs.right_extent, contours)
            # Ignore extent if outside of contours
            if current_position < 0:
                print 'Bad extent, ignoring.'
                continue

        # print 'last low pt', type(last_low_pt), last_low_pt, 'current_low_pt', type(current_low_pt), current_low_pt
        # Clip contour based on orig/current high/low points
        low_contour = _clip_to_bfe(orig_low_contour, last_low_pt, current_low_pt)
        high_contour = _clip_to_bfe(orig_high_contour, last_high_pt, current_high_pt)

        # Make contours point up hill
        _orient_contours(last_low_pt, low_contour)
        _orient_contours(last_high_pt, high_contour)

        if NEW_DEBUG:
            low_contour.plot(color='black', linewidth=2)
            high_contour.plot(color='red')
            low_contour.first_point.plot(marker='o')
            low_contour.last_point.plot(marker='o')
            high_contour.first_point.plot(marker='o')
            high_contour.last_point.plot(marker='o')

        boundary = gt.draw_line_between_contours(low_contour, high_contour, last_position, current_position)
        if type(boundary) is gt.ADPolyline:
            print 'Success'
        if _contour_crosses_boundary(boundary, orig_high_contour, orig_low_contour):
            status = 'Crosses'
        else:
            status = 'OK'
        boundary.status = status
        right_boundary.append(boundary)

        if DEBUG1:
            boundary.plot(marker='D')
    except ComplexContourError:
        print 'Right: Funky contour'
    except ContourNotFound:
        print 'Right: Contour not found'
    except gt.UnknownIntersection:
        print 'Left: Contour doesn\'t intersect BFE/cross section'
    except Exception as e:
        print 'Right: unknown exception:', str(e)

    # Reset for next BFE/XS
    last_bfe_xs = current_bfe_xs
    if type(last_bfe_xs) is BFE:
        # BFE, last high is new low
        last_low_pt = current_high_pt
        # Hack, should extend BFE or intersect XS
        last_high_pt = current_high_pt
    else:  # Cross section
        last_low_pt = current_low_pt
        last_high_pt = current_high_pt
    if current_position == 1:
        last_position = 0
    else:
        last_position = current_position