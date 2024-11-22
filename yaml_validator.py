import sys
import yaml
from typing import Optional
from pathlib import Path
import os
import webbrowser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                            QFileDialog, QMessageBox, QMenuBar, QMenu, QStatusBar,
                            QFrame, QScrollBar, QPlainTextEdit)
from PyQt6.QtCore import Qt, QMimeData, QRect, QSize
from PyQt6.QtGui import (QDragEnterEvent, QDropEvent, QIcon, QAction, 
                        QPainter, QColor, QTextFormat, QTextCursor)

class YAMLValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_content(self, content: str) -> bool:
        self.errors = []
        self.warnings = []
        
        try:
            data = yaml.safe_load(content)
            
            if data is None:
                self.warnings.append("警告: 空のYAMLドキュメントです")
                return True
            
            self._validate_structure(data)
            self._check_indentation(content)
            
            return len(self.errors) == 0
            
        except yaml.MarkedYAMLError as e:
            self.errors.append(f"YAML構文エラー (行 {e.problem_mark.line + 1}): {e.problem}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"YAML解析エラー: {str(e)}")
            return False

    def _validate_structure(self, data, path=""):
        if isinstance(data, dict):
            for key, value in data.items():
                if not isinstance(key, str):
                    self.warnings.append(f"警告: キー '{key}' は文字列ではありません ({path})")
                
                if value is None:
                    self.warnings.append(f"警告: キー '{key}' の値が空です ({path})")
                
                new_path = f"{path}.{key}" if path else key
                self._validate_structure(value, new_path)
                
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                self._validate_structure(item, new_path)

    def _check_indentation(self, content: str):
        lines = content.split('\n')
        spaces_pattern = None
        
        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith('#'):
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    if spaces_pattern is None:
                        spaces_pattern = indent
                    elif indent % spaces_pattern != 0:
                        self.warnings.append(f"警告: 行 {i} のインデントが一貫していません")

    def get_report(self) -> str:
        report = []
        if self.errors:
            report.append("エラー:")
            for error in self.errors:
                report.append(f"- {error}")
        
        if self.warnings:
            if report:
                report.append("")
            report.append("警告:")
            for warning in self.warnings:
                report.append(f"- {warning}")
                
        if not report:
            report.append("✅ 検証に成功しました！問題は見つかりませんでした。")
            
        return "\n".join(report)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.line_number_area = LineNumberArea(self)
        
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        
        self.update_line_number_area_width(0)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                              self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#808080"))
                painter.drawText(0, int(top), self.line_number_area.width() - 2,
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#f8f8f8")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls() or mime_data.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            file_path = mime_data.urls()[0].toLocalFile()
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    self.setPlainText(file.read())
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ファイル読み込みエラー: {str(e)}")
        elif mime_data.hasText():
            self.setPlainText(mime_data.text())

class DropTextEditWithLineNumbers(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.line_number_area = LineNumberArea(self)
        
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        
        self.update_line_number_area_width(0)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

    def line_number_area_width(self):
        digits = len(str(max(1, self.document().blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                              self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#808080"))
                painter.drawText(0, int(top), self.line_number_area.width() - 2,
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#f8f8f8")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls() or mime_data.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            file_path = mime_data.urls()[0].toLocalFile()
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    self.setText(file.read())
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ファイル読み込みエラー: {str(e)}")
        elif mime_data.hasText():
            self.setText(mime_data.text())

# YAMLValidatorGUIクラスの更新
class YAMLValidatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.validator = YAMLValidator()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('YAML Validator')
        self.setMinimumSize(800, 600)

        icon_path = self._get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.create_menu_bar()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        input_label = QLabel('YAMLテキストを入力するか、ファイルをドラッグ&ドロップしてください:')
        layout.addWidget(input_label)
        
        # CodeEditorを使用
        self.input_text = CodeEditor()
        self.input_text.setPlaceholderText("ここにYAMLを入力...")
        layout.addWidget(self.input_text)

        button_layout = QHBoxLayout()
        
        self.load_button = QPushButton('ファイルを開く')
        self.load_button.clicked.connect(self.load_file)
        button_layout.addWidget(self.load_button)

        self.validate_button = QPushButton('検証')
        self.validate_button.clicked.connect(self.validate_yaml)
        self.validate_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.validate_button)

        self.clear_button = QPushButton('クリア')
        self.clear_button.clicked.connect(self.clear_all)
        button_layout.addWidget(self.clear_button)
        
        layout.addLayout(button_layout)

        result_label = QLabel('検証結果:')
        layout.addWidget(result_label)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(200)
        layout.addWidget(self.result_text)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('準備完了')


    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu('ファイル')
        
        open_action = QAction('開く', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.load_file)
        file_menu.addAction(open_action)
        
        exit_action = QAction('終了', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ヘルプメニュー
        help_menu = menubar.addMenu('ヘルプ')
        
        about_action = QAction('このアプリについて', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _get_resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def load_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "YAMLファイルを開く",
            "",
            "YAML files (*.yaml *.yml);;All files (*.*)"
        )
        
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    self.input_text.setText(file.read())
                self.statusBar.showMessage(f'ファイルを読み込みました: {file_name}')
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ファイル読み込みエラー: {str(e)}")
                self.statusBar.showMessage('ファイル読み込みに失敗しました')

    def validate_yaml(self):
        content = self.input_text.toPlainText()
        if not content.strip():
            self.result_text.setText("エラー: YAMLテキストを入力してください。")
            self.statusBar.showMessage('検証失敗: 入力が空です')
            return

        self.validator.validate_content(content)
        report = self.validator.get_report()
        
        if "エラー:" in report:
            self.result_text.setStyleSheet("background-color: #ffebee;")
            self.statusBar.showMessage('検証完了: エラーが見つかりました')
        elif "警告:" in report:
            self.result_text.setStyleSheet("background-color: #fff3e0;")
            self.statusBar.showMessage('検証完了: 警告があります')
        else:
            self.result_text.setStyleSheet("background-color: #e8f5e9;")
            self.statusBar.showMessage('検証成功: 問題は見つかりませんでした')
            
        self.result_text.setText(report)

    def clear_all(self):
        self.input_text.clear()
        self.result_text.clear()
        self.result_text.setStyleSheet("")
        self.statusBar.showMessage('入力をクリアしました')

    def show_about(self):
        QMessageBox.about(self,
            "YAML Validator について",
            "YAML Validator v1.0\n\n"
            "YAMLファイルの構文チェックと検証を行うツールです。\n"
            "テキスト入力またはファイルのドラッグ&ドロップに対応しています。"
        )

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = YAMLValidatorGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()