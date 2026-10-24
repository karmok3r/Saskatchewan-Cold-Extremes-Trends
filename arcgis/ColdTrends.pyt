# -*- coding: utf-8 -*-
"""ArcGIS Pro toolbox for the Saskatchewan cold-extremes trend analysis.

Run the Python pipeline (scripts/01-06) first; these tools pick up its CSV outputs.
"""
import os

import arcpy

# Reruns replace earlier outputs (e.g. a cube left behind by a failed run).
arcpy.env.overwriteOutput = True

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spatial analysis outputs live with the ArcGIS Pro project in gisProject/gisProject.
GIS_DIR = os.path.join(PROJECT_ROOT, "gisProject", "gisProject")
DEFAULT_GDB = os.path.join(GIS_DIR, "gisProject.gdb")
TABLES = os.path.join(PROJECT_ROOT, "outputs", "tables")
PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")

# NAD 1983 Statistics Canada Lambert, the projection of StatCan boundary files.
SR_LAMBERT = arcpy.SpatialReference(3347)
SR_WGS84 = arcpy.SpatialReference(4326)
SK_PRUID = "47"
NUMERIC = ["Double", "Single", "Long", "Short"]
# Indices where a falling value means warming (fewer cold days, earlier last frost).
COLD_COUNT_INDICES = ["FD", "ID", "CN30", "CN40", "LSF"]

# Map titles for trend rasters (trend_slope_<field>).
MAP_TITLES = {
    "TNn": "Coldest night of the year (°C/decade)",
    "TXn": "Coldest day of the year (°C/decade)",
    "DJF_TN": "Winter mean minimum temperature (°C/decade)",
    "DJF_TX": "Winter mean maximum temperature (°C/decade)",
    "FD": "Frost days (days/decade)",
    "ID": "Ice days (days/decade)",
    "CN30": "Nights at or below −30 °C (nights/decade)",
    "CN40": "Nights at or below −40 °C (nights/decade)",
    "LSF": "Last spring frost date (days/decade)",
    "FFF": "First fall frost date (days/decade)",
    "FFS": "Frost-free season length (days/decade)",
    "Tmin_Win": "Winter minimum temperature, homogenized (°C/decade)",
    "Tmax_Win": "Winter maximum temperature, homogenized (°C/decade)",
    "Tmean_Win": "Winter mean temperature, homogenized (°C/decade)",
    "Tmin_Ann": "Annual minimum temperature, homogenized (°C/decade)",
    "Tmean_Ann": "Annual mean temperature, homogenized (°C/decade)",
}


# Sequential palettes, light -> dark. Dark always marks the warmest change.
PALETTES = {
    "Yellow-Orange-Red": ["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"],
    "Magma": ["#fcfdbf", "#fe9f6d", "#de4968", "#8c2981", "#3b0f70"],
    "Viridis": ["#fde725", "#5ec962", "#21918c", "#3b528b", "#440154"],
    "Blues": ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
}
DEFAULT_PALETTE = "Yellow-Orange-Red"


def rgb(hex_color):
    color = arcpy.cim.CreateCIMObjectFromClassName("CIMRGBColor", "V3")
    h = hex_color.lstrip("#")
    color.values = [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [100]
    return color


def multipart_ramp(colors):
    """Continuous ramp through the given colours, in the order Pro applies them."""
    ramp = arcpy.cim.CreateCIMObjectFromClassName("CIMMultipartColorRamp", "V3")
    parts = []
    for a, b in zip(colors[:-1], colors[1:]):
        part = arcpy.cim.CreateCIMObjectFromClassName("CIMLinearContinuousColorRamp", "V3")
        part.fromColor, part.toColor = rgb(a), rgb(b)
        parts.append(part)
    ramp.colorRamps = parts
    ramp.weights = [1.0 / len(parts)] * len(parts)
    return ramp


def raster_range(path):
    lo = float(arcpy.management.GetRasterProperties(path, "MINIMUM").getOutput(0).replace(",", "."))
    hi = float(arcpy.management.GetRasterProperties(path, "MAXIMUM").getOutput(0).replace(",", "."))
    return lo, hi


def stretch_labels(lo, hi, negative_is_warming):
    """Readable legend labels for the low and high ends of the stretch."""
    def num(v):
        if abs(v) < 0.005:
            return "0"
        return (f"{v:+.2f}" if abs(v) < 0.1 else f"{v:+.1f}").replace("-", "−")
    if negative_is_warming and hi <= 0:
        return f"{num(lo)} (largest loss)", f"{num(hi)} ({'no change' if abs(hi) < 0.05 else 'smallest loss'})"
    if not negative_is_warming and lo >= 0:
        return f"{num(lo)} (slowest)", f"{num(hi)} (fastest)"
    return num(lo), num(hi)


def style_trend_layer(lyr, path, name, messages, palette=DEFAULT_PALETTE):
    """Stretch with a sequential palette (dark = toward warmer) and labelled ends."""
    negative_is_warming = any(f"slope_{k}" in name for k in COLD_COUNT_INDICES)
    lo, hi = raster_range(path)
    min_label, max_label = stretch_labels(lo, hi, negative_is_warming)

    sym = lyr.symbology
    if hasattr(sym, "updateColorizer"):
        sym.updateColorizer("RasterStretchColorizer")
        sym.colorizer.stretchType = "MinimumMaximum"
        try:
            sym.colorizer.minLabel = min_label
            sym.colorizer.maxLabel = max_label
        except AttributeError:
            pass
        lyr.symbology = sym

    try:
        cim = lyr.getDefinition("V3")
        low_dark = negative_is_warming
        light_to_dark = PALETTES.get(palette, PALETTES[DEFAULT_PALETTE])
        low_to_high = light_to_dark[::-1] if low_dark else light_to_dark
        # Pro's stretch applies the ramp from the HIGH end down, so feed it high -> low.
        cim.colorizer.colorRamp = multipart_ramp(low_to_high[::-1])
        # Labels via CIM too, in case this Pro release ignores minLabel/maxLabel.
        classes = getattr(cim.colorizer, "stretchClasses", None) or []
        if len(classes) >= 2:
            classes[0].label, classes[-1].label = min_label, max_label
        lyr.setDefinition(cim)
        messages.addMessage(f"{name}: {palette} palette, dark = {'lowest' if low_dark else 'highest'} value; "
                            f"labels '{min_label}' / '{max_label}'")
    except Exception as exc:
        messages.addWarningMessage(f"{name}: could not set the colour ramp automatically ({exc}).")


def hide_legend_headings(layout, messages):
    """Drop the 'Value' heading under each legend item."""
    try:
        cim = layout.getDefinition("V3")
        for element in cim.elements:
            if type(element).__name__ == "CIMLegend":
                for item in element.items:
                    item.showHeading = False
        layout.setDefinition(cim)
    except Exception as exc:
        messages.addWarningMessage(f"Could not hide legend headings ({exc}).")


def map_title(raster_name):
    field = raster_name.replace("trend_slope_", "")
    period = "1951–2020" if field.startswith(("Tmin_", "Tmax_", "Tmean_")) else "1951–2025"
    return f"{MAP_TITLES.get(field, field.replace('_', ' '))}\nSaskatchewan trend, {period}"


def ensure_gdb(path):
    if not arcpy.Exists(path):
        arcpy.management.CreateFileGDB(os.path.dirname(path), os.path.basename(path))
    return path


def param(name, label, datatype, direction="Input", required=True, multi=False, default=None):
    p = arcpy.Parameter(name=name, displayName=label, datatype=datatype, direction=direction,
                        parameterType="Required" if required else "Optional", multiValue=multi)
    if default is not None:
        p.value = default
    return p


def changed(*params):
    """True when any input was edited since the dialog last validated."""
    return any(p.value and p.altered and not p.hasBeenValidated for p in params)


def check_out(extension):
    if arcpy.CheckExtension(extension) != "Available":
        raise arcpy.ExecuteError(f"The {extension} extension is not licensed.")
    arcpy.CheckOutExtension(extension)


class Toolbox:
    def __init__(self):
        self.label = "Saskatchewan Cold Trends"
        self.alias = "coldtrends"
        self.tools = [PrepareBoundaries, ImportResults, InterpolateTrend,
                      EmergingHotSpots, ZonalSummary, ExportMaps]


class PrepareBoundaries:
    def __init__(self):
        self.label = "1. Prepare Boundaries"
        self.description = ("Extract Saskatchewan from StatCan province / census-division files "
                            "and clip ecozones to the province.")

    def getParameterInfo(self):
        return [
            param("provinces", "StatCan provinces (lpr_000b21a_e)", "GPFeatureLayer"),
            param("census_divs", "StatCan census divisions (lcd_000b21a_e)", "GPFeatureLayer", required=False),
            param("ecozones", "Ecozones (National Ecological Framework)", "GPFeatureLayer", required=False),
            param("gdb", "Output geodatabase", "DEWorkspace", default=DEFAULT_GDB),
        ]

    def execute(self, parameters, messages):
        provinces, census_divs, ecozones, gdb = [p.valueAsText for p in parameters]
        os.makedirs(os.path.dirname(gdb), exist_ok=True)
        gdb = ensure_gdb(gdb)
        where = f"PRUID = '{SK_PRUID}'"
        boundary = os.path.join(gdb, "sk_boundary")
        # Dissolve so any StatCan layer carrying PRUID yields a single outline.
        sel = arcpy.management.MakeFeatureLayer(provinces, "sk_prov", where)
        projected = os.path.join(arcpy.env.scratchGDB, "sk_prov_lambert")
        arcpy.management.Project(sel, projected, SR_LAMBERT)
        arcpy.management.Dissolve(projected, boundary, "PRUID")
        if census_divs:
            sel = arcpy.management.MakeFeatureLayer(census_divs, "sk_cd", where)
            arcpy.management.Project(sel, os.path.join(gdb, "sk_census_divisions"), SR_LAMBERT)
        if ecozones:
            projected = os.path.join(arcpy.env.scratchGDB, "ecozones_lambert")
            arcpy.management.Project(ecozones, projected, SR_LAMBERT)
            arcpy.analysis.Clip(projected, boundary, os.path.join(gdb, "sk_ecozones"))
        messages.addMessage(f"Boundaries written to {gdb}")


class ImportResults:
    def __init__(self):
        self.label = "2. Import Pipeline Results"
        self.description = "Turn the Python pipeline's CSV outputs into projected point feature classes."

    def getParameterInfo(self):
        return [param("gdb", "Output geodatabase", "DEWorkspace", default=DEFAULT_GDB)]

    def execute(self, parameters, messages):
        gdb = ensure_gdb(parameters[0].valueAsText)
        sources = {
            "station_trends": os.path.join(TABLES, "station_trends.csv"),
            "ahccd_trends": os.path.join(TABLES, "ahccd_trends.csv"),
            "station_indices": os.path.join(PROCESSED, "station_indices.csv"),
        }
        for name, csv in sources.items():
            if not os.path.exists(csv):
                messages.addWarningMessage(f"Missing {csv}; run the Python pipeline first.")
                continue
            tmp = os.path.join(arcpy.env.scratchGDB, f"{name}_wgs")
            arcpy.management.XYTableToPoint(csv, tmp, "lon", "lat", coordinate_system=SR_WGS84)
            out = os.path.join(gdb, name)
            arcpy.management.Project(tmp, out, SR_LAMBERT)
            messages.addMessage(f"Created {out}")

        # Space-time cubes need a true date field.
        indices = os.path.join(gdb, "station_indices")
        if arcpy.Exists(indices):
            arcpy.management.AddField(indices, "obs_date", "DATE")
            arcpy.management.CalculateField(indices, "obs_date", "to_date(!year!)", "PYTHON3",
                                            "import datetime\ndef to_date(y):\n"
                                            "    return datetime.datetime(int(y), 1, 1)")


class InterpolateTrend:
    def __init__(self):
        self.label = "3. Interpolate Trend Surface"
        self.description = ("Interpolate a station trend field (e.g. slope_TNn) to a raster "
                            "clipped to Saskatchewan.")

    def getParameterInfo(self):
        points = param("points", "Station trend points", "GPFeatureLayer")
        field = param("field", "Trend field (slope_*)", "Field")
        field.parameterDependencies = [points.name]
        field.filter.list = NUMERIC
        method = param("method", "Method", "GPString", default="IDW")
        method.filter.list = ["IDW", "Natural Neighbor", "Empirical Bayesian Kriging"]
        return [
            points, field,
            param("boundary", "Saskatchewan boundary", "GPFeatureLayer",
                  default=os.path.join(DEFAULT_GDB, "sk_boundary")),
            method,
            param("cell_size", "Cell size (m)", "GPDouble", default=5000),
            param("out_raster", "Output raster", "DERasterDataset", direction="Output"),
            param("max_distance", "Only map within this distance of a station (blank = whole province)",
                  "GPLinearUnit", required=False),
        ]

    def updateParameters(self, parameters):
        points, field, _, _, _, out, _ = parameters
        if field.value and points.value and changed(points, field):
            out.value = os.path.join(DEFAULT_GDB, f"trend_{field.valueAsText}")

    def execute(self, parameters, messages):
        points, field, boundary, method, cell, out, max_distance = [p.valueAsText for p in parameters]
        cell = float(cell)
        check_out("Spatial")
        lyr = arcpy.management.MakeFeatureLayer(points, "trend_pts", f"{field} IS NOT NULL")
        n = int(arcpy.management.GetCount(lyr)[0])
        messages.addMessage(f"Interpolating {field} from {n} stations with {method}.")

        # Optionally restrict the surface to areas with nearby stations.
        if max_distance:
            near = os.path.join(arcpy.env.scratchGDB, "station_reach")
            arcpy.analysis.Buffer(lyr, near, max_distance, dissolve_option="ALL")
            mask = os.path.join(arcpy.env.scratchGDB, "station_reach_sk")
            arcpy.analysis.Clip(near, boundary, mask)
            boundary = mask
            messages.addMessage(f"Surface limited to within {max_distance} of a station.")

        with arcpy.EnvManager(extent=boundary, mask=boundary, outputCoordinateSystem=SR_LAMBERT,
                              cellSize=cell):
            if method == "IDW":
                surface = arcpy.sa.Idw(lyr, field, cell, 2)
            elif method == "Natural Neighbor":
                surface = arcpy.sa.NaturalNeighbor(lyr, field, cell)
            else:
                check_out("GeoStats")
                tmp = os.path.join(arcpy.env.scratchGDB, "ebk_tmp")
                arcpy.ga.EmpiricalBayesianKriging(lyr, field, None, tmp, cell)
                surface = tmp
            arcpy.sa.ExtractByMask(surface, boundary).save(out)
        messages.addMessage(f"Saved {out}")


class EmergingHotSpots:
    def __init__(self):
        self.label = "4. Emerging Hot Spot Analysis"
        self.description = ("Build a space-time cube from yearly station indices and classify "
                            "where an index is trending into a hot or cold spot.")

    def getParameterInfo(self):
        features = param("features", "Station indices points", "GPFeatureLayer",
                         default=os.path.join(DEFAULT_GDB, "station_indices"))
        field = param("field", "Index field", "Field")
        field.parameterDependencies = [features.name]
        field.filter.list = NUMERIC
        return [
            features, field,
            param("min_fraction", "Minimum fraction of years with data per station", "GPDouble", default=0.8),
            param("distance", "Neighbourhood distance", "GPLinearUnit", default="150 Kilometers"),
            param("out_cube", "Output space-time cube (.nc)", "DEFile", direction="Output"),
            param("out_features", "Output hot spot features", "DEFeatureClass", direction="Output"),
        ]

    def updateParameters(self, parameters):
        _, field, _, _, cube, feats = parameters
        if field.value and changed(field):
            cube.value = os.path.join(GIS_DIR, "cubes", f"cube_{field.valueAsText}.nc")
            feats.value = os.path.join(DEFAULT_GDB, f"ehsa_{field.valueAsText}")

    def execute(self, parameters, messages):
        features, field, min_frac, distance, cube, out_fc = [p.valueAsText for p in parameters]
        os.makedirs(os.path.dirname(cube), exist_ok=True)

        # Keep only stations with enough valid years so the cube isn't mostly filled values.
        valid, years = {}, set()
        with arcpy.da.SearchCursor(features, ["loc_id", "year", field]) as rows:
            for loc, year, value in rows:
                years.add(year)
                if value is not None:
                    valid[loc] = valid.get(loc, 0) + 1
        keep = [loc for loc, n in valid.items() if n >= float(min_frac) * len(years)]
        if len(keep) < 8:
            raise arcpy.ExecuteError(f"Only {len(keep)} stations pass the coverage filter; lower it.")
        messages.addMessage(f"{len(keep)} stations used for the cube.")
        lyr = arcpy.management.MakeFeatureLayer(
            features, "cube_pts", f"loc_id IN ({','.join(str(k) for k in keep)})")

        arcpy.stpm.CreateSpaceTimeCubeDefinedLocations(
            lyr, cube, "loc_id", "NO_TEMPORAL_AGGREGATION", "obs_date", "1 Years",
            "END_TIME", None, [[field, "SPACE_TIME_NEIGHBORS"]])

        # The cube may rename the variable; find it rather than guess.
        variables = arcpy.NetCDFFileProperties(cube).getVariables()
        matches = [v for v in variables if field.lower() in v.lower()]
        variable = matches[0] if matches else field
        # Positional: in_cube, analysis_variable, output_features, neighborhood_distance,
        # neighborhood_time_step (keyword names differ between Pro releases).
        arcpy.stpm.EmergingHotSpotAnalysis(cube, variable, out_fc, distance, 1)
        messages.addMessage(f"Saved {out_fc}")


class ZonalSummary:
    def __init__(self):
        self.label = "5. Zonal Trend Summary"
        self.description = "Summarize a trend raster by ecozone or census division and export CSV."

    def getParameterInfo(self):
        zones = param("zones", "Zones (ecozones / census divisions)", "GPFeatureLayer")
        zone_field = param("zone_field", "Zone field", "Field")
        zone_field.parameterDependencies = [zones.name]
        return [
            param("raster", "Trend raster", "GPRasterLayer"),
            zones, zone_field,
            param("out_csv", "Output CSV", "DEFile", direction="Output"),
        ]

    def updateParameters(self, parameters):
        raster, zones, _, out = parameters
        if raster.value and zones.value and changed(raster, zones):
            r = os.path.basename(arcpy.Describe(raster.value).catalogPath)
            z = os.path.basename(arcpy.Describe(zones.value).catalogPath)
            out.value = os.path.join(TABLES, f"zonal_{r}_{z}.csv")

    def execute(self, parameters, messages):
        raster, zones, zone_field, out_csv = [p.valueAsText for p in parameters]
        check_out("Spatial")
        table = os.path.join(arcpy.env.scratchGDB, "zonal_tmp")
        arcpy.sa.ZonalStatisticsAsTable(zones, zone_field, raster, table, "DATA", "ALL")
        arcpy.conversion.ExportTable(table, out_csv)
        messages.addMessage(f"Saved {out_csv}")


class ExportMaps:
    def __init__(self):
        self.label = "6. Export Trend Map Series"
        self.description = ("For each raster: show it (adding it if needed), apply a red ramp where "
                            "dark = toward warmer with labelled ends, set the layout title, export PNG. "
                            "Run inside an open project with a prepared layout.")

    def getParameterInfo(self):
        palette = param("palette", "Colour palette (dark = toward warmer)", "GPString",
                        default=DEFAULT_PALETTE)
        palette.filter.list = list(PALETTES)
        return [
            param("map_name", "Map name", "GPString", default="Map"),
            param("layout_name", "Layout name", "GPString", default="Layout"),
            param("title_element", "Title text element name", "GPString", default="Title"),
            param("rasters", "Trend rasters", "GPRasterLayer", multi=True),
            param("out_folder", "Output folder", "DEFolder",
                  default=os.path.join(GIS_DIR, "maps")),
            palette,
        ]

    def updateParameters(self, parameters):
        # Offer the open project's maps and layouts as dropdowns.
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            parameters[0].filter.list = [m.name for m in aprx.listMaps()]
            parameters[1].filter.list = [lyt.name for lyt in aprx.listLayouts()]
        except Exception:
            pass

    def execute(self, parameters, messages):
        map_name, layout_name, title_name, rasters, out_folder, palette = [p.valueAsText for p in parameters]
        os.makedirs(out_folder, exist_ok=True)
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        maps, layouts = aprx.listMaps(map_name), aprx.listLayouts(layout_name)
        if not maps:
            raise arcpy.ExecuteError(f"No map named '{map_name}'. Maps in this project: "
                                     f"{[m.name for m in aprx.listMaps()]}")
        if not layouts:
            raise arcpy.ExecuteError(f"No layout named '{layout_name}'. Layouts in this project: "
                                     f"{[lyt.name for lyt in aprx.listLayouts()] or 'none - create one first'}")
        m, layout = maps[0], layouts[0]
        if not layout.listElements("TEXT_ELEMENT", title_name):
            messages.addWarningMessage(f"No text element named '{title_name}'; maps export without a title.")
        paths = [arcpy.Describe(r.strip("'")).catalogPath for r in rasters.split(";")]

        def existing_layer(path):
            for lyr in m.listLayers():
                if lyr.isRasterLayer and os.path.normcase(lyr.dataSource) == os.path.normcase(path):
                    return lyr
            return None

        for path in paths:
            name = os.path.basename(path)
            lyr = existing_layer(path)
            added = lyr is None
            if added:
                lyr = m.addDataFromPath(path)
            style_trend_layer(lyr, path, name, messages, palette or DEFAULT_PALETTE)

            # Show only this raster among the ones being exported.
            for other in paths:
                o = existing_layer(other)
                if o is not None:
                    o.visible = o is lyr
            lyr.visible = True

            for el in layout.listElements("TEXT_ELEMENT", title_name):
                el.text = map_title(name)
            hide_legend_headings(layout, messages)
            out = os.path.join(out_folder, f"{name}.png")
            layout.exportToPNG(out, resolution=200)
            if added:
                m.removeLayer(lyr)
            messages.addMessage(f"Exported {out}")
