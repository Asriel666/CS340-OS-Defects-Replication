"""Render the personal progress Markdown as a searchable, linked Chinese PDF."""
import argparse
from html import escape
from pathlib import Path
import re
from urllib.parse import quote

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT/'docs/contributions/1230037310_钟峻瀚_2026-11-22.md'
DEFAULT_OUTPUT = ROOT/'output/pdf/1230037310_zhong_junhan_progress_2026-11-22.pdf'
BLUE = colors.HexColor('#153D66')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--font', type=Path, default=Path('C:/Windows/Fonts/msyh.ttc'))
    parser.add_argument('--bold-font', type=Path, default=Path('C:/Windows/Fonts/msyhbd.ttc'))
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error('A Chinese TrueType font is required; supply --font and optionally --bold-font.')
    pdfmetrics.registerFont(TTFont('ReportCJK', str(args.font), subfontIndex=0))
    pdfmetrics.registerFont(TTFont('ReportCJKBold', str(args.bold_font if args.bold_font.is_file() else args.font), subfontIndex=0))
    pdfmetrics.registerFontFamily('ReportCJK', normal='ReportCJK', bold='ReportCJKBold', italic='ReportCJK', boldItalic='ReportCJKBold')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyCJK', fontName='ReportCJK', fontSize=9.5, leading=15,
                              spaceAfter=6, wordWrap='CJK', textColor=colors.HexColor('#263442')))
    styles.add(ParagraphStyle(name='TitleCJK', parent=styles['BodyCJK'], fontName='ReportCJKBold',
                              fontSize=20, leading=28, textColor=BLUE, spaceAfter=16, keepWithNext=True))
    styles.add(ParagraphStyle(name='SectionCJK', parent=styles['BodyCJK'], fontName='ReportCJKBold',
                              fontSize=13, leading=19, textColor=BLUE, spaceBefore=12, spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle(name='SubCJK', parent=styles['SectionCJK'], fontSize=10.5, leading=16, spaceBefore=8))
    styles.add(ParagraphStyle(name='CellCJK', parent=styles['BodyCJK'], fontSize=8, leading=12, spaceAfter=0))
    styles.add(ParagraphStyle(name='CodeCJK', parent=styles['BodyCJK'], fontSize=8.5, leading=13,
                              backColor=colors.HexColor('#F0F4F8'), borderPadding=7, spaceBefore=4, spaceAfter=9))

    def inline(value):
        pieces = []
        last = 0
        for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', value):
            pieces.append(escape(value[last:match.start()]))
            label, target = match.groups()
            if not re.match(r'https?://', target):
                local = (args.source.resolve().parent/target.split('#')[0]).resolve()
                target = 'https://github.com/Asriel666/CS340-OS-Defects-Replication/blob/main/' + quote(local.relative_to(ROOT).as_posix())
            pieces.append('<link href="'+escape(target, quote=True)+'" color="#205B91">'+escape(label)+'</link>')
            last = match.end()
        pieces.append(escape(value[last:]))
        result = ''.join(pieces)
        result = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', result)
        result = re.sub(r'`([^`]+)`', r'<font color="#435A70">\1</font>', result)
        # Use ordinary hyphens in the print edition for predictable font coverage.
        return result.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')

    story = []
    lines = args.source.read_text(encoding='utf-8').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(escape(lines[i]))
                i += 1
            story.append(Paragraph('<br/>'.join(code), styles['CodeCJK']))
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [cell.strip() for cell in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                    rows.append(cells)
                i += 1
            width = 174*mm
            n = len(rows[0])
            weights = {2:[0.28,0.72],3:[0.22,0.30,0.48],4:[0.17,0.19,0.28,0.36],5:[0.14,0.16,0.22,0.24,0.24]}.get(n,[1/n]*n)
            if n == 4 and rows[0][-1] == '改动文件数':
                weights = [0.16, 0.40, 0.32, 0.12]
            data = [[Paragraph(inline(cell), styles['CellCJK']) for cell in row] for row in rows]
            table = Table(data, colWidths=[width*w for w in weights], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E5EDF5')),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7F9FC')]),
                ('LINEBELOW',(0,0),(-1,0),0.6,BLUE),
                ('LINEBELOW',(0,1),(-1,-1),0.25,colors.HexColor('#DCE3EB')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)
            ]))
            story.extend([table, Spacer(1,7)])
            continue
        elif line.startswith('# '):
            story.append(Paragraph(inline(line[2:]), styles['TitleCJK']))
        elif line.startswith('## '):
            story.append(Paragraph(inline(line[3:]), styles['SectionCJK']))
        elif line.startswith('### '):
            story.append(Paragraph(inline(line[4:]), styles['SubCJK']))
        elif line.startswith('- '):
            story.append(Paragraph('• '+inline(line[2:]), styles['BodyCJK']))
        else:
            story.append(Paragraph(inline(line), styles['BodyCJK']))
        i += 1

    def page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(0.5)
        canvas.line(18*mm, 282*mm, 192*mm, 282*mm)
        canvas.setFont('ReportCJK', 8)
        canvas.setFillColor(colors.HexColor('#607386'))
        canvas.drawString(18*mm, 285*mm, 'CS340 | 操作系统缺陷论文复现')
        canvas.drawString(18*mm, 13*mm, '1230037310 钟峻瀚 | 2026-11-22')
        canvas.drawRightString(192*mm, 13*mm, str(doc.page))
        canvas.restoreState()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(args.output), pagesize=(210*mm,297*mm),
                            leftMargin=18*mm, rightMargin=18*mm, topMargin=23*mm, bottomMargin=23*mm,
                            title='论文复现个人进度与贡献报告', author='1230037310 钟峻瀚',
                            subject='Progress, contribution evidence, reproducibility checks, and remaining work')
    doc.build(story, onFirstPage=page, onLaterPages=page)
    print(str(args.output))


if __name__ == '__main__':
    main()
