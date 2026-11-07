"""Standalone scientific plots using ReportLab charts and Poppler rendering."""
from pathlib import Path
import subprocess
import tempfile
from reportlab.graphics.shapes import Drawing, String, Rect, Line, Circle
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.lib import colors
from .common import OS_ORDER

PALETTE = (colors.HexColor("#2563a6"), colors.HexColor("#df8b2d"), colors.HexColor("#28866c"))


def save_png(drawing, path):
    from reportlab.graphics import renderPDF
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="osdefects-plot-") as temporary:
        pdf = Path(temporary) / "plot.pdf"
        renderPDF.drawToFile(drawing, str(pdf))
        subprocess.run(["pdftoppm", "-f", "1", "-singlefile", "-scale-to", "1800", "-png", str(pdf), str(path.with_suffix(""))], check=True, capture_output=True)


def _canvas(title, subtitle, width=1120, height=650):
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=None))
    drawing.add(String(38, height-42, title, fontName="Helvetica-Bold", fontSize=23, fillColor=colors.HexColor("#162b3c")))
    drawing.add(String(38, height-68, subtitle, fontSize=12, fillColor=colors.HexColor("#4e6271")))
    return drawing


def grouped_bars(title, categories, series, path, subtitle="Released labels; 500 defects per OS", ymax=100):
    drawing = _canvas(title, subtitle)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 82, 155, 985, 365
    chart.data = [tuple(series[os_name]) for os_name in OS_ORDER]
    chart.categoryAxis.categoryNames = list(categories)
    chart.categoryAxis.labels.angle = 32
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.dx, chart.categoryAxis.labels.dy = -2, -7
    chart.categoryAxis.labels.fontSize = 11
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, ymax, max(10, ymax/5)
    chart.valueAxis.labels.fontSize = 11
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = colors.HexColor("#e4eaf0")
    chart.barSpacing, chart.groupSpacing = 2, 12
    for index, color in enumerate(PALETTE):
        chart.bars[index].fillColor = color
        chart.bars[index].strokeColor = None
    drawing.add(chart)
    drawing.add(String(20, 535, "%", fontSize=13))
    for index, os_name in enumerate(OS_ORDER):
        x = 300 + index*185
        drawing.add(Rect(x, 558, 14, 11, fillColor=PALETTE[index], strokeColor=None))
        drawing.add(String(x+22, 558, os_name, fontSize=12))
    drawing.add(String(38, 24, "Source: pinned author dataset. Values are recomputed, not copied from the paper.", fontSize=10, fillColor=colors.HexColor("#536774")))
    save_png(drawing, path)


def multi_series_bars(title, categories, series_names, series_values, path, subtitle="", ymax=100):
    """Grouped bars with explicit series names, e.g. paper labels vs recomputations.

    Categories are shared by every series; series_values is a list aligned with
    series_names. Used by the repair-size sensitivity analysis to overlay the
    published bar labels and each boundary convention in one figure.
    """
    drawing = _canvas(title, subtitle)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 82, 155, 985, 365
    chart.data = [tuple(values) for values in series_values]
    chart.categoryAxis.categoryNames = list(categories)
    chart.categoryAxis.labels.angle = 32
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.dx, chart.categoryAxis.labels.dy = -2, -7
    chart.categoryAxis.labels.fontSize = 9
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, ymax, max(10, ymax/5)
    chart.valueAxis.labels.fontSize = 11
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = colors.HexColor("#e4eaf0")
    chart.barSpacing, chart.groupSpacing = 1, 8
    palette = [colors.HexColor("#4a5560"), PALETTE[0], PALETTE[1]]
    if len(series_values) > len(palette):
        palette = palette + [PALETTE[2]] * (len(series_values) - len(palette))
    for index, color in enumerate(palette[:len(series_values)]):
        chart.bars[index].fillColor = color
        chart.bars[index].strokeColor = None
    drawing.add(chart)
    drawing.add(String(20, 535, "%", fontSize=13))
    for index, name in enumerate(series_names):
        x = 110 + index*300
        drawing.add(Rect(x, 558, 14, 11, fillColor=palette[index], strokeColor=None))
        drawing.add(String(x+22, 558, name, fontSize=11))
    drawing.add(String(38, 24, "Source: pinned author dataset; the paper series shows transcribed bar labels.", fontSize=10, fillColor=colors.HexColor("#536774")))
    save_png(drawing, path)


def heatmap(title, row_labels, col_labels, matrix, path, subtitle, correlation=False):
    drawing = _canvas(title, subtitle, width=1120, height=730)
    x0, y0, width, height = 190, 180, 875, 420
    cw, ch = width/len(col_labels), height/len(row_labels)
    maximum = 1.0 if correlation else max((value for row in matrix for value in row if value is not None), default=1) or 1
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            x, y = x0+j*cw, y0+(len(row_labels)-i-1)*ch
            if value is None:
                strength, rgb = 0, (1, 1, 1)
            elif correlation:
                strength = abs(value)
                rgb = (0.75, 0.25, 0.25) if value < 0 else (0.13, 0.38, 0.64)
            else:
                strength = value/maximum
                rgb = (0.13, 0.38, 0.64)
            fill = colors.Color(*(1-strength*(1-c) for c in rgb))
            drawing.add(Rect(x, y, cw, ch, fillColor=fill, strokeColor=colors.white, strokeWidth=1))
            label = "N/A" if value is None else (f"{value:.3f}" if correlation else f"{value:.1f}")
            drawing.add(String(x+cw/2, y+ch/2-4, label, textAnchor="middle", fontSize=12,
                               fillColor=colors.white if strength>.62 else colors.HexColor("#203344")))
    for i, label in enumerate(row_labels):
        drawing.add(String(x0-12, y0+(len(row_labels)-i-.5)*ch-4, label, textAnchor="end", fontSize=12))
    for j, label in enumerate(col_labels):
        # Short labels are deliberately kept horizontal on a wide figure.
        drawing.add(String(x0+(j+.5)*cw, y0-24, label, textAnchor="middle", fontSize=10))
    note = "Spearman rho; average ranks for ties; blue positive, red negative." if correlation else "Cells are percentages of all defects within an OS, not row-normalized percentages."
    drawing.add(String(38, 42, note, fontSize=11, fillColor=colors.HexColor("#536774")))
    save_png(drawing, path)


def extension_plot(summary, path):
    drawing = _canvas("Extension: sample-size sensitivity", "Mean total variation over 30 seeds; averaged over the three classification dimensions")
    x0, y0, width, height = 90, 125, 955, 395
    sizes = summary["sizes"]
    values = {}
    for os_name in OS_ORDER:
        values[os_name] = []
        for size in sizes:
            rows = [r for r in summary["aggregates"] if r["os"]==os_name and r["sample_size"]==size]
            values[os_name].append(sum(r["tv_mean"] for r in rows)/len(rows))
    ymax = max(.1, max(max(v) for v in values.values())*1.2)
    for tick in range(6):
        y = y0+height*tick/5
        drawing.add(Line(x0, y, x0+width, y, strokeColor=colors.HexColor("#e4eaf0")))
        drawing.add(String(x0-12, y-4, f"{ymax*tick/5:.2f}", textAnchor="end", fontSize=11))
    for index, size in enumerate(sizes):
        x = x0+width*index/(len(sizes)-1)
        drawing.add(String(x, y0-26, str(size), textAnchor="middle", fontSize=12))
    for oi, os_name in enumerate(OS_ORDER):
        points = [(x0+width*i/(len(sizes)-1), y0+height*v/ymax) for i,v in enumerate(values[os_name])]
        for a,b in zip(points, points[1:]):
            drawing.add(Line(*a,*b,strokeColor=PALETTE[oi],strokeWidth=2))
        for x,y in points:
            drawing.add(Circle(x,y,4,fillColor=PALETTE[oi],strokeColor=None))
        lx=300+oi*185
        drawing.add(Rect(lx,558,14,11,fillColor=PALETTE[oi],strokeColor=None))
        drawing.add(String(lx+22,558,os_name,fontSize=12))
    drawing.add(String(540, 65, "Sample size per OS", textAnchor="middle", fontSize=13))
    drawing.add(String(38, 24, "Only sample size changes. This is within-corpus robustness, not external validation. SD is reported in extension_summary.csv.", fontSize=10))
    save_png(drawing, path)


def make_plots(results, outdir):
    outdir = Path(outdir)
    paths = []
    names = {"os_layer":"RQ1: OS-layer distribution", "affected_function":"RQ1: affected functions",
             "trigger_scenario":"RQ1: trigger scenarios", "severity":"RQ1: severity", "code_level":"RQ1: repaired code elements (multiple labels allowed)"}
    for dim, groups in results.get("univariate", {}).get("dimensions", {}).items():
        path = outdir/f"rq1_{dim}.png"
        categories = groups["Android"]["categories"]
        grouped_bars(names[dim], categories, {os_name:groups[os_name]["percent"] for os_name in OS_ORDER}, path)
        paths.append(str(path))
    for field, groups in results.get("repairs", {}).get("distributions", {}).items():
        path = outdir/f"repair_{field}.png"
        grouped_bars("Repair size: "+field.replace("_"," "), groups["Android"]["bins"], {o:groups[o]["percent"] for o in OS_ORDER}, path,
                     subtitle="Declared reproduction bins; original Figure 2/3 bar heights are not numerically verified")
        paths.append(str(path))
    for table_name, table in results.get("joint", {}).get("tables", {}).items():
        for os_name, matrix in table["matrices"].items():
            path = outdir/f"{table_name}_{os_name}.png"
            label = "Table " + table_name.removeprefix("table_").upper()
            heatmap(f"RQ2: {label} / {os_name}", matrix["row_categories"], matrix["column_categories"], matrix["percent"], path,
                    "Joint percentages; N=500. Colors scale to the maximum within each panel.")
            paths.append(str(path))
    for dimension, summary in results.get("similarity", {}).get("dimensions", {}).items():
        if dimension == "overall": continue
        path = outdir/f"rq3_{dimension}.png"
        heatmap("RQ3: "+dimension.replace("_"," "), summary["os_order"], summary["os_order"], summary["matrix"], path,
                "Recomputed distribution correlations; compare with published Fig. 4", correlation=True)
        paths.append(str(path))
    if "extension" in results:
        path = outdir/"extension_sample_size.png"
        extension_plot(results["extension"], path)
        paths.append(str(path))
    return paths
