# -*- coding: utf-8 -*-
"""
PySide6 GUI for qPCR ΔΔCt workflow.

This window lets users configure and run `compute_ddct` from core.compute.
- Choose input Excel and (optional) output path
- Set regexes, column mapping, sheet name
- Configure outlier filtering (enable/disable, method, threshold, min reps, record outliers)
- Configure other flags (exclude_ref_in_sample_sheet, case-insensitive regex)

Run: python /Users/mojackhu/Github/qPCR/gui/main_window.py
"""
#%%
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QFileDialog, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QTextEdit, QLabel, QGroupBox, QMessageBox, QSizePolicy
)

# --- Import compute_ddct -----------------------------------------------------
# Ensure project root (…/qPCR) is on sys.path so `core.compute` can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from core.compute import compute_ddct
except Exception as e:  # Keep UI usable; show error on run
    compute_ddct = None
    _import_error = e
else:
    _import_error = None


def _parse_sheet_name(text: str):
    text = (text or "").strip()
    if text == "" or text == "0":
        return 0
    # int-like (handles e.g. 2, 10)
    if text.isdigit():
        try:
            return int(text)
        except Exception:
            pass
    return text  # e.g., "Sheet1"


class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        cw = QWidget(self)
        self.setCentralWidget(cw)

        # --- i18n ------------------------------------------------------------
        self._lang = "en"  # default language: zh or en
        self._t = {
            "zh": {
                "title": "qPCR 计算器 (by Mojack, v0.1)",
                "group_paths": "文件路径",
                "choose_excel": "选择Excel…",
                "input_excel": "输入Excel:",
                "save_to": "保存到…",
                "output_path": "输出路径(可选):",
                "group_regex": "正则设置",
                "ctrl_regex": "控制组正则:",
                "ref_regex": "参考基因正则:",
                "group_cols": "列映射 & 工作表",
                "ctrl_col": "控制组所在列:",
                "ref_col": "基因所在列:",
                "sample_col": "样本标签所在列:",
                "cq_col": "Cq列:",
                "well_col": "孔位列:",
                "sheet": "工作表 (索引或名称):",
                "group_flags": "其他选项",
                "exclude_ref": "样本均值中排除参考基因",
                "case_ins": "正则忽略大小写",
                "group_outlier": "异常值过滤 (按每个 样本×基因 的Cq分布)",
                "runlog": "运行与日志",
                "enable_outliers": "启用异常值过滤",
                "outlier_method": "方法:",
                "outlier_thresh": "阈值:",
                "outlier_min_reps": "最小重复数:",
                "record_outliers": "导出被过滤的孔至 'outliers' 工作表",
                "run": "运行计算",
                "open_output": "打开输出文件",
                "log": "日志:",
                "log_placeholder": "这里显示运行日志与错误信息…",
                "running": "\n▶️ 正在运行 compute_ddct …",
                "done": "✅ 完成。结果已写入：{path}",
                "import_err_title": "导入错误",
                "import_err_body": "无法导入 compute_ddct: {err}",
                "path_err_title": "路径错误",
                "path_err_body": "请先选择有效的输入Excel文件。",
                "run_fail_title": "运行失败",
                "out_missing_title": "提示",
                "out_missing_body": "输出文件不存在。请先运行计算。",
                "file_filter": "Excel (*.xlsx *.xls);;所有文件 (*.*)",
                "save_filter": "Excel (*.xlsx)",
                "lang": "语言:",
                "lang_cn": "中文",
                "lang_en": "English",
            },
            "en": {
                "title": "qPCR Calculator (by Mojack, v0.1)",
                "group_paths": "Paths",
                "choose_excel": "Choose Excel…",
                "input_excel": "Input Excel:",
                "save_to": "Save as…",
                "output_path": "Output path (optional):",
                "group_regex": "Regex",
                "ctrl_regex": "Control-group regex:",
                "ref_regex": "Reference-gene regex:",
                "group_cols": "Column mapping & Sheet",
                "ctrl_col": "Column for control group:",
                "ref_col": "Column for gene:",
                "sample_col": "Column for sample label:",
                "cq_col": "Cq column:",
                "well_col": "Well column:",
                "sheet": "Sheet (index or name):",
                "group_flags": "Other options",
                "exclude_ref": "Exclude reference gene in sample means",
                "case_ins": "Ignore case in regex",
                "group_outlier": "Outlier filtering (per Sample×Gene Cq)",
                "runlog": "Run & Log",
                "enable_outliers": "Enable outlier filtering",
                "outlier_method": "Method:",
                "outlier_thresh": "Threshold:",
                "outlier_min_reps": "Min repeats:",
                "record_outliers": "Export removed wells to 'outliers' sheet",
                "run": "Run",
                "open_output": "Open output",
                "log": "Log:",
                "log_placeholder": "Logs and errors will appear here…",
                "running": "\n▶️ Running compute_ddct …",
                "done": "✅ Done. Wrote results to: {path}",
                "import_err_title": "Import Error",
                "import_err_body": "Failed to import compute_ddct: {err}",
                "path_err_title": "Path Error",
                "path_err_body": "Please select a valid Excel file first.",
                "run_fail_title": "Run Failed",
                "out_missing_title": "Info",
                "out_missing_body": "Output file not found. Please run first.",
                "file_filter": "Excel (*.xlsx *.xls);;All files (*.*)",
                "save_filter": "Excel (*.xlsx)",
                "lang": "Language:",
                "lang_cn": "中文",
                "lang_en": "English",
            },
        }

        self.setWindowTitle(self._t[self._lang]["title"])
        self.resize(980, 720)

        # --- Widgets ---------------------------------------------------------
        # Paths
        self.le_input = QLineEdit()
        self.btn_browse_in = QPushButton("")
        self.btn_browse_in.clicked.connect(self._pick_input)

        self.le_output = QLineEdit()
        self.btn_browse_out = QPushButton("")
        self.btn_browse_out.clicked.connect(self._pick_output)

        # Regex
        self.le_ctrl_regex = QLineEdit("CTR")
        self.le_ref_regex = QLineEdit("B-ACTIN")

        # Column mapping
        # Conventional: control_search_col=Sample, ref_search_col=Target, sample_name_col=Sample
        self.le_control_search_col = QLineEdit("Target")
        self.le_ref_search_col = QLineEdit("Sample")
        self.le_sample_name_col = QLineEdit("Target")
        self.le_cq_col = QLineEdit("Cq")
        self.le_well_col = QLineEdit("Well")
        self.le_sheet = QLineEdit("0")  # sheet index or name

        # Make text inputs longer and expandable
        from PySide6.QtWidgets import QSizePolicy
        _expanding = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for _w in [
            self.le_input, self.le_output, self.le_ctrl_regex, self.le_ref_regex,
            self.le_control_search_col, self.le_ref_search_col, self.le_sample_name_col,
            self.le_cq_col, self.le_well_col, self.le_sheet
        ]:
            _w.setMinimumWidth(420)
            _w.setSizePolicy(_expanding)

        # Flags
        self.cb_exclude_ref = QCheckBox("")
        self.cb_exclude_ref.setChecked(False)  # compute_ddct default
        self.cb_case_ins = QCheckBox("")
        self.cb_case_ins.setChecked(True)

        # Outlier filtering options
        self.cb_enable_outliers = QCheckBox("")
        self.cb_enable_outliers.setChecked(True)

        self.cmb_outlier_method = QComboBox()
        self.cmb_outlier_method.addItems(["mad", "iqr", "zscore"])  # default 'mad'
        self.cmb_outlier_method.setCurrentText("mad")

        self.sb_outlier_thresh = QDoubleSpinBox()
        self.sb_outlier_thresh.setRange(0.1, 10.0)
        self.sb_outlier_thresh.setSingleStep(0.1)
        self.sb_outlier_thresh.setDecimals(2)
        self.sb_outlier_thresh.setValue(3.0)

        self.sb_outlier_min_reps = QSpinBox()
        self.sb_outlier_min_reps.setRange(2, 99)
        self.sb_outlier_min_reps.setValue(3)

        self.cb_record_outliers = QCheckBox("")
        self.cb_record_outliers.setChecked(True)

        # Enable/disable outlier widgets based on master switch
        self.cb_enable_outliers.toggled.connect(self._toggle_outlier_widgets)

        # Language selector
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems([self._t["zh"]["lang_cn"], self._t["en"]["lang_en"]])
        self.cmb_lang.setCurrentIndex(1 if self._lang == "en" else 0)
        self.cmb_lang.currentIndexChanged.connect(self._on_lang_changed)
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(self._t[self._lang]["lang"]))
        lang_row.addWidget(self.cmb_lang)
        lang_row.addStretch(1)

        # Store group boxes for i18n
        self.paths_box = QGroupBox("")
        self.regex_box = QGroupBox("")
        self.cols_box = QGroupBox("")
        self.flags_box = QGroupBox("")
        self.outlier_box = QGroupBox("")

        # Paths form with QLabel captions for i18n
        self.form_paths = QFormLayout()
        self.lbl_input_excel = QLabel("")
        self.lbl_output_path = QLabel("")
        row_in = QHBoxLayout(); row_in.addWidget(self.le_input, 1); row_in.addWidget(self.btn_browse_in)
        row_in_w = QWidget(); row_in_w.setLayout(row_in); self.row_in_widget = row_in_w
        row_out = QHBoxLayout(); row_out.addWidget(self.le_output, 1); row_out.addWidget(self.btn_browse_out)
        row_out_w = QWidget(); row_out_w.setLayout(row_out)
        self.form_paths.addRow(self.lbl_input_excel, row_in_w)
        self.form_paths.addRow(self.lbl_output_path, row_out_w)
        self.paths_box.setLayout(self.form_paths)

        self.form_regex = QFormLayout()
        self.lbl_ctrl_regex = QLabel("")
        self.lbl_ref_regex = QLabel("")
        self.form_regex.addRow(self.lbl_ctrl_regex, self.le_ctrl_regex)
        self.form_regex.addRow(self.lbl_ref_regex, self.le_ref_regex)
        self.regex_box.setLayout(self.form_regex)

        self.form_cols = QFormLayout()
        self.lbl_ctrl_col = QLabel("")
        self.lbl_ref_col = QLabel("")
        self.lbl_sample_col = QLabel("")
        self.lbl_cq_col = QLabel("")
        self.lbl_well_col = QLabel("")
        self.lbl_sheet = QLabel("")
        self.form_cols.addRow(self.lbl_ctrl_col, self.le_control_search_col)
        self.form_cols.addRow(self.lbl_ref_col, self.le_ref_search_col)
        self.form_cols.addRow(self.lbl_sample_col, self.le_sample_name_col)
        self.form_cols.addRow(self.lbl_cq_col, self.le_cq_col)
        self.form_cols.addRow(self.lbl_well_col, self.le_well_col)
        self.form_cols.addRow(self.lbl_sheet, self.le_sheet)
        self.cols_box.setLayout(self.form_cols)

        self.flags_box_layout = QVBoxLayout()
        self.flags_box_layout.addWidget(self.cb_exclude_ref)
        self.flags_box_layout.addWidget(self.cb_case_ins)
        self.flags_box.setLayout(self.flags_box_layout)

        self.form_out = QFormLayout()
        self.form_out.addRow(self.cb_enable_outliers)
        self.lbl_outlier_method = QLabel("")
        self.lbl_outlier_thresh = QLabel("")
        self.lbl_outlier_min_reps = QLabel("")
        self.form_out.addRow(self.lbl_outlier_method, self.cmb_outlier_method)
        self.form_out.addRow(self.lbl_outlier_thresh, self.sb_outlier_thresh)
        self.form_out.addRow(self.lbl_outlier_min_reps, self.sb_outlier_min_reps)
        self.form_out.addRow(self.cb_record_outliers)
        self.outlier_box.setLayout(self.form_out)

        # --- Run & Log group box --------------------------------------------
        self.run_box = QGroupBox("")
        run_box_layout = QVBoxLayout()
        # buttons row created below will be added here after it's built
        # placeholder for label is self.lbl_log; the QTextEdit is self.log
        # We'll add them after btn_row is defined.

        # --- Tighten paddings/spacing for forms and groups -------------------
        for _f in (self.form_paths, self.form_regex, self.form_cols, self.form_out):
            _f.setContentsMargins(8, 8, 8, 8)
            _f.setHorizontalSpacing(8)
            _f.setVerticalSpacing(6)
        # Reduce minimum width of all QLineEdit fields
        for _w in [
            self.le_input, self.le_output,
            self.le_ctrl_regex, self.le_ref_regex,
            self.le_control_search_col, self.le_ref_search_col,
            self.le_sample_name_col, self.le_cq_col, self.le_well_col, self.le_sheet,
        ]:
            _w.setMinimumWidth(210)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("")
        self.btn_run.clicked.connect(self._run_compute)
        self.btn_open_output = QPushButton("")
        self.btn_open_output.clicked.connect(self._open_output)
        self.btn_open_output.setEnabled(False)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_open_output)
        btn_row.addStretch(1)

        # Enlarge Run & Open output buttons, bold text
        from PySide6.QtGui import QFont
        big_font = self.btn_run.font()
        big_font.setPointSize(big_font.pointSize() + 4)
        big_font.setBold(True)
        self.btn_run.setFont(big_font)
        self.btn_open_output.setFont(big_font)
        self.btn_run.setMinimumHeight(40)
        self.btn_open_output.setMinimumHeight(40)

        # Compact button style
        btn_style = "QPushButton { padding: 4px 8px; }"
        self.btn_run.setStyleSheet(btn_style)
        self.btn_open_output.setStyleSheet(btn_style)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.lbl_log = QLabel("")

        # Populate run_box with buttons and log
        run_box_layout.addLayout(btn_row)
        self.lbl_log.setContentsMargins(0, 6, 0, 0)
        run_box_layout.addWidget(self.lbl_log)
        run_box_layout.addWidget(self.log, 1)
        self.run_box.setLayout(run_box_layout)

        # Tighten group box layouts
        for _box in (self.paths_box, self.regex_box, self.cols_box, self.flags_box, self.outlier_box, self.run_box):
            layout = _box.layout()
            if layout is not None:
                layout.setContentsMargins(8, 8, 8, 8)
                if hasattr(layout, "setSpacing"):
                    layout.setSpacing(8)

        # --- Root grid layout (3x2) -----------------------------------------
        grid = QGridLayout()
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        # top language row spans two columns
        lang_container = QWidget()
        lang_container.setLayout(lang_row)
        grid.addWidget(lang_container, 0, 0, 1, 2)

        # row 1 (index starts at 1 here for sections), col 0/1
        grid.addWidget(self.paths_box,   1, 0)
        grid.addWidget(self.cols_box,    1, 1)
        # row 2
        grid.addWidget(self.regex_box,   2, 0)
        grid.addWidget(self.flags_box,   2, 1)
        # row 3
        grid.addWidget(self.outlier_box, 3, 0)
        grid.addWidget(self.run_box,     3, 1)

        cw.setLayout(grid)

        # initialize enabled state
        self._toggle_outlier_widgets(self.cb_enable_outliers.isChecked())
        self._apply_i18n()
        self._apply_group_title_fonts()
        self._apply_inner_font_style()

    # --- Slots ---------------------------------------------------------------
    def _pick_input(self) -> None:
        t = self._t[self._lang]
        path, _ = QFileDialog.getOpenFileName(self, t["choose_excel"], "", t["file_filter"])
        if not path:
            return
        self.le_input.setText(path)
        # suggest default output next to input
        base = os.path.dirname(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        default_out = os.path.join(base or ".", f"{stem}_ddct.xlsx")
        if not self.le_output.text().strip():
            self.le_output.setText(default_out)

    def _pick_output(self) -> None:
        t = self._t[self._lang]
        # Let user pick a save path (xlsx)
        path, _ = QFileDialog.getSaveFileName(self, t["save_to"], self.le_output.text().strip() or "", t["save_filter"])
        if path:
            # ensure .xlsx extension
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.le_output.setText(path)

    def _toggle_outlier_widgets(self, enabled: bool) -> None:
        for w in (self.cmb_outlier_method, self.sb_outlier_thresh, self.sb_outlier_min_reps, self.cb_record_outliers):
            w.setEnabled(enabled)

    def _open_output(self) -> None:
        t = self._t[self._lang]
        path = self.le_output.text().strip()
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(self, t["out_missing_title"], t["out_missing_body"])

    def _run_compute(self) -> None:
        t = self._t[self._lang]
        if compute_ddct is None:
            QMessageBox.critical(self, t["import_err_title"], t["import_err_body"].format(err=_import_error))
            return

        excel_path = self.le_input.text().strip()
        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, t["path_err_title"], t["path_err_body"])
            return

        # Gather params
        control_group_regex = self.le_ctrl_regex.text().strip()
        ref_gene_regex = self.le_ref_regex.text().strip()

        control_search_col = self.le_control_search_col.text().strip() or "Sample"
        ref_search_col = self.le_ref_search_col.text().strip() or "Target"
        sample_name_col = self.le_sample_name_col.text().strip() or "Sample"
        cq_col = self.le_cq_col.text().strip() or "Cq"
        well_col = self.le_well_col.text().strip() or "Well"
        sheet_name = _parse_sheet_name(self.le_sheet.text())

        exclude_ref = self.cb_exclude_ref.isChecked()
        case_ins = self.cb_case_ins.isChecked()

        enable_outlier_filter = self.cb_enable_outliers.isChecked()
        outlier_method = self.cmb_outlier_method.currentText()
        outlier_threshold = float(self.sb_outlier_thresh.value())
        outlier_min_reps = int(self.sb_outlier_min_reps.value())
        record_outliers = self.cb_record_outliers.isChecked()

        output_path = self.le_output.text().strip() or None

        self.log.append(t["running"])
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            well_df, sample_df, out_path = compute_ddct(
                excel_path=excel_path,
                control_group_regex=control_group_regex,
                ref_gene_regex=ref_gene_regex,
                output_path=output_path,
                control_search_col=control_search_col,
                ref_search_col=ref_search_col,
                sample_name_col=sample_name_col,
                cq_col=cq_col,
                well_col=well_col,
                sheet_name=sheet_name,
                exclude_ref_in_sample_sheet=exclude_ref,
                assume_case_insensitive_regex=case_ins,
                outlier_method=outlier_method,
                outlier_threshold=outlier_threshold,
                outlier_min_reps=outlier_min_reps,
                record_outliers=record_outliers,
                enable_outlier_filter=enable_outlier_filter,
            )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            tb = traceback.format_exc()
            self.log.append(f"❌ 运行失败：{e}\n{tb}")
            QMessageBox.critical(self, t["run_fail_title"], f"{e}")
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self.le_output.setText(out_path)
        self.btn_open_output.setEnabled(True)
        self.log.append(t["done"].format(path=out_path))

    def _apply_i18n(self) -> None:
        t = self._t[self._lang]
        self.setWindowTitle(t["title"])
        # group titles
        self.paths_box.setTitle(t["group_paths"]) 
        self.regex_box.setTitle(t["group_regex"]) 
        self.cols_box.setTitle(t["group_cols"]) 
        self.flags_box.setTitle(t["group_flags"]) 
        self.outlier_box.setTitle(t["group_outlier"]) 
        self.run_box.setTitle(t["runlog"])
        # buttons/checkboxes
        self.btn_browse_in.setText(t["choose_excel"]) 
        self.btn_browse_out.setText(t["save_to"]) 
        self.cb_exclude_ref.setText(t["exclude_ref"]) 
        self.cb_case_ins.setText(t["case_ins"]) 
        self.cb_enable_outliers.setText(t["enable_outliers"]) 
        self.cb_record_outliers.setText(t["record_outliers"]) 
        self.btn_run.setText(t["run"]) 
        self.btn_open_output.setText(t["open_output"]) 
        self.lbl_log.setText(t["log"]) 
        # log placeholder
        self.log.setPlaceholderText(t["log_placeholder"])
        # form labels
        self.lbl_input_excel.setText(t["input_excel"]) 
        self.lbl_output_path.setText(t["output_path"]) 
        self.lbl_ctrl_regex.setText(t["ctrl_regex"]) 
        self.lbl_ref_regex.setText(t["ref_regex"]) 
        self.lbl_ctrl_col.setText(t["ctrl_col"]) 
        self.lbl_ref_col.setText(t["ref_col"]) 
        self.lbl_sample_col.setText(t["sample_col"]) 
        self.lbl_cq_col.setText(t["cq_col"]) 
        self.lbl_well_col.setText(t["well_col"]) 
        self.lbl_sheet.setText(t["sheet"]) 
        self.lbl_outlier_method.setText(t["outlier_method"]) 
        self.lbl_outlier_thresh.setText(t["outlier_thresh"]) 
        self.lbl_outlier_min_reps.setText(t["outlier_min_reps"]) 
        # language row label
        # Update language label next to combobox
        lang_label = self.cmb_lang.parent().layout().itemAt(0).widget()
        if isinstance(lang_label, QLabel):
            lang_label.setText(t["lang"]) 
        self._apply_group_title_fonts()


    def _apply_group_title_fonts(self) -> None:
        from PySide6.QtGui import QFont
        boxes = [self.paths_box, self.regex_box, self.cols_box, self.flags_box, self.outlier_box, self.run_box]
        for box in boxes:
            f = box.font()
            f.setPointSize(max(10, f.pointSize() + 2))
            f.setBold(True)
            box.setFont(f)

    def _apply_inner_font_style(self) -> None:
        """Make inner widgets' fonts smaller and not bold, while keeping
        group titles and the Run/Open buttons styled separately."""
        from PySide6.QtGui import QFont
        shrink_targets = [self.paths_box, self.regex_box, self.cols_box, self.flags_box, self.outlier_box]
        for box in shrink_targets:
            for w in box.findChildren(QWidget):
                # Do not touch group boxes (titles) or the big action buttons
                if isinstance(w, QGroupBox):
                    continue
                if w is self.btn_run or w is self.btn_open_output:
                    continue
                f = w.font()
                # Reduce size slightly but keep it readable
                new_pt = max(9, f.pointSize() - 1 if f.pointSize() > 0 else 9)
                f.setPointSize(new_pt)
                f.setBold(False)
                w.setFont(f)
        # Also shrink fonts inside Run & Log (except the big buttons)
        # 3a) Log label
        f_lbl = self.lbl_log.font()
        new_pt_lbl = max(9, f_lbl.pointSize() - 1 if f_lbl.pointSize() > 0 else 9)
        f_lbl.setPointSize(new_pt_lbl)
        f_lbl.setBold(False)
        self.lbl_log.setFont(f_lbl)
        # 3b) Log QTextEdit font
        f_log = self.log.font()
        new_pt_log = max(9, f_log.pointSize() - 1 if f_log.pointSize() > 0 else 9)
        f_log.setPointSize(new_pt_log)
        f_log.setBold(False)
        self.log.setFont(f_log)

    def _on_lang_changed(self, idx: int) -> None:
        self._lang = "zh" if idx == 0 else "en"
        self._apply_i18n()


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())