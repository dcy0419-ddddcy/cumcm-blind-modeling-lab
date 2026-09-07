"""Pillow-only confirmed Q2 repair figures, no new rays or manuscript edits.
Read result JSON and the frozen compact design; never infer missing values.
Standard library plus existing Pillow only. Internal Pillow font, no external
font files, matplotlib, network access or import-time figure generation.
"""
from __future__ import annotations
import time
START = time.perf_counter()
from pathlib import Path
import sys
import math
import json
import io as string_io
import traceback
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q02_repair_common_v001 as io


def write_once(path, data):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError('Different existing figure artifact: ' + str(path))
        return
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_bytes(data)
    io.replace(temporary, path)


def create_figures(budget, report):
    import PIL
    from PIL import Image, ImageDraw, ImageFont
    import q02_compact_v001 as compact
    O = io.OUT
    result_path = O / '结果数据.json'
    freeze_path = O / '最终拟提交候选冻结.json'
    work_path = O / '独立工作指标重建.json'
    data, freeze, work = io.load(result_path), io.load(freeze_path), io.load(work_path)
    if data.get('decision') != 'PASS' or work.get('all_pass') is not True or work.get('exports_created') is not True:
        raise ValueError('Figures require current confirmed and independently rebuilt PASS results')
    if data['name'] != freeze['name'] or data['design_key'] != freeze['design_key']:
        raise ValueError('Result/frozen candidate identity mismatch')
    if work.get('exports', {}).get('结果数据.json', {}).get('sha256') != io.sha(result_path):
        raise ValueError('Results JSON differs from verified postprocessing export')
    if data['sources']['frozen_candidate_sha256'] != io.sha(freeze_path):
        raise ValueError('Frozen candidate differs from results binding')
    summary_path = O / 'frozen' / 'confirmation' / 'summary.json'
    if data['sources']['confirmation_summary_sha256'] != io.sha(summary_path):
        raise ValueError('Confirmation summary differs from results binding')
    if data['sources']['result2_excel_sha256'] != io.sha(O / 'result2.xlsx'):
        raise ValueError('Official workbook differs from confirmed export')
    bundle = O / 'frozen' / 'design.bundle.json'
    design, receipt = compact.read_compact(bundle, freeze['bundle_sha256'])
    expected_design = {'tower_xy': list(design.tower_xy), 'width_m': design.width, 'height_m': design.height,
        'installation_height_m': design.installation_height, 'n': design.n, 'total_area_m2': design.total_area}
    if data['actual_design'] != expected_design:
        raise ValueError('Result geometry differs from independently read compact design')
    monthly_rows = data['tables']['table1']['rows']
    work_rows = data['monthly_and_annual_work_indicator']
    if len(monthly_rows) != 12 or len(work_rows) != 13 or any(len(row) != 6 for row in monthly_rows + work_rows):
        raise ValueError('Expected twelve monthly rows and thirteen six-metric work-indicator rows')
    if [row[0] for row in monthly_rows] != [str(m) + '月21日' for m in range(1, 13)]:
        raise ValueError('Monthly samples must be in the fixed January-to-December order')
    q = [float(row[5]) for row in monthly_rows]
    uq = [float(row[5]) for row in work_rows[:12]]
    if not all(math.isfinite(v) and v > 0 for v in q) or not all(math.isfinite(v) and v >= 0 for v in uq):
        raise ValueError('Required monthly values/U are missing, nonfinite or outside the positive-power domain')
    xy = [(float(row['x']), float(row['y'])) for row in design.mirrors]
    tx, ty = map(float, design.tower_xy)
    if len(xy) != design.n or not all(math.isfinite(x) and math.isfinite(y) for x, y in xy):
        raise ValueError('Invalid actual mirror center coordinates')
    destination = io.ROOT / '工作记录' / '论文' / '图表' / 'Q02-v002'
    destination.mkdir(parents=True, exist_ok=True)
    fonts = {size: ImageFont.load_default(size=size) for size in (24, 26, 28, 30, 32, 40, 44)}
    ink, muted, blue, orange, grid = '#203040', '#52606b', '#235979', '#a15b3b', '#e3e8ec'
    def label(draw, at, text, size=28, anchor='la', fill=ink):
        draw.text(at, text, font=fonts[size], anchor=anchor, fill=fill)
    def save_png(image, name):
        output = destination / name
        buffer = string_io.BytesIO()
        image.save(buffer, format='PNG', dpi=(300, 300), optimize=True)
        write_once(output, buffer.getvalue())
        with Image.open(output) as rebuilt:
            if rebuilt.size != image.size or rebuilt.format != 'PNG':
                raise ValueError('PNG format or pixel-size readback mismatch')
            rebuilt.load()
        return {'path': str(output.relative_to(io.ROOT)), 'sha256': io.sha(output),
                'pixels': list(image.size), 'dpi': [300, 300], 'format': 'PNG', 'readback_ok': True}

    budget.guard(15)
    image = Image.new('RGB', (1800, 1900), 'white')
    draw = ImageDraw.Draw(image)
    left, top, size = 180., 210., 1440.
    extent = math.ceil(max(370., abs(tx) + 105., abs(ty) + 105.) / 25.) * 25.
    scale = size / (2 * extent)
    def X(x): return left + (x + extent) * scale
    def Y(y): return top + (extent - y) * scale
    label(draw, (900, 45), freeze['name'] + ': confirmed heliostat layout', 44, 'mt')
    subtitle = 'N = {:,} | Mirror = {:g} x {:g} m | Installation height = {:g} m'.format(
        design.n, design.width, design.height, design.installation_height)
    label(draw, (900, 111), subtitle, 28, 'mt', muted)
    label(draw, (left, 165), 'North y (m)', 28)
    tick_min = math.ceil(-extent / 100.) * 100
    tick_max = math.floor(extent / 100.) * 100
    for value in range(tick_min, tick_max + 1, 100):
        draw.line((X(value), top, X(value), top + size), fill=grid, width=2)
        draw.line((left, Y(value), left + size, Y(value)), fill=grid, width=2)
        label(draw, (X(value), top + size + 19), str(value), 26, 'mt', muted)
        label(draw, (left - 22, Y(value)), str(value), 26, 'rm', muted)
    draw.rectangle((left, top, left + size, top + size), outline=muted, width=2)
    for x, y in xy:
        px, py = X(x), Y(y)
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=blue)
    draw.ellipse((X(-350), Y(350), X(350), Y(-350)), outline=ink, width=4)
    draw.ellipse((X(tx - 100), Y(ty + 100), X(tx + 100), Y(ty - 100)), outline=orange, width=4)
    draw.line((X(tx) - 13, Y(ty), X(tx) + 13, Y(ty)), fill=orange, width=5)
    draw.line((X(tx), Y(ty) - 13, X(tx), Y(ty) + 13), fill=orange, width=5)
    label(draw, (900, 1730), 'East x (m) - equal x/y scale', 30, 'mt')
    label(draw, (900, 1790), 'Dots: mirror centers | Field radius: 350 m | Tower exclusion radius: 100 m', 26, 'mt', muted)
    label(draw, (900, 1840), 'Tower = ({:g}, {:g}) m. Confirmed under the prescribed numerical work criteria.'.format(tx, ty), 24, 'mt', muted)
    layout = save_png(image, 'Q02-确认镜场布局-v002.png')
    layout.update({'kind': 'mirror_center_layout', 'candidate': freeze['name'], 'actual_n': design.n,
        'x_range_m': [-extent, extent], 'y_range_m': [-extent, extent], 'equal_scale': True,
        'pixels_per_m_x': scale, 'pixels_per_m_y': scale, 'field_center_m': [0, 0], 'field_radius_m': 350,
        'tower_center_m': [tx, ty], 'exclusion_radius_m': 100, 'points_are_centers_not_footprints': True})
    del draw, image
    budget.tick()

    budget.guard(15)
    image = Image.new('RGB', (1800, 1300), 'white')
    draw = ImageDraw.Draw(image)
    left, top, width, height = 180., 205., 1440., 790.
    maximum = max(a + b for a, b in zip(q, uq))
    # Zero baseline makes the visual range explicit; work bars are never inflated.
    step_raw = maximum * 1.12 / 6
    magnitude = 10. ** math.floor(math.log10(step_raw))
    step = next(v for v in (1., 2., 2.5, 5., 10.) if v >= step_raw / magnitude) * magnitude
    ymax = math.ceil(maximum * 1.10 / step) * step
    ymin = min(0., math.floor(min(a - b for a, b in zip(q, uq)) / step) * step)
    def MX(month): return left + (month - .5) / 12. * width
    def MY(value): return top + (ymax - value) / (ymax - ymin) * height
    label(draw, (900, 40), 'Monthly unit-area thermal power', 44, 'mt')
    label(draw, (900, 108), freeze['name'] + ' | 21st of each month; average of the five prescribed times', 28, 'mt', muted)
    label(draw, (left, 162), 'Unit-area power (kW/m^2)', 28)
    for k in range(int(round((ymax - ymin) / step)) + 1):
        value = ymin + k * step
        draw.line((left, MY(value), left + width, MY(value)), fill=grid, width=2)
        label(draw, (left - 20, MY(value)), format(value, '.3g'), 26, 'rm', muted)
    draw.rectangle((left, top, left + width, top + height), outline=muted, width=2)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    points = [(MX(m + 1), MY(value)) for m, value in enumerate(q)]
    draw.line(points, fill=blue, width=5)
    for m, (value, uncertainty) in enumerate(zip(q, uq), start=1):
        px, py = MX(m), MY(value)
        high, low = MY(value + uncertainty), MY(value - uncertainty)
        draw.line((px, high, px, low), fill=ink, width=3)
        draw.line((px - 10, high, px + 10, high), fill=ink, width=3)
        draw.line((px - 10, low, px + 10, low), fill=ink, width=3)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=blue)
        label(draw, (px, top + height + 22), month_names[m - 1], 26, 'mt', muted)
    label(draw, (900, 1075), 'Representative month (21st)', 30, 'mt')
    label(draw, (900, 1136), 'Bars: +/- numerical work indicator U; not physical uncertainty or a confidence interval.', 24, 'mt', muted)
    label(draw, (900, 1183), 'Bars may be smaller than the markers. Lines connect the 12 prescribed dates only.', 24, 'mt', muted)
    label(draw, (900, 1230), 'Prescribed times: 09:00, 10:30, 12:00, 13:30, 15:00. No continuous-year interpolation.', 24, 'mt', muted)
    monthly = save_png(image, 'Q02-月度单位面积功率-v002.png')
    monthly.update({'kind': '12_prescribed_monthly_unit_power_samples', 'x_values': list(range(1, 13)),
        'x_range_month': [0.5, 12.5], 'y_range_kw_m2': [ymin, ymax], 'y_unit': 'kW/m^2',
        'monthly_q_kw_m2': q, 'monthly_U_kw_m2': uq, 'bars': 'q plus/minus prescribed numerical U, exact scale, no minimum visual inflation',
        'line_meaning': 'straight connections between twelve prescribed-date averages; no continuous-year estimate',
        'physical_uncertainty_claimed': False, 'confidence_interval_claimed': False})
    result_sha = io.sha(result_path)
    captions = f'''# 第2问图注与来源（修复轮）

本文件仅保存两幅图的图注与来源，不构成论文正文修订。

**镜场布局图。** 当前经独立确认的方案为 {freeze['name']}，共有 {design.n} 面定日镜，统一尺寸为 {design.width:g} m × {design.height:g} m，安装高度为 {design.installation_height:g} m。图中点表示镜面中心，不表示镜面占地轮廓；外圆为以场地原点为中心、半径 350 m 的中心布置边界，内圆以实际塔位 ({tx:g}, {ty:g}) m 为中心、半径 100 m，表示塔周禁布区。横纵坐标均以米计并采用相同比例。图中“确认”仅指通过本轮预登记数值工作判据。

![当前确认镜场布局](Q02-确认镜场布局-v002.png)

**月度单位面积功率图。** 每个点仅对应当月 21 日五个规定时刻的平均单位面积热功率，单位为 kW/m²；连线只帮助辨认这 12 个离散样本的变化，不代表连续全年插值或积分。误差棒表示该表项对应的数值工作指标 $U_q$ 的正负幅度，并未放大至最小可见长度；它可能小于点标记。该幅度不是物理模型误差、测量误差或置信区间。

![规定月样本的单位面积功率](Q02-月度单位面积功率-v002.png)

来源：工作记录/诊断结果/Q02-修复-v001/结果数据.json，SHA-256：{result_sha}。冻结清单及图片哈希、坐标范围、单位和生成器版本见本轮图表生成记录.json。图内英文标注使用 Pillow 内置字体，未读取外部字体文件。
'''
    caption_path = destination / 'Q02-图注与来源-v002.md'
    write_once(caption_path, captions.encode('utf-8'))
    report.update({'all_pass': True, 'figure_count': 2, 'candidate': freeze['name'], 'design_key': freeze['design_key'],
        'figures': [layout, monthly], 'caption': {'path': str(caption_path.relative_to(io.ROOT)), 'sha256': io.sha(caption_path)},
        'sources': {'results_json': str(result_path.relative_to(io.ROOT)), 'results_json_sha256': result_sha,
                    'frozen_candidate_sha256': io.sha(freeze_path), 'work_reconstruction_sha256': io.sha(work_path),
                    'confirmation_summary_sha256': io.sha(summary_path), 'compact_manifest_sha256': receipt['bundle_sha256'],
                    'compact_metadata_sha256': receipt['metadata_sha256'], 'compact_mirrors_sha256': receipt['mirrors_sha256']},
        'Pillow_version': PIL.__version__, 'font': 'Pillow internal default font; no external font paths',
        'new_optical_rays': 0, 'matplotlib_used': False, 'new_search': False, 'manuscript_modified': False,
        'visual_check_scope': 'PNG load/dimensions verified by entry; human-visible layout inspection remains for the root after execution.'})


def main():
    report = {'version': 'q02-repair-figures-v001', 'created': io.now(), 'all_pass': False, 'figure_count': 0}
    budget = io.Budget('confirmed_paper_figures', 'confirmation', START)
    try:
        create_figures(budget, report)
    except Exception:
        report.update(all_pass=False, execution_error=traceback.format_exc(), incomplete=True)
    finally:
        report['elapsed_seconds_before_save'] = time.perf_counter() - START
        report['budget_used_seconds_before_save'] = budget.used()
        report['generator_sha256'] = io.sha(Path(__file__))
        io.save(io.OUT / '图表生成记录.json', report)
        budget.finish('FAILED' if report.get('execution_error') else 'COMPLETED')
    print(json.dumps({'all_pass': report['all_pass'], 'figure_count': report['figure_count'],
                      'record': str(io.OUT / '图表生成记录.json')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    main()
