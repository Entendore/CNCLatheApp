import sys
import math
import re
import json
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QSlider, QTextEdit, QLineEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QSplitter,
    QToolBar, QFileDialog, QMessageBox, QFrame, QRadioButton,
    QFormLayout, QSizePolicy, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QTextCharFormat,
    QSyntaxHighlighter, QKeySequence, QIcon, QAction, QPalette,
    QConicalGradient, QRadialGradient, QLinearGradient
)

# ============================================================
# Machine State Model
# ============================================================
class MachineState:
    def __init__(self):
        self.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
        self.work_offset = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
        self.feed_rate = 100.0; self.spindle_speed = 1000; self.spindle_on = False; self.spindle_dir = 'CW'
        self.coolant = False; self.machine_state = 'IDLE'; self.current_line = 0; self.units = 'MM'; self.mode = 'ABS'
        self.tools = []; self.current_tool = 1; self.work_offsets = []; self.active_offset = 'G54'; self.log_messages = []
        self.lathe_diameter_mode = True; self.door_closed = True
        self.soft_limits = {'X': 500, 'Y': 300, 'Z': 400}
        self.override_feed = 100; self.override_rapid = 100; self.override_spindle = 100
        self.load_data()

    def load_data(self):
        if os.path.exists('cnc_tools.json'):
            with open('cnc_tools.json', 'r') as f: self.tools = json.load(f)
        else:
            self.tools = [
                {'id': 1, 'type': 'End Mill', 'diameter': 6.0, 'length': 50.0, 'x_offset': 0.0, 'z_offset': 0.0, 'comment': 'Roughing'},
                {'id': 2, 'type': 'Drill', 'diameter': 5.0, 'length': 40.0, 'x_offset': 0.0, 'z_offset': 0.0, 'comment': 'Center Drill'},
                {'id': 3, 'type': 'End Mill', 'diameter': 10.0, 'length': 55.0, 'x_offset': 0.0, 'z_offset': 0.0, 'comment': 'Finish Mill'},
                {'id': 4, 'type': 'Turning Tool', 'diameter': 0.0, 'length': 35.0, 'x_offset': 0.0, 'z_offset': 0.0, 'comment': 'OD Roughing'},
                {'id': 5, 'type': 'Grooving Tool', 'diameter': 3.0, 'length': 25.0, 'x_offset': 0.0, 'z_offset': 0.0, 'comment': 'Parting/Groove'},
            ]
        if os.path.exists('cnc_offsets.json'):
            with open('cnc_offsets.json', 'r') as f: self.work_offsets = json.load(f)
        else:
            self.work_offsets = [{'id': 'G54', 'X': 0.0, 'Y': 0.0, 'Z': 0.0}, {'id': 'G55', 'X': 100.0, 'Y': 0.0, 'Z': 0.0}]
    def save_data(self):
        with open('cnc_tools.json', 'w') as f: json.dump(self.tools, f, indent=2)
        with open('cnc_offsets.json', 'w') as f: json.dump(self.work_offsets, f, indent=2)
    def log(self, msg): self.log_messages.append(msg)
    def get_work_position(self, axis): return self.position[axis] - self.work_offset[axis]
    def jog(self, axis, distance):
        new_val = self.position[axis] + distance
        if abs(new_val) > self.soft_limits.get(axis, 9999): self.machine_state = 'ALARM'; self.log(f"SOFT LIMIT EXCEEDED on {axis}"); return
        self.position[axis] = new_val; self.log(f"JOG {axis} {distance:+.3f}")

# ============================================================
# Premium Analog Gauge Widget
# ============================================================
class AnalogGauge(QWidget):
    def __init__(self, title="", min_val=0, max_val=100, parent=None):
        super().__init__(parent)
        self.title, self.min_val, self.max_val = title, min_val, max_val
        self.value = 0; self.setFixedSize(130, 110)

    def set_value(self, val): self.value = val; self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(15, 10, 100, 80); start_angle = 210 * 16; span_angle = -240 * 16

        # Outer Bezel
        gradient = QRadialGradient(65, 50, 60); gradient.setColorAt(0.8, QColor("#444")); gradient.setColorAt(1.0, QColor("#222"))
        painter.setBrush(QBrush(gradient)); painter.setPen(Qt.NoPen); painter.drawEllipse(5, 0, 120, 110)
        
        # Inner Background
        painter.setBrush(QBrush(QColor("#1a1a1a"))); painter.drawEllipse(10, 5, 110, 100)

        # Background Arc
        painter.setPen(QPen(QColor("#222222"), 8, Qt.SolidLine, Qt.RoundCap)); painter.drawArc(rect, start_angle, span_angle)

        # Ticks and Text
        painter.setPen(QPen(QColor("#888"), 1))
        for i in range(9):
            pct = i / 8.0; angle_rad = math.radians(210 - 240 * pct)
            x1 = 65 + 42 * math.cos(angle_rad); y1 = 50 - 42 * math.sin(angle_rad)
            x2 = 65 + 48 * math.cos(angle_rad); y2 = 50 - 48 * math.sin(angle_rad)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            val = self.min_val + (self.max_val - self.min_val) * pct
            painter.setFont(QFont("Consolas", 5)); painter.drawText(QRectF(x2-10, y2-6, 20, 12), Qt.AlignCenter, f"{val:.0f}")

        # Value Arc
        pct = (self.value - self.min_val) / (self.max_val - self.min_val) if (self.max_val - self.min_val) != 0 else 0
        color = QColor("#00ff88") if pct < 0.7 else QColor("#ffaa00") if pct < 0.9 else QColor("#ff3333")
        painter.setPen(QPen(color, 8, Qt.SolidLine, Qt.RoundCap)); painter.drawArc(rect, start_angle, int(span_angle * pct))

        # Needle
        center = QPointF(65, 50); angle_rad = math.radians(210 - 240 * pct)
        end_x = center.x() + 38 * math.cos(angle_rad); end_y = center.y() - 38 * math.sin(angle_rad)
        painter.setPen(Qt.NoPen)
        path = QPainterPath(); path.moveTo(center); path.lineTo(end_x-2, end_y-2); path.lineTo(end_x+2, end_y+2); path.closeSubpath()
        painter.setBrush(QBrush(QColor("#ff3333"))); painter.drawPath(path)

        # Center Cap
        cap_grad = QRadialGradient(65, 50, 5); cap_grad.setColorAt(0, QColor("#ccc")); cap_grad.setColorAt(1, QColor("#666"))
        painter.setBrush(QBrush(cap_grad)); painter.drawEllipse(center, 5, 5)

        # Glass Effect
        glass_grad = QRadialGradient(65, 35, 40); glass_grad.setColorAt(0, QColor(255, 255, 255, 40)); glass_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(glass_grad)); painter.setPen(Qt.NoPen); painter.drawEllipse(15, 8, 90, 50)

        # Text
        painter.setPen(QColor("#ffffff")); painter.setFont(QFont("Consolas", 11, QFont.Bold))
        painter.drawText(QRectF(0, 70, 130, 20), Qt.AlignCenter, f"{self.value:.0f}")
        painter.setPen(QColor("#888888")); painter.setFont(QFont("Consolas", 7))
        painter.drawText(QRectF(0, 85, 130, 20), Qt.AlignCenter, self.title)

# ============================================================
# DRO Widget
# ============================================================
class DROWidget(QGroupBox):
    def __init__(self, machine_state, parent=None):
        super().__init__("📊 Digital Readout", parent); self.machine = machine_state; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); layout.setSpacing(4); self.axis_labels = {}
        axis_colors = {'X': '#ff3333', 'Y': '#33ff33', 'Z': '#3399ff'}
        for axis in ['X', 'Y', 'Z']:
            frame = QFrame(); frame.setStyleSheet("QFrame { background-color: #050505; border: 2px inset #222; border-radius: 4px; padding: 2px; }")
            fl = QHBoxLayout(frame); fl.setContentsMargins(6, 2, 6, 2); fl.setSpacing(4)
            al = QLabel(f"{axis}:"); al.setStyleSheet(f"color: {axis_colors[axis]}; font-size: 18px; font-weight: bold; font-family: Consolas;"); fl.addWidget(al)
            vl = QLabel("0.000"); vl.setAlignment(Qt.AlignRight | Qt.AlignVCenter); vl.setStyleSheet(f"color: {axis_colors[axis]}; font-size: 32px; font-weight: bold; font-family: Consolas; background: transparent; letter-spacing: 2px;"); fl.addWidget(vl)
            self.axis_labels[axis] = vl; ul = QLabel("mm"); ul.setStyleSheet("color: #444; font-size: 10px; font-family: Consolas;"); fl.addWidget(ul); layout.addWidget(frame)
        self.state_label = QLabel("● IDLE"); self.state_label.setAlignment(Qt.AlignCenter); self.state_label.setStyleSheet("color: #44ff44; font-size: 14px; font-weight: bold; padding: 3px; background: #050505; border: 1px solid #222; border-radius: 3px;"); layout.addWidget(self.state_label)
        info_frame = QFrame(); info_frame.setStyleSheet("background-color: #050505; border: 1px solid #222; border-radius: 3px; padding: 1px;"); info_inner = QHBoxLayout(info_frame); info_inner.setContentsMargins(4, 1, 4, 1)
        self.tool_lbl, self.offset_lbl, self.mode_lbl, self.dr_lbl = QLabel("T01"), QLabel("G54"), QLabel("ABS"), QLabel("DIA")
        for lbl in [self.tool_lbl, self.offset_lbl, self.mode_lbl, self.dr_lbl]: lbl.setStyleSheet("color: #ffaa00; font-size: 11px; font-weight: bold; font-family: Consolas;"); lbl.setAlignment(Qt.AlignCenter); info_inner.addWidget(lbl)
        self.dr_btn = QPushButton("D/R"); self.dr_btn.setFixedSize(30, 20); self.dr_btn.setStyleSheet("QPushButton { background: #224422; color: #aaa; font-size: 9px; font-weight: bold; border: 1px solid #336633; border-radius: 2px; } QPushButton:hover { background: #336633; color: #fff; }"); self.dr_btn.clicked.connect(self.toggle_dr); info_inner.addWidget(self.dr_btn)
        layout.addWidget(info_frame)
    def toggle_dr(self): self.machine.lathe_diameter_mode = not self.machine.lathe_diameter_mode; self.update_display()
    def update_display(self):
        for axis in ['X', 'Y', 'Z']:
            val = self.machine.position[axis] if self.machine.mode == 'ABS' else self.machine.get_work_position(axis)
            if axis == 'X' and self.machine.lathe_diameter_mode: val *= 2
            self.axis_labels[axis].setText(f"{val:9.3f}")
        state_colors = {'IDLE': '#44ff44', 'RUNNING': '#44aaff', 'PAUSED': '#ffaa00', 'ERROR': '#ff4444', 'ALARM': '#ff0000'}
        color = state_colors.get(self.machine.machine_state, '#ffffff')
        self.state_label.setText(f"● {self.machine.machine_state}"); self.state_label.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; padding: 3px; background: #050505; border: 1px solid #222; border-radius: 3px;")
        self.tool_lbl.setText(f"T{self.machine.current_tool:02d}"); self.offset_lbl.setText(self.machine.active_offset); self.mode_lbl.setText(self.machine.mode); self.dr_lbl.setText("DIA" if self.machine.lathe_diameter_mode else "RAD")

# ============================================================
# Jog Control Widget
# ============================================================
class JogControl(QGroupBox):
    jog_clicked = Signal(str, float)
    def __init__(self, parent=None): super().__init__("🕹 Jog Control", parent); self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); sl = QHBoxLayout(); sl.addWidget(QLabel("Step:")); self.step_combo = QComboBox(); self.step_combo.addItems(["0.001", "0.01", "0.1", "1.0", "10.0", "100.0"]); self.step_combo.setCurrentIndex(3); sl.addWidget(self.step_combo); layout.addLayout(sl)
        grid = QGridLayout(); grid.setSpacing(3)
        for text, row, col, axis, d in [('X-', 1, 0, 'X', -1), ('X+', 1, 2, 'X', 1), ('Y-', 2, 0, 'Y', -1), ('Y+', 2, 2, 'Y', 1), ('Z-', 3, 0, 'Z', -1), ('Z+', 3, 2, 'Z', 1)]:
            bg = '#225522' if d > 0 else '#552222'; hover_bg = '#338833' if d > 0 else '#883333'
            btn = QPushButton(text); btn.setStyleSheet(f"QPushButton {{ background-color: {bg}; color: white; font-weight: bold; min-width: 50px; min-height: 32px; border: 1px solid {hover_bg}; border-radius: 4px; font-size: 13px; }} QPushButton:hover {{ background-color: {hover_bg}; }} QPushButton:pressed {{ background-color: #111; }}")
            btn.pressed.connect(lambda a=axis, dr=d: self.do_jog(a, dr)); grid.addWidget(btn, row, col)
        for row, axis in [(1, 'X'), (2, 'Y'), (3, 'Z')]:
            home_btn = QPushButton(f"⌂ {axis}"); home_btn.setStyleSheet("QPushButton { background-color: #333; color: #ddd; font-size: 11px; min-height: 32px; border: 1px solid #555; border-radius: 4px; } QPushButton:hover { background-color: #444; } QPushButton:pressed { background-color: #111; }")
            home_btn.pressed.connect(lambda a=axis: self.jog_clicked.emit(a, -99999)); grid.addWidget(home_btn, row, 1)
        layout.addLayout(grid)
    def do_jog(self, axis, direction): self.jog_clicked.emit(axis, direction * float(self.step_combo.currentText()))

# ============================================================
# Spindle & Feed Control Widget
# ============================================================
class SpindleFeedControl(QGroupBox):
    spindle_toggled = Signal(bool); speed_changed = Signal(int); feed_changed = Signal(float); coolant_toggled = Signal(bool)
    def __init__(self, machine_state, parent=None): super().__init__("⚙ Spindle / Feed", parent); self.machine = machine_state; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); gl = QHBoxLayout(); self.rpm_gauge = AnalogGauge("RPM", 0, 4000); self.feed_gauge = AnalogGauge("FEED", 0, 2000); gl.addWidget(self.rpm_gauge); gl.addWidget(self.feed_gauge); layout.addLayout(gl)
        spl = QHBoxLayout(); spl.addWidget(QLabel("Spindle:")); self.spindle_btn = QPushButton("OFF"); self.spindle_btn.setCheckable(True); self.spindle_btn.setStyleSheet("QPushButton { background-color: #552222; color: #ffaaaa; font-weight: bold; min-height: 24px; border: 1px solid #883333; border-radius: 4px; } QPushButton:checked { background-color: #225522; color: #aaffaa; border: 1px solid #338833; }"); self.spindle_btn.clicked.connect(self.toggle_spindle); spl.addWidget(self.spindle_btn); self.dir_btn = QPushButton("CW"); self.dir_btn.setCheckable(True); self.dir_btn.setStyleSheet("QPushButton { background-color: #333; color: #aaa; min-height: 24px; border: 1px solid #555; border-radius: 4px; } QPushButton:checked { background-color: #553322; color: #ffaa88; border: 1px solid #885533; }"); self.dir_btn.clicked.connect(lambda c: self.dir_btn.setText("CCW" if c else "CW")); spl.addWidget(self.dir_btn); layout.addLayout(spl)
        sl = QHBoxLayout(); sl.addWidget(QLabel("S:")); self.speed_spin = QSpinBox(); self.speed_spin.setRange(0, 30000); self.speed_spin.setValue(1000); self.speed_spin.setSingleStep(100); self.speed_spin.valueChanged.connect(lambda v: self.speed_changed.emit(v)); sl.addWidget(self.speed_spin); layout.addLayout(sl)
        fl = QHBoxLayout(); fl.addWidget(QLabel("F:")); self.feed_spin = QDoubleSpinBox(); self.feed_spin.setRange(0, 50000); self.feed_spin.setValue(100.0); self.feed_spin.setSingleStep(10); self.feed_spin.setSuffix(" mm/min"); self.feed_spin.valueChanged.connect(lambda v: self.feed_changed.emit(v)); fl.addWidget(self.feed_spin); layout.addLayout(fl)
        self.coolant_btn = QPushButton("Coolant OFF"); self.coolant_btn.setCheckable(True); self.coolant_btn.setStyleSheet("QPushButton { background-color: #333; color: #aaa; font-weight: bold; min-height: 22px; border: 1px solid #555; border-radius: 4px; } QPushButton:checked { background-color: #224488; color: #aaccff; border: 1px solid #3366aa; }"); self.coolant_btn.clicked.connect(lambda c: self.coolant_toggled.emit(c)); layout.addWidget(self.coolant_btn)
    def toggle_spindle(self, checked): self.spindle_btn.setText("ON" if checked else "OFF"); self.machine.spindle_on = checked; self.spindle_toggled.emit(checked)
    def update_gauges(self): self.rpm_gauge.set_value(self.machine.spindle_speed * (self.machine.override_spindle / 100.0)); self.feed_gauge.set_value(self.machine.feed_rate * (self.machine.override_feed / 100.0))

# ============================================================
# G-Code Syntax Highlighter
# ============================================================
class GCodeHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): super().__init__(parent); self.highlighting_rules = []; g_fmt = QTextCharFormat(); g_fmt.setForeground(QColor("#44aaff")); g_fmt.setFontWeight(QFont.Bold); self.highlighting_rules.append((re.compile(r'\bG\d+\.?\d*\b'), g_fmt)); m_fmt = QTextCharFormat(); m_fmt.setForeground(QColor("#ff8844")); m_fmt.setFontWeight(QFont.Bold); self.highlighting_rules.append((re.compile(r'\bM\d+\b'), m_fmt)); coord_fmt = QTextCharFormat(); coord_fmt.setForeground(QColor("#44ff88")); self.highlighting_rules.append((re.compile(r'\b[XYZABCUVWFSTIK]\s*-?\d+\.?\d*'), coord_fmt)); comment_fmt = QTextCharFormat(); comment_fmt.setForeground(QColor("#555555")); comment_fmt.setFontItalic(True); self.highlighting_rules.append((re.compile(r';.*$|\(.*?\)'), comment_fmt))
    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text): self.setFormat(match.start(), match.end() - match.start(), fmt)

# ============================================================
# G-Code Editor Widget
# ============================================================
class GCodeEditor(QWidget):
    def __init__(self, parent=None): super().__init__(parent); self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); toolbar = QToolBar(); toolbar.setIconSize(QSize(16, 16)); toolbar.addAction("📄 New", self.new_file); toolbar.addAction("📂 Open", self.open_file); toolbar.addAction("💾 Save", self.save_file); toolbar.addSeparator(); toolbar.addAction("📥 Mill Sample", self.load_sample_mill); toolbar.addAction("🔩 Lathe Sample", self.load_sample_lathe); layout.addWidget(toolbar)
        el = QHBoxLayout(); el.setSpacing(0); self.line_numbers = QTextEdit(); self.line_numbers.setReadOnly(True); self.line_numbers.setMaximumWidth(40); self.line_numbers.setStyleSheet("QTextEdit { background-color: #111; color: #555; border: none; font-family: Consolas; font-size: 12px; }"); self.line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor = QTextEdit(); self.editor.setStyleSheet("QTextEdit { background-color: #1a1a1a; color: #ddd; font-family: Consolas; font-size: 12px; border: none; }"); self.highlighter = GCodeHighlighter(self.editor.document()); self.editor.verticalScrollBar().valueChanged.connect(lambda v: self.line_numbers.verticalScrollBar().setValue(v)); self.editor.textChanged.connect(self.update_line_numbers)
        el.addWidget(self.line_numbers); el.addWidget(self.editor); layout.addLayout(el); self.load_sample_mill()
    def update_line_numbers(self): self.line_numbers.setPlainText('\n'.join(str(i) for i in range(1, self.editor.toPlainText().count('\n') + 2)))
    def new_file(self): self.editor.clear()
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open G-Code", "", "G-Code (*.nc *.gcode *.ngc *.txt);;All Files (*)")
        if path:
            with open(path, 'r') as f: self.editor.setPlainText(f.read())
    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save G-Code", "", "G-Code (*.nc *.gcode *.ngc);;All Files (*)")
        if path:
            with open(path, 'w') as f: f.write(self.editor.toPlainText())
    def load_sample_mill(self):
        self.editor.setPlainText("""(=============================================)
( Complex CNC Milling Example: Plate Profile )
( with Rounded Corners & Drill Holes          )
(=============================================)
G90 G21 G17           (Absolute, Metric, XY Plane)
G54                    (Work Offset 1)
T01 M06                (Tool 1: 10mm End Mill)
S2500 M03              (Spindle On CW 2500 RPM)
G00 X0 Y0 Z10         (Rapid to origin)
G00 X20 Y20           (Rapid to start point)
G01 Z-3 F150          (Plunge to depth 1)
G01 X80 F400          (Cut bottom edge)
G02 X90 Y30 I0 J10    (Arc bottom-right corner R10)
G01 Y70               (Cut right edge)
G02 X80 Y80 I-10 J0   (Arc top-right corner R10)
G01 X20               (Cut top edge)
G02 X10 Y70 I0 J-10   (Arc top-left corner R10)
G01 Y30               (Cut left edge)
G02 X20 Y20 I10 J0    (Arc bottom-left corner R10)
G01 Z-6 F150          (Plunge to depth 2)
G01 X80 F400          (Second pass bottom)
G02 X90 Y30 I0 J10
G01 Y70
G02 X80 Y80 I-10 J0
G01 X20
G02 X10 Y70 I0 J-10
G01 Y30
G02 X20 Y20 I10 J0
G00 Z10               (Retract)
T02 M06                (Tool 2: 5mm Drill)
S4000 M03
G00 X20 Y20           (Hole 1)
G01 Z-12 F80; G00 Z10
G00 X80 Y20           (Hole 2)
G01 Z-12 F80; G00 Z10
G00 X80 Y80           (Hole 3)
G01 Z-12 F80; G00 Z10
G00 X20 Y80           (Hole 4)
G01 Z-12 F80; G00 Z10
G28 Z0; G28 X0 Y0; M05; M30""")
    def load_sample_lathe(self):
        self.editor.setPlainText("""(=============================================)
( Complex CNC Lathe Example: Profile Shaft   )
( Chamfer, Taper, Radius, Groove            )
(=============================================)
G90 G21 G18           (Absolute, Metric, XZ Plane)
G54; T0404 M06        (Tool 4: OD Turning); S1200 M03
G00 X54 Z5; G01 Z0 F100; G01 X-1 F80; G00 Z2
( Rough Pass )
G00 X48; G01 Z-85 F150; G00 X50; Z2
( Finish Profile )
G00 X0; G01 Z0 F100
G01 X30 Z-2 F80       (Chamfer)
G01 Z-30 F120         (Straight D30)
G01 X40 Z-50 F100     (Taper to D40)
G01 Z-60 F120         (Straight D40)
G03 X50 Z-70 I0 K-10 F80 (Radius R10 to D50)
G01 Z-85 F120         (Straight D50)
G00 X54; Z5
( Groove Operation )
T0505 M06; S800 M03
G00 X42 Z-30; G01 X32 F40
G04 P500              (Dwell 0.5s)
G00 X42; Z5
G28 Z0; G28 X0; M05; M30""")
    def get_gcode_lines(self): return self.editor.toPlainText().split('\n')

# ============================================================
# Toolpath View Widget
# ============================================================
class ToolpathView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.toolpath_segments = []; self.rapid_segments = []; self.current_pos = {'X': 0, 'Y': 0, 'Z': 0}
        self.scale = 4.0; self.offset_x = 50; self.offset_y = 50; self.show_rapid = True; self.show_grid = True
        self.view_mode = 'XY'; self.dragging = False; self.last_mouse = None; self.highlight_line = -1; self.sim_trail = []
        self.setMinimumSize(400, 300); self.setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)

    def parse_gcode(self, gcode_text):
        self.toolpath_segments = []; self.rapid_segments = []; self.sim_trail = []
        pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}; current_mode = 'G00'
        for line_num, line in enumerate(gcode_text.split('\n')):
            line = re.sub(r';.*$|\(.*?\)', '', line).strip()
            if not line or line.startswith('%'): continue
            for g in re.findall(r'G(\d+)', line, re.IGNORECASE):
                code = int(g)
                if code == 0: current_mode = 'G00'
                elif code == 1: current_mode = 'G01'
                elif code == 2: current_mode = 'G02'
                elif code == 3: current_mode = 'G03'
            x_m = re.search(r'X\s*(-?\d+\.?\d*)', line, re.IGNORECASE); y_m = re.search(r'Y\s*(-?\d+\.?\d*)', line, re.IGNORECASE); z_m = re.search(r'Z\s*(-?\d+\.?\d*)', line, re.IGNORECASE)
            i_m = re.search(r'I\s*(-?\d+\.?\d*)', line, re.IGNORECASE); j_m = re.search(r'J\s*(-?\d+\.?\d*)', line, re.IGNORECASE); k_m = re.search(r'K\s*(-?\d+\.?\d*)', line, re.IGNORECASE)
            new_pos = pos.copy()
            if x_m: new_pos['X'] = float(x_m.group(1)); 
            if y_m: new_pos['Y'] = float(y_m.group(1))
            if z_m: new_pos['Z'] = float(z_m.group(1))
            if x_m or y_m or z_m:
                seg = {'from': pos.copy(), 'to': new_pos.copy(), 'type': current_mode, 'line': line_num}
                if i_m: seg['I'] = float(i_m.group(1)); 
                if j_m: seg['J'] = float(j_m.group(1))
                if k_m: seg['K'] = float(k_m.group(1))
                if current_mode == 'G00': self.rapid_segments.append(seg)
                else: self.toolpath_segments.append(seg)
                pos = new_pos.copy()
        self.current_pos = pos; self.auto_scale(); self.update()

    def auto_scale(self):
        all_segs = self.toolpath_segments + self.rapid_segments
        if not all_segs: return
        all_x, all_y = [], []
        for s in all_segs:
            p1, p2 = self._extract_iso_coords(s['from']), self._extract_iso_coords(s['to'])
            all_x.extend([p1[0], p2[0]]); all_y.extend([p1[1], p2[1]])
        if not all_x: return
        min_x, max_x = min(all_x), max(all_x); min_y, max_y = min(all_y), max(all_y)
        range_x = max(max_x - min_x, 1); range_y = max(max_y - min_y, 1)
        margin = 60; w = max(self.width() - 2 * margin, 100); h = max(self.height() - 2 * margin, 100)
        self.scale = min(w / range_x, h / range_y) * 0.85
        self.offset_x = margin + (w - range_x * self.scale) / 2 - min_x * self.scale
        self.offset_y = margin + (h - range_y * self.scale) / 2 + max_y * self.scale

    def _extract_iso_coords(self, pos):
        if self.view_mode == 'XY': return pos['X'], pos['Y']
        elif self.view_mode == 'XZ': return pos['Z'], pos['X']
        elif self.view_mode == 'ISO':
            angle = math.pi / 6; iso_x = (pos['X'] - pos['Y']) * math.cos(angle); iso_y = pos['Z'] - (pos['X'] + pos['Y']) * math.sin(angle); return iso_x, iso_y

    def world_to_screen(self, x, y): return x * self.scale + self.offset_x, -y * self.scale + self.offset_y

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        # Gradient Background
        bg_grad = QLinearGradient(0, 0, 0, self.height()); bg_grad.setColorAt(0, QColor("#0a0a18")); bg_grad.setColorAt(1, QColor("#050510"))
        painter.fillRect(self.rect(), bg_grad)
        if self.show_grid: self._draw_grid(painter)
        if self.show_rapid:
            painter.setPen(QPen(QColor("#333355"), 1, Qt.DashLine))
            for seg in self.rapid_segments:
                p1, p2 = self._extract_iso_coords(seg['from']), self._extract_iso_coords(seg['to'])
                x1, y1 = self.world_to_screen(p1[0], p1[1]); x2, y2 = self.world_to_screen(p2[0], p2[1]); painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        for seg in self.toolpath_segments:
            z = seg['to']['Z']; color = QColor("#44aaff") if z > 0 else QColor("#44ff88") if z > -2 else QColor("#ffaa44") if z > -5 else QColor("#ff4444")
            if seg['line'] == self.highlight_line: color = QColor("#ffffff")
            painter.setPen(QPen(color, 2 if seg['line'] != self.highlight_line else 3))
            if seg['type'] == 'G01':
                p1, p2 = self._extract_iso_coords(seg['from']), self._extract_iso_coords(seg['to'])
                x1, y1 = self.world_to_screen(p1[0], p1[1]); x2, y2 = self.world_to_screen(p2[0], p2[1]); painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            elif seg['type'] in ('G02', 'G03'): self._draw_arc(painter, seg)
        if len(self.sim_trail) > 1:
            painter.setPen(QPen(QColor("#ff00ff"), 2, Qt.DashDotLine))
            for i in range(len(self.sim_trail) - 1):
                p1, p2 = self._extract_iso_coords(self.sim_trail[i]), self._extract_iso_coords(self.sim_trail[i+1])
                x1, y1 = self.world_to_screen(p1[0], p1[1]); x2, y2 = self.world_to_screen(p2[0], p2[1]); painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # Glowing Crosshair
        p_curr = self._extract_iso_coords(self.current_pos); cx, cy = self.world_to_screen(p_curr[0], p_curr[1])
        painter.setPen(QPen(QColor(255, 0, 0, 100), 6)); painter.drawLine(int(cx)-12, int(cy), int(cx)+12, int(cy)); painter.drawLine(int(cx), int(cy)-12, int(cx), int(cy)+12)
        painter.setPen(QPen(QColor("#ff0000"), 2)); painter.drawLine(int(cx)-10, int(cy), int(cx)+10, int(cy)); painter.drawLine(int(cx), int(cy)-10, int(cx), int(cy)+10)
        painter.setPen(QPen(QColor("#ff0000"), 1)); painter.setBrush(Qt.NoBrush); painter.drawEllipse(int(cx)-6, int(cy)-6, 12, 12)
        painter.end()

    def _draw_arc(self, painter, seg):
        p1_iso, p2_iso = self._extract_iso_coords(seg['from']), self._extract_iso_coords(seg['to'])
        cx1, cy1 = self.world_to_screen(p1_iso[0], p1_iso[1]); cx2, cy2 = self.world_to_screen(p2_iso[0], p2_iso[1])
        i, j, k = seg.get('I', 0), seg.get('J', 0), seg.get('K', 0)
        if self.view_mode == 'XZ': center_x = seg['from']['X'] + i; center_z = seg['from']['Z'] + k; sc_z, sc_x = self.world_to_screen(center_z, center_x); r = math.sqrt((cx1 - sc_z)**2 + (cy1 - sc_x)**2); start_angle = math.atan2(cy1 - sc_x, cx1 - sc_z); end_angle = math.atan2(cy2 - sc_x, cx2 - sc_z); center_2d = QPointF(sc_z, sc_x)
        else: center_x = seg['from']['X'] + i; center_y = seg['from']['Y'] + j; scx, scy = self.world_to_screen(center_x, center_y); r = math.sqrt((cx1 - scx)**2 + (cy1 - scy)**2); start_angle = math.atan2(cy1 - scy, cx1 - scx); end_angle = math.atan2(cy2 - scy, cx2 - scx); center_2d = QPointF(scx, scy)
        if r < 0.5: return
        sweep = start_angle - end_angle if seg['type'] == 'G02' else end_angle - start_angle
        if sweep <= 0: sweep += 2 * math.pi
        steps = max(int(sweep * 30), 16); points = []
        for step in range(steps + 1):
            t = step / steps; angle = start_angle - t * sweep if seg['type'] == 'G02' else start_angle + t * sweep
            points.append(QPointF(center_2d.x() + r * math.cos(angle), center_2d.y() + r * math.sin(angle)))
        if len(points) > 1: painter.drawPolyline(points)

    def _draw_grid(self, painter):
        painter.setPen(QPen(QColor("#1a1a2e"), 1, Qt.DotLine))
        for x in range(-500, 500, 10):
            sx, _ = self.world_to_screen(x, 0)
            if 0 <= sx <= self.width(): painter.drawLine(int(sx), 0, int(sx), self.height())
        for y in range(-500, 500, 10):
            _, sy = self.world_to_screen(0, y)
            if 0 <= sy <= self.height(): painter.drawLine(0, int(sy), self.width(), int(sy))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15; mx, my = event.position().x(), event.position().y()
        self.offset_x = mx - (mx - self.offset_x) * factor; self.offset_y = my - (my - self.offset_y) * factor; self.scale *= factor; self.update()
    def mousePressEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton): self.dragging = True; self.last_mouse = event.position()
    def mouseMoveEvent(self, event):
        if self.dragging and self.last_mouse: self.offset_x += event.position().x() - self.last_mouse.x(); self.offset_y += event.position().y() - self.last_mouse.y(); self.last_mouse = event.position(); self.update()
    def mouseReleaseEvent(self, event): self.dragging = False; self.last_mouse = None
    def resizeEvent(self, event): self.auto_scale(); super().resizeEvent(event)

# ============================================================
# Right Panel Widgets
# ============================================================
class ToolManager(QWidget):
    tool_selected = Signal(int)
    def __init__(self, machine_state, parent=None): super().__init__(parent); self.machine = machine_state; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); self.table = QTableWidget(); self.table.setColumnCount(7); self.table.setHorizontalHeaderLabels(["T#", "Type", "Dia", "Len", "X Off", "Z Off", "Comment"]); self.table.horizontalHeader().setStretchLastSection(True); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.DoubleClicked); self.populate_table(); layout.addWidget(self.table)
        bl = QHBoxLayout()
        for t, s in [("➕ Add", self.add_tool), ("🗑 Del", self.delete_tool), ("✅ Select", self.select_tool), ("💾 Save", self.save_changes)]: b = QPushButton(t); b.clicked.connect(s); bl.addWidget(b)
        layout.addLayout(bl)
    def populate_table(self):
        self.table.setRowCount(len(self.machine.tools))
        for i, tool in enumerate(self.machine.tools):
            for j, val in enumerate([str(tool['id']), tool['type'], f"{tool['diameter']:.1f}", f"{tool['length']:.1f}", f"{tool['x_offset']:.3f}", f"{tool['z_offset']:.3f}", tool['comment']]): item = QTableWidgetItem(val); item.setBackground(QColor("#113311")) if tool['id'] == self.machine.current_tool and j == 0 else None; self.table.setItem(i, j, item)
    def add_tool(self): self.machine.tools.append({'id': max((t['id'] for t in self.machine.tools), default=0) + 1, 'type': 'End Mill', 'diameter': 6.0, 'length': 50.0, 'x_offset': 0.0, 'z_offset': 0.0, 'comment': 'New'}); self.populate_table()
    def delete_tool(self): r = self.table.currentRow(); self.machine.tools.pop(r) if r >= 0 and len(self.machine.tools) > 1 else None; self.populate_table()
    def select_tool(self): r = self.table.currentRow(); self.machine.current_tool = self.machine.tools[r]['id'] if r >= 0 else self.machine.current_tool; self.tool_selected.emit(self.machine.current_tool); self.populate_table()
    def save_changes(self):
        for i in range(self.table.rowCount()):
            if i < len(self.machine.tools): t = self.machine.tools[i]; t['type'] = self.table.item(i, 1).text(); t['diameter'] = float(self.table.item(i, 2).text()); t['length'] = float(self.table.item(i, 3).text()); t['x_offset'] = float(self.table.item(i, 4).text()); t['z_offset'] = float(self.table.item(i, 5).text()); t['comment'] = self.table.item(i, 6).text()
        self.machine.save_data()

class WorkOffsetsWidget(QWidget):
    def __init__(self, machine_state, parent=None): super().__init__(parent); self.machine = machine_state; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); self.table = QTableWidget(); self.table.setColumnCount(4); self.table.setHorizontalHeaderLabels(["Offset", "X", "Y", "Z"]); self.table.horizontalHeader().setStretchLastSection(True); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.DoubleClicked); self.populate_table(); layout.addWidget(self.table)
        bl = QHBoxLayout(); ab = QPushButton("💾 Apply & Save"); ab.clicked.connect(self.apply_changes); bl.addWidget(ab); acb = QPushButton("✅ Activate"); acb.clicked.connect(self.activate_offset); bl.addWidget(acb); layout.addLayout(bl)
    def populate_table(self):
        self.table.setRowCount(len(self.machine.work_offsets))
        for i, off in enumerate(self.machine.work_offsets):
            for j, val in enumerate([off['id'], f"{off['X']:.3f}", f"{off['Y']:.3f}", f"{off['Z']:.3f}"]): item = QTableWidgetItem(val); item.setBackground(QColor("#112233")) if off['id'] == self.machine.active_offset and j == 0 else None; self.table.setItem(i, j, item)
    def apply_changes(self):
        for i in range(self.table.rowCount()): off = self.machine.work_offsets[i]; off['X'] = float(self.table.item(i, 1).text()); off['Y'] = float(self.table.item(i, 2).text()); off['Z'] = float(self.table.item(i, 3).text())
        self.machine.save_data(); self.populate_table()
    def activate_offset(self): r = self.table.currentRow(); self.machine.active_offset = self.machine.work_offsets[r]['id'] if r >= 0 else self.machine.active_offset; self.populate_table()

class MDIWidget(QWidget):
    command_sent = Signal(str)
    def __init__(self, parent=None): super().__init__(parent); self.command_history = []; self.history_idx = -1; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); self.output = QTextEdit(); self.output.setReadOnly(True); self.output.setStyleSheet("QTextEdit { background-color: #050505; color: #44ff88; font-family: Consolas; font-size: 12px; border: 1px solid #222; }"); layout.addWidget(self.output)
        il = QHBoxLayout(); il.addWidget(QLabel("MDI >")); self.input = QLineEdit(); self.input.setStyleSheet("QLineEdit { background-color: #050505; color: #44ff88; font-family: Consolas; font-size: 12px; border: 1px solid #222; padding: 4px; }"); self.input.returnPressed.connect(self.send_command); il.addWidget(self.input); sb = QPushButton("Send"); sb.clicked.connect(self.send_command); il.addWidget(sb); layout.addLayout(il)
    def send_command(self): cmd = self.input.text().strip(); self.output.append(f"<span style='color:#ffaa00'>&gt; {cmd}</span>") if cmd else None; self.command_history.append(cmd) if cmd else None; self.command_sent.emit(cmd) if cmd else None; self.input.clear()
    def append_output(self, text): self.output.append(text)

class MacroPanel(QWidget):
    macro_triggered = Signal(str)
    def __init__(self, parent=None): super().__init__(parent); self.macros = {"Home All": "G28 Z0\nG28 X0 Y0", "Safe Z": "G00 Z50", "Measure Tool": "G00 X0 Y0\nG00 Z-50\nG92 Z0", "Spin Up": "M03 S3000", "Coolant On": "M08", "Program End": "M05\nM09\nM30"}; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self)
        for name, code in self.macros.items(): btn = QPushButton(name); btn.setStyleSheet("QPushButton { text-align: left; padding: 8px; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333, stop:1 #222); border: 1px solid #444; border-radius: 4px; } QPushButton:hover { background: #444; } QPushButton:pressed { background: #111; }"); btn.clicked.connect(lambda c=code: self.macro_triggered.emit(c)); layout.addWidget(btn)
        layout.addStretch()

# ============================================================
# Machine Control & Override Panels
# ============================================================
class MachineControlPanel(QGroupBox):
    cycle_start = Signal(); feed_hold = Signal(); stop = Signal(); e_stop = Signal(); home_all = Signal(); reset_alarm = Signal()
    def __init__(self, parent=None): super().__init__("🎮 Control", parent); self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); 
        self.estop_btn = QPushButton("⟲ E-STOP"); self.estop_btn.setMinimumHeight(50)
        self.estop_btn.setStyleSheet("QPushButton { background-color: #cc0000; color: white; font-size: 18px; font-weight: bold; border: 4px solid #ffcc00; border-radius: 8px; } QPushButton:hover { background-color: #ff0000; } QPushButton:pressed { background-color: #880000; border-color: #fff; }")
        self.estop_btn.clicked.connect(self.e_stop.emit); layout.addWidget(self.estop_btn)
        bl = QHBoxLayout(); 
        self.start_btn = QPushButton("▶ Start"); self.start_btn.setStyleSheet("QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #338833, stop:1 #226622); color: white; font-size: 12px; font-weight: bold; border: 1px solid #44aa44; border-radius: 4px; min-height: 32px; } QPushButton:hover { background: #44aa44; } QPushButton:pressed { background: #112211; }"); self.start_btn.clicked.connect(self.cycle_start.emit); bl.addWidget(self.start_btn)
        self.hold_btn = QPushButton("⏸ Hold"); self.hold_btn.setStyleSheet("QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #887733, stop:1 #665522); color: white; font-size: 12px; font-weight: bold; border: 1px solid #aa9944; border-radius: 4px; min-height: 32px; } QPushButton:hover { background: #aa9944; } QPushButton:pressed { background: #332211; }"); self.hold_btn.clicked.connect(self.feed_hold.emit); bl.addWidget(self.hold_btn)
        layout.addLayout(bl)
        self.reset_btn = QPushButton("🔧 Reset Alarm"); self.reset_btn.setStyleSheet("QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444, stop:1 #333); color: #ddd; border: 1px solid #666; border-radius: 4px; padding: 4px; } QPushButton:hover { background: #555; } QPushButton:pressed { background: #111; }"); self.reset_btn.clicked.connect(self.reset_alarm.emit); layout.addWidget(self.reset_btn)

class OverridePanel(QGroupBox):
    override_changed = Signal()
    def __init__(self, machine_state, parent=None): super().__init__("🚀 Overrides", parent); self.machine = machine_state; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self)
        for attr, label, val in [('override_feed', 'Feed %', 100), ('override_rapid', 'Rapid %', 100), ('override_spindle', 'Spindle %', 100)]:
            lay = QHBoxLayout(); lay.addWidget(QLabel(label)); slider = QSlider(Qt.Horizontal); slider.setRange(0, 200); slider.setValue(val); lbl = QLabel(f"{val}%"); lbl.setMinimumWidth(35)
            slider.valueChanged.connect(lambda v, l=lbl, a=attr: (l.setText(f"{v}%"), setattr(self.machine, a, v), self.override_changed.emit()))
            lay.addWidget(slider); lay.addWidget(lbl); layout.addLayout(lay)

# ============================================================
# Main Window
# ============================================================
class CNCMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.machine = MachineState(); self.simulation_running = False; self.simulation_line = 0
        self.sim_timer = QTimer(); self.sim_timer.timeout.connect(self.simulation_step)
        self.setWindowTitle("CNC & Lathe Controller Pro v3.0 - Industrial UI"); self.setMinimumSize(1400, 900); self.resize(1500, 950)
        self.init_ui(); self.apply_theme()
        self.update_timer = QTimer(); self.update_timer.timeout.connect(self.update_displays); self.update_timer.start(80)

    def init_ui(self):
        self.create_menus(); self.create_toolbar()
        central = QWidget(); self.setCentralWidget(central); ml = QHBoxLayout(central); ml.setSpacing(6); ml.setContentsMargins(6,6,6,6)
        lp = QWidget(); ll = QVBoxLayout(lp); ll.setSpacing(6); ll.setContentsMargins(0,0,0,0)
        self.dro = DROWidget(self.machine); ll.addWidget(self.dro)
        self.machine_ctrl = MachineControlPanel(); self.machine_ctrl.cycle_start.connect(self.cycle_start); self.machine_ctrl.feed_hold.connect(self.feed_hold); self.machine_ctrl.stop.connect(self.stop_machine); self.machine_ctrl.e_stop.connect(self.emergency_stop); self.machine_ctrl.home_all.connect(self.home_all); self.machine_ctrl.reset_alarm.connect(self.reset_alarm); ll.addWidget(self.machine_ctrl)
        self.jog_ctrl = JogControl(); self.jog_ctrl.jog_clicked.connect(self.do_jog); ll.addWidget(self.jog_ctrl)
        self.spindle_feed = SpindleFeedControl(self.machine); self.spindle_feed.spindle_toggled.connect(self.toggle_spindle); self.spindle_feed.speed_changed.connect(self.change_speed); self.spindle_feed.feed_changed.connect(self.change_feed); self.spindle_feed.coolant_toggled.connect(self.toggle_coolant); ll.addWidget(self.spindle_feed)
        self.override_panel = OverridePanel(self.machine); ll.addWidget(self.override_panel)
        lp.setFixedWidth(280); ml.addWidget(lp)
        cs = QSplitter(Qt.Vertical); self.toolpath = ToolpathView(); cs.addWidget(self.toolpath); self.gcode_editor = GCodeEditor(); cs.addWidget(self.gcode_editor); cs.setSizes([500, 350]); ml.addWidget(cs, stretch=1)
        rp = QWidget(); rl = QVBoxLayout(rp); rl.setSpacing(6); rl.setContentsMargins(0,0,0,0)
        self.right_tabs = QTabWidget(); self.tool_manager = ToolManager(self.machine); self.tool_manager.tool_selected.connect(self.on_tool_selected); self.right_tabs.addTab(self.tool_manager, "🔧 Tools"); self.work_offsets = WorkOffsetsWidget(self.machine); self.right_tabs.addTab(self.work_offsets, "📏 Offsets"); self.macro_panel = MacroPanel(); self.macro_panel.macro_triggered.connect(self.process_macro); self.right_tabs.addTab(self.macro_panel, "⚡ Macros"); self.mdi = MDIWidget(); self.mdi.command_sent.connect(self.process_mdi); self.right_tabs.addTab(self.mdi, "⌨ MDI"); rl.addWidget(self.right_tabs)
        lg = QGroupBox("📋 Log"); lgl = QVBoxLayout(lg); self.log_text = QTextEdit(); self.log_text.setReadOnly(True); self.log_text.setMaximumHeight(120); self.log_text.setStyleSheet("QTextEdit { background-color: #050505; color: #888; font-family: Consolas; font-size: 10px; border: 1px solid #222; }"); lgl.addWidget(self.log_text); rl.addWidget(lg); rp.setFixedWidth(380); ml.addWidget(rp)
        self.statusBar().showMessage("Ready")

    def create_menus(self):
        menubar = self.menuBar(); vm = menubar.addMenu("&View"); vm.addAction("XY Mill View", lambda: self.set_view_mode('XY')); vm.addAction("XZ Lathe View", lambda: self.set_view_mode('XZ')); vm.addAction("ISO 2.5D View", lambda: self.set_view_mode('ISO')); vm.addSeparator(); vm.addAction("Refresh Toolpath", self.refresh_toolpath, QKeySequence("Ctrl+R")); vm.addAction("Auto-Fit", self.toolpath_auto_fit)
    def create_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False); tb.addAction("▶ Start", self.cycle_start); tb.addAction("⏸ Hold", self.feed_hold); tb.addAction("⏹ Stop", self.stop_machine); tb.addSeparator(); tb.addAction("XY Mill", lambda: self.set_view_mode('XY')); tb.addAction("XZ Lathe", lambda: self.set_view_mode('XZ')); tb.addAction("ISO 3D", lambda: self.set_view_mode('ISO')); tb.addSeparator(); tb.addAction("🔄 Refresh", self.refresh_toolpath); self.addToolBar(tb)
    def set_view_mode(self, mode): self.toolpath.view_mode = mode; self.refresh_toolpath()
    
    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { color: #ddd; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 10px; padding-top: 14px; font-weight: bold; color: #aaa; background-color: #181818; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #ccc; }
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3a3a, stop:1 #2a2a2a); color: #ddd; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background: #444; border: 1px solid #888; } QPushButton:pressed { background: #111; }
            QComboBox { background-color: #2a2a2a; color: #ddd; border: 1px solid #444; border-radius: 4px; padding: 3px; }
            QComboBox QAbstractItemView { background-color: #1a1a1a; color: #ddd; selection-background-color: #444; }
            QSpinBox, QDoubleSpinBox, QLineEdit { background-color: #0a0a0a; color: #ddd; border: 1px solid #333; border-radius: 4px; padding: 3px; }
            QSlider::groove:horizontal { height: 6px; background: #222; border-radius: 3px; }
            QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #666, stop:1 #444); border-radius: 8px; border: 1px solid #888; }
            QTabWidget::pane { border: 1px solid #333; background: #181818; border-radius: 4px; }
            QTabBar::tab { background: #222; color: #888; padding: 6px 12px; border: 1px solid #333; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #333; color: #fff; border-bottom-color: #333; }
            QTableWidget { background-color: #0a0a0a; color: #ddd; gridline-color: #222; border: 1px solid #333; alternate-background-color: #111; }
            QHeaderView::section { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333, stop:1 #222); color: #aaa; border: 1px solid #444; padding: 4px; }
            QSplitter::handle { background-color: #333; height: 4px; }
            QScrollBar:vertical { background: #111; width: 10px; border: none; } QScrollBar::handle:vertical { background: #444; border-radius: 5px; min-height: 20px; } QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QToolBar { background: #181818; border-bottom: 1px solid #333; spacing: 4px; padding: 2px; }
            QToolButton { background: #222; color: #ddd; padding: 5px 10px; border: 1px solid #444; border-radius: 4px; } QToolButton:hover { background: #333; }
        """)

    def update_displays(self):
        self.dro.update_display(); self.spindle_feed.update_gauges(); state = self.machine.machine_state
        if state == 'ALARM': self.statusBar().setStyleSheet("background-color: #330000; color: #ff4444; padding: 2px; font-weight: bold;")
        elif state == 'RUNNING': self.statusBar().setStyleSheet("background-color: #003300; color: #44ff44; padding: 2px; font-weight: bold;")
        else: self.statusBar().setStyleSheet("background-color: #121212; color: #888; padding: 2px;")
        self.statusBar().showMessage(f"  State: {state}  |  Tool: T{self.machine.current_tool:02d}  |  Offset: {self.machine.active_offset}  |  View: {self.toolpath.view_mode}")

    def refresh_toolpath(self): self.toolpath.parse_gcode(self.gcode_editor.editor.toPlainText()); self.log("Toolpath refreshed")
    def toolpath_auto_fit(self): self.toolpath.auto_scale(); self.toolpath.update()
    def cycle_start(self):
        if self.machine.machine_state in ('ALARM', 'RUNNING'): return
        self.log("Cycle Start"); self.machine.machine_state = 'RUNNING'; self.refresh_toolpath(); self.toolpath.sim_trail = [self.machine.position.copy()]; self.simulation_running = True; self.simulation_line = 0; self.sim_timer.start(150)
    def simulation_step(self):
        lines = self.gcode_editor.get_gcode_lines()
        if self.simulation_line >= len(lines): self.sim_timer.stop(); self.simulation_running = False; self.machine.machine_state = 'IDLE'; self.toolpath.highlight_line = -1; self.toolpath.update(); self.log("Program finished"); return
        self.toolpath.highlight_line = self.simulation_line; self.execute_line(lines[self.simulation_line].strip()); self.toolpath.sim_trail.append(self.machine.position.copy()); self.toolpath.current_pos = self.machine.position.copy(); self.toolpath.update(); self.simulation_line += 1

    def execute_line(self, line):
        clean = re.sub(r';.*$|\(.*?\)', '', line).strip()
        if not clean or clean.startswith('%'): return
        if clean.startswith('N'): clean = re.sub(r'^N\d+\s*', '', clean)
        if not clean: return
        for g in re.findall(r'G(\d+)', clean, re.IGNORECASE):
            code = int(g)
            if code == 90: self.machine.mode = 'ABS'
            elif code == 91: self.machine.mode = 'INC'
            elif code == 21: self.machine.units = 'MM'
            elif code == 20: self.machine.units = 'IN'
            elif code == 28: self.machine.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}; self.log("Homed")
            elif code == 4: self.log("Dwell executed")
        for m in re.findall(r'M(\d+)', clean, re.IGNORECASE):
            code = int(m)
            if code in (3, 4): self.machine.spindle_on = True; self.machine.spindle_dir = 'CW' if code == 3 else 'CCW'; self.spindle_feed.spindle_btn.setChecked(True); self.spindle_feed.spindle_btn.setText("ON")
            elif code == 5: self.machine.spindle_on = False; self.spindle_feed.spindle_btn.setChecked(False); self.spindle_feed.spindle_btn.setText("OFF")
            elif code == 6: t_m = re.search(r'T(\d+)', clean, re.IGNORECASE); self.machine.current_tool = int(t_m.group(1)) if t_m else self.machine.current_tool; self.log(f"Tool T{self.machine.current_tool:02d}")
            elif code == 8: self.machine.coolant = True; self.spindle_feed.coolant_btn.setChecked(True); self.spindle_feed.coolant_btn.setText("Coolant ON")
            elif code == 9: self.machine.coolant = False; self.spindle_feed.coolant_btn.setChecked(False); self.spindle_feed.coolant_btn.setText("Coolant OFF")
            elif code == 30: self.sim_timer.stop(); self.simulation_running = False; self.machine.machine_state = 'IDLE'; self.machine.spindle_on = False; self.log("Program End (M30)")
        x_m, y_m, z_m = re.search(r'X\s*(-?\d+\.?\d*)', clean, re.IGNORECASE), re.search(r'Y\s*(-?\d+\.?\d*)', clean, re.IGNORECASE), re.search(r'Z\s*(-?\d+\.?\d*)', clean, re.IGNORECASE)
        f_m, s_m = re.search(r'F\s*(-?\d+\.?\d*)', clean, re.IGNORECASE), re.search(r'S\s*(-?\d+\.?\d*)', clean, re.IGNORECASE)
        if x_m or y_m or z_m:
            if self.machine.mode == 'ABS':
                if x_m: self.machine.position['X'] = float(x_m.group(1)) / (2 if self.machine.lathe_diameter_mode else 1)
                if y_m: self.machine.position['Y'] = float(y_m.group(1))
                if z_m: self.machine.position['Z'] = float(z_m.group(1))
            else:
                if x_m: self.machine.position['X'] += float(x_m.group(1)) / (2 if self.machine.lathe_diameter_mode else 1)
                if y_m: self.machine.position['Y'] += float(y_m.group(1))
                if z_m: self.machine.position['Z'] += float(z_m.group(1))
            for ax in ['X', 'Y', 'Z']:
                if abs(self.machine.position[ax]) > self.machine.soft_limits.get(ax, 9999): self.emergency_stop(); return
        if f_m: self.machine.feed_rate = float(f_m.group(1)); self.spindle_feed.feed_spin.setValue(self.machine.feed_rate)
        if s_m: self.machine.spindle_speed = int(float(s_m.group(1))); self.spindle_feed.speed_spin.setValue(self.machine.spindle_speed)

    def feed_hold(self): 
        if self.simulation_running: self.sim_timer.stop(); self.machine.machine_state = 'PAUSED'; self.log("Feed Hold")
    def stop_machine(self): self.sim_timer.stop(); self.simulation_running = False; self.machine.machine_state = 'IDLE'; self.toolpath.highlight_line = -1; self.toolpath.update(); self.log("Stopped")
    def emergency_stop(self): self.sim_timer.stop(); self.simulation_running = False; self.machine.machine_state = 'ALARM'; self.machine.spindle_on = False; self.machine.coolant = False; self.spindle_feed.spindle_btn.setChecked(False); self.spindle_feed.spindle_btn.setText("OFF"); self.spindle_feed.coolant_btn.setChecked(False); self.spindle_feed.coolant_btn.setText("Coolant OFF"); self.toolpath.highlight_line = -1; self.toolpath.update(); self.log("⚠ E-STOP ACTIVATED")
    def reset_alarm(self): 
        if self.machine.machine_state == 'ALARM': self.machine.machine_state = 'IDLE'; self.log("Alarm Reset")
    def home_all(self): self.machine.position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}; self.machine.machine_state = 'IDLE'; self.toolpath.current_pos = self.machine.position.copy(); self.toolpath.update(); self.log("Homed")
    def do_jog(self, axis, distance): 
        if self.machine.machine_state in ('RUNNING', 'ALARM'): return
        if distance == -99999: self.machine.position[axis] = 0.0; self.log(f"Home {axis}")
        else: self.machine.jog(axis, distance)
        self.toolpath.current_pos = self.machine.position.copy(); self.toolpath.update()
    def toggle_spindle(self, on): self.machine.spindle_on = on
    def change_speed(self, rpm): self.machine.spindle_speed = rpm
    def change_feed(self, feed): self.machine.feed_rate = feed
    def toggle_coolant(self, on): self.machine.coolant = on
    def on_tool_selected(self, tool_id): self.machine.current_tool = tool_id; self.log(f"Tool T{tool_id:02d}")
    def process_mdi(self, cmd): self.log(f"MDI: {cmd}"); self.execute_line(cmd); self.toolpath.current_pos = self.machine.position.copy(); self.toolpath.update(); self.mdi.append_output(f"<span style='color:#44aaff'>OK: {cmd}</span>")
    def process_macro(self, gcode): self.log("Macro Executed"); [self.execute_line(line) for line in gcode.split('\n')]; self.toolpath.current_pos = self.machine.position.copy(); self.toolpath.update()
    def log(self, message):
        import datetime; self.log_text.append(f"<span style='color:#444'>[{datetime.datetime.now().strftime('%H:%M:%S')}]</span> {message}")
    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_F5: self.cycle_start()
        elif k == Qt.Key_F6: self.feed_hold()
        elif k == Qt.Key_Escape: self.emergency_stop() if event.modifiers() & Qt.ShiftModifier else self.stop_machine()
        else: super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv); window = CNCMainWindow(); window.show(); sys.exit(app.exec())
if __name__ == "__main__": main()