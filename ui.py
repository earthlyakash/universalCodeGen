import sys
import json
import os
import subprocess
import tempfile
import uuid
import shutil
import ast
import re
import random
import string
import traceback
import onnxruntime  

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsProxyWidget,
    QToolBar, QAction, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QPushButton, QFileDialog, QMessageBox,
    QStyle, QColorDialog, QCheckBox, QProgressDialog, QComboBox, QTextEdit, QListWidget, 
    QListWidgetItem, QAbstractItemView, QTreeWidget, QTreeWidgetItem, QSpinBox, 
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QGraphicsEllipseItem, QShortcut,
    QCompleter, QScrollArea, QTextBrowser, QTabBar, QInputDialog, QSlider
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QMouseEvent, QPixmap, QKeySequence, 
    QPainterPath, QImage, QTransform, QTextCursor, QSyntaxHighlighter, QTextCharFormat, QFont
)
from PyQt5.QtCore import Qt, QRectF, QPoint, QPointF, QThread, pyqtSignal, QMimeData, QRegExp, QStringListModel
def ensure_functions_file():
    target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "functions.py")
    if not os.path.exists(target_file):
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# Automatically generated functions.py\n# Add your top-level custom logic here.\nimport os\n\ndef apply_red_channel_mask(image_path, output_path):\n    pass\n\ndef resize_and_normalize(image_path, width, height):\n    pass\n\ndef copy_file(source, destination):\n    import shutil\n    shutil.copy(source, destination)\n")

def ensure_ai_functions_file():
    target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_functions.py")
    if not os.path.exists(target_file):
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("""import os\nimport urllib.request\n\ndef check_and_download_model(model_name, url):\n    pass\n""")


# ==========================================
# 🚀 DYNAMIC AST PARSERS (UPGRADED WITH DEFAULTS)
# ==========================================
def _extract_defaults(node):
    defs = {}
    args = [a.arg for a in node.args.args]
    num_defs = len(node.args.defaults)
    if num_defs > 0:
        for i, d in enumerate(node.args.defaults):
            arg_name = args[-(num_defs - i)]
            if hasattr(d, 'value'): defs[arg_name] = str(d.value)
            elif hasattr(d, 'id'): defs[arg_name] = str(d.id)
            elif isinstance(d, ast.UnaryOp) and isinstance(d.op, ast.USub) and hasattr(d.operand, 'value'):
                defs[arg_name] = f"-{d.operand.value}"
            else: defs[arg_name] = ""
    return defs

def parse_custom_functions():
    funcs = []
    target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "functions.py")
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f: tree = ast.parse(f.read())
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    args = [a.arg for a in node.args.args]
                    docstring = ast.get_docstring(node) or "No description provided."
                    funcs.append({"name": node.name, "args": args, "defaults": _extract_defaults(node), "doc": docstring})
        except Exception as e: print("Error parsing functions.py:", e)
    return funcs

def parse_ai_functions():
    funcs = []
    target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_functions.py")
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f: tree = ast.parse(f.read())
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and node.name != "check_and_download_model":
                    args = [a.arg for a in node.args.args]
                    docstring = ast.get_docstring(node) or "No AI description provided."
                    funcs.append({"name": node.name, "args": args, "defaults": _extract_defaults(node), "doc": docstring})
        except Exception as e: print("Error parsing ai_functions.py:", e)
    return funcs

def parse_custom_code_functions():
    funcs = []
    target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customCode.py")
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f: tree = ast.parse(f.read())
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    args = [a.arg for a in node.args.args]
                    docstring = ast.get_docstring(node) or "No description provided."
                    funcs.append({"name": node.name, "args": args, "defaults": _extract_defaults(node), "doc": docstring})
        except Exception as e: print("Error parsing customCode.py:", e)
    return funcs


def ensure_custom_code_file():
    target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customCode.py")
    if not os.path.exists(target_file):
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("# Automatically generated customCode.py\n# User saved custom functions will appear here.\nimport os\nimport cv2\nimport numpy as np\nimport shutil\n\n")

def parse_imported_libraries():
    libs = set()
    for filename in ["functions.py", "ai_functions.py", "customCode.py"]:
        target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                # ast.walk se file ke andar kisi bhi function me chupe imports bhi read ho jayenge
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            libs.add(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            libs.add(node.module.split('.')[0])
            except Exception as e:
                print(f"Error parsing imports in {filename}:", e)
    return sorted(list(libs))

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569cd6"))
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda", "None",
            "nonlocal", "not", "or", "pass", "raise", "return", "True",
            "try", "while", "with", "yield"
        ]
        for word in keywords:
            pattern = QRegExp(r"\b" + word + r"\b")
            self.highlightingRules.append((pattern, keywordFormat))

        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#4ec9b0"))
        builtins = ["print", "len", "range", "int", "float", "str", "list", "dict", "set", "tuple", "Exception", "NameError", "locals", "globals"]
        for word in builtins:
            pattern = QRegExp(r"\b" + word + r"\b")
            self.highlightingRules.append((pattern, builtinFormat))

        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#dcdcaa"))
        self.highlightingRules.append((QRegExp(r"\b[A-Za-z0-9_]+(?=\()"), functionFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#ce9178"))
        self.highlightingRules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), stringFormat))
        self.highlightingRules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), stringFormat))

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#b5cea8"))
        self.highlightingRules.append((QRegExp(r"\b[0-9]+(\.[0-9]+)?\b"), numberFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6a9955"))
        commentFormat.setFontItalic(True)
        self.highlightingRules.append((QRegExp(r"#[^\n]*"), commentFormat))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        self.setCurrentBlockState(0)

class CodeTextEdit(QTextEdit):
    def __init__(self, keywords, parent=None):
        super().__init__(parent)  # ⚠️ YEH LINE SABSE ZAROORI HAI! Iske bina app crash hogi.
        
        self.base_keywords = keywords
        self.highlighter = PythonHighlighter(self.document())
        
        # --- Completer Setup ---
        self.completer = QCompleter(self.base_keywords, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insertCompletion)
        self.setAcceptRichText(False)
        
        # --- VS Code Dark Theme for Suggestion Box ---
        self.completer.popup().setStyleSheet("""
            QListView {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #454545;
                selection-background-color: #062f4a;
                font-family: Consolas, monospace;
                font-size: 13px;
            }
        """)
        
        # --- Dynamic Word Learner ---
        self.textChanged.connect(self.update_dynamic_completions)

    def update_dynamic_completions(self):
        # Jaise hi kuch naya type hoga, editor usey list mein add kar lega
        current_text = self.toPlainText()
        found_words = set(re.findall(r'\b[a-zA-Z_]\w*\b', current_text))
        all_keywords = sorted(list(set(self.base_keywords) | found_words))
        
        from PyQt5.QtCore import QStringListModel # Ensure it's available
        model = QStringListModel(all_keywords, self.completer)
        self.completer.setModel(model)

    # ... (Iske neeche aapke baaki ke functions jaise insertFromMimeData, insertCompletion, textUnderCursor aur keyPressEvent waise hi rahenge) ...

    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())

    def insertCompletion(self, completion):
        tc = self.textCursor()
        text = tc.block().text()
        pos = tc.positionInBlock()
        start = pos
        # Backward search to find complete word including underscore '_'
        while start > 0 and (text[start-1].isalnum() or text[start-1] == '_'):
            start -= 1
        
        # Word ko select karke naye suggestion se replace karega
        tc.setPosition(tc.position() - (pos - start), QTextCursor.KeepAnchor)
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        text = tc.block().text()
        pos = tc.positionInBlock()
        start = pos
        # Underscore aur alphabets ko ek hi word maanega
        while start > 0 and (text[start-1].isalnum() or text[start-1] == '_'):
            start -= 1
        return text[start:pos]

    def keyPressEvent(self, e):
        if self.completer.popup().isVisible():
            if e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                e.ignore()
                return

        if e.key() == Qt.Key_Tab and not self.completer.popup().isVisible():
            self.insertPlainText("    ")
            return

        if e.key() in (Qt.Key_Enter, Qt.Key_Return):
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indentation = ""
            for char in current_line:
                if char in (' ', '\t'): indentation += char
                else: break
            text_up_to_cursor = current_line[:cursor.positionInBlock()].strip()
            if text_up_to_cursor.endswith(':'): indentation += "    "
            cursor.insertText("\n" + indentation)
            self.ensureCursorVisible()
            return

        pairs = {Qt.Key_ParenLeft: ")", Qt.Key_BracketLeft: "]", Qt.Key_BraceLeft: "}"}
        if e.key() in pairs:
            super().keyPressEvent(e)
            self.insertPlainText(pairs[e.key()])
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return
            
        if e.text() in ['"', "'"]:
            super().keyPressEvent(e)
            self.insertPlainText(e.text())
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return

        isShortcut = (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_Space
        if not isShortcut: super().keyPressEvent(e)
        ctrlOrShift = e.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
        if not isShortcut and (ctrlOrShift and e.text() == ''): return
        
        # ⚠️ Yahan se underscore '_' hata diya gaya hai taaki break na ho
        eow = "~!@#$%^&*()+{}|:\"<>?,./;'[]\\-=" 
        hasModifier = (e.modifiers() != Qt.NoModifier) and not ctrlOrShift
        completionPrefix = self.textUnderCursor()
        
        if not isShortcut and (hasModifier or e.text() == '' or len(completionPrefix) < 1 or e.text()[-1] in eow):
            self.completer.popup().hide()
            return
        
        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
        
        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)


class CompileThread(QThread):
    finished = pyqtSignal(bool, str, str)
    def __init__(self, script_path, icon_path, output_dir, target_dir):
        super().__init__()
        self.script_path, self.icon_path, self.output_dir, self.target_dir = script_path, icon_path, output_dir, target_dir

    def run(self):
        try:
            cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--hidden-import=PyQt5"]
            if self.icon_path and os.path.exists(self.icon_path): cmd.append(f"--icon={self.icon_path}")
            cmd.append(self.script_path)
            
            process = subprocess.run(cmd, cwd=self.output_dir, capture_output=True, text=True)
            
            if os.path.exists(self.script_path): os.remove(self.script_path)
            spec_file = self.script_path.replace(".py", ".spec")
            if os.path.exists(spec_file): os.remove(spec_file)
            build_dir = os.path.join(self.output_dir, "build")
            if os.path.exists(build_dir): shutil.rmtree(build_dir, ignore_errors=True)
            temp_ico = os.path.join(self.output_dir, "temp_app_icon.ico")
            if os.path.exists(temp_ico): os.remove(temp_ico)

            if process.returncode == 0:
                exe_name = os.path.basename(self.script_path).replace(".py", ".exe")
                exe_source = os.path.join(self.output_dir, "dist", exe_name)
                exe_dest = os.path.join(self.target_dir, exe_name)
                
                if os.path.exists(exe_source):
                    if os.path.exists(exe_dest): os.remove(exe_dest)
                    shutil.move(exe_source, exe_dest)
                    dist_dir = os.path.join(self.output_dir, "dist")
                    if os.path.exists(dist_dir): shutil.rmtree(dist_dir, ignore_errors=True)
                    self.finished.emit(True, "App published successfully! Executable saved in the project folder.", self.target_dir)
                else:
                    self.finished.emit(False, "Compiled successfully but couldn't locate the EXE.", "")
            else:
                self.finished.emit(False, process.stderr, "")
        except Exception as e:
            self.finished.emit(False, str(e), "")

class NewAppDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New App Workspace")
        self.resize(400, 200)
        layout = QFormLayout(self)
        self.name_input = QLineEdit(self); self.name_input.setPlaceholderText("e.g. My Custom App")
        layout.addRow("App Name:", self.name_input)
        self.author_input = QLineEdit(self); self.author_input.setPlaceholderText("e.g. Akash Kumar")
        layout.addRow("Author Name:", self.author_input)
        self.version_input = QLineEdit(self); self.version_input.setPlaceholderText("e.g. 1.0.0")
        layout.addRow("Version:", self.version_input)
        icon_layout = QHBoxLayout()
        self.icon_input = QLineEdit(self); self.icon_input.setPlaceholderText("Select 128x128 PNG/ICO...")
        self.btn_browse_icon = QPushButton("Browse"); self.btn_browse_icon.clicked.connect(self.browse_icon)
        icon_layout.addWidget(self.icon_input); icon_layout.addWidget(self.btn_browse_icon)
        layout.addRow("App Icon:", icon_layout)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def browse_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select App Icon", "", "Images (*.png *.ico)")
        if file_path: self.icon_input.setText(file_path)

    def get_data(self):
        return {
            "app_name": self.name_input.text().strip() or "Untitled App",
            "author": self.author_input.text().strip(),
            "version": self.version_input.text().strip() or "1.0.0",
            "icon_path": self.icon_input.text().strip()
        }

class HelpDialog(QDialog):
    def __init__(self, custom_funcs, ai_funcs, global_funcs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 App Builder - Dynamic Instruction Manual")
        self.resize(900, 700)
        layout = QVBoxLayout(self)
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; padding: 15px;")
        
        html_content = self.generate_html(custom_funcs, ai_funcs, global_funcs)
        self.browser.setHtml(html_content)
        layout.addWidget(self.browser)
        
        btn_close = QPushButton("Close Help")
        btn_close.setStyleSheet("background-color: #007acc; color: white; padding: 8px; font-weight: bold; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def generate_html(self, custom_funcs, ai_funcs, global_funcs):
        # 🔥 DYNAMIC EXTRACTION
        detected_libs = parse_imported_libraries()
        libs_str = ", ".join(detected_libs) if detected_libs else "None detected"
        
        ai_model_names = [f["name"] for f in ai_funcs]
        ai_models_str = ", ".join(ai_model_names) if ai_model_names else "No AI models detected"

        html = f"""
        <style>
            h1 {{ color: #007acc; border-bottom: 2px solid #007acc; padding-bottom: 5px; }}
            h2 {{ color: #ff9800; margin-top: 25px; }}
            h3 {{ color: #4caf50; margin-bottom: 5px; }}
            p {{ margin-top: 5px; line-height: 1.5; }}
            .box {{ background-color: #2d2d30; padding: 10px; border-radius: 5px; border: 1px solid #555; margin-bottom: 15px; }}
            .warning {{ background-color: #3e2723; padding: 10px; border-radius: 5px; border: 1px solid #ff9800; color: #ffb300; margin-bottom: 15px; }}
            .legal {{ background-color: #4a148c; padding: 15px; border-radius: 5px; border: 1px solid #e91e63; color: #f8bbd0; margin-bottom: 20px; line-height: 1.6; }}
            .code {{ background-color: #111; color: #ce9178; padding: 4px 8px; border-radius: 3px; font-family: Consolas; display: inline-block; margin-top: 5px; margin-bottom: 10px; word-wrap: break-word; }}
            .doc {{ color: #a5d6a7; font-style: italic; white-space: pre-wrap; background: #222; padding: 8px; border-left: 3px solid #4caf50; }}
            ul li {{ margin-bottom: 6px; }}
        </style>
        <h1>📖 Universal App Builder & Node Editor Manual</h1>
        <p>Welcome! This manual is <b>dynamically generated</b>. Whenever you add a new Python function to your backend files, it will automatically appear here.</p>
        
        <h2>⚖️ Dynamic Legal & Licensing Disclaimer</h2>
        <div class="legal">
            <p><b>Auto-Detected External Libraries & Dependencies:</b><br>
            <span class="code">{libs_str}</span></p>
            
            <p><b>Auto-Detected AI Modules / Engine Logic:</b><br>
            <span class="code">{ai_models_str}</span></p>
            
            <ul>
                <li><b>Licensing:</b> All detected third-party models, algorithms, and libraries listed above remain the intellectual property of their respective creators. They are subject to their original open-source licenses (e.g., MIT, Apache 2.0, GPL, CC BY-NC).</li>
                <li><b>Commercial Use Warning:</b> Some AI models (especially research-based ones like those detected above) may be strictly restricted to <b>non-commercial or academic use only</b>. It is your sole responsibility as the end-user to verify the original license of each specific model/library before utilizing it in any commercial product.</li>
                <li><b>No Warranty ("As-Is"):</b> This visual scripting engine is provided "as is", without any express or implied warranties. The developer assumes no liability for copyright infringement, legal disputes, data loss, or damages arising from the use of this tool.</li>
            </ul>
        </div>
        
        <h2>⌨️ Universal Shortcuts & Controls</h2>
        <div class="box">
            <ul>
                <li><b>Ctrl + F:</b> Open Universal Search Palette (Quickly find & add Nodes/UI)</li>
                <li><b>Ctrl + C / Ctrl + V:</b> Copy & Paste UI Elements, Main Functions, or Master Pipelines</li>
                <li><b>Ctrl + S:</b> Quick Save Project | <b>Ctrl + Shift + S:</b> Save As...</li>
                <li><b>Delete / Backspace:</b> Delete the currently selected Node/Element</li>
                <li><b>Middle Mouse Button (Hold & Drag):</b> Pan/Move around the canvas smoothly</li>
                <li><b>Mouse Wheel:</b> Zoom In / Zoom Out</li>
                <li><b>Shift + Click/Drag:</b> Multi-select UI elements in App Builder mode</li>
            </ul>
        </div>

        <h2>📱 Mode 1: App Builder (Compile to EXE)</h2>
        <div class="box">
            <p><b>1. UI Elements:</b> Drag Buttons, Inputs, Consoles, and <b>Plain Text Edits</b> onto the screen to build your app interface. You can dynamically resize the Plain Text Edit and its font will adjust.</p>
            <p><b>2. Main Function Panel:</b> The "Brain". Connect a <b>Trigger</b> (Blue Dot from a Button) and an <b>Input Path</b> (Yellow Dot from a Text Field).</p>
            <p><b>3. Loops (The Engine):</b> Inside the Main Function, drop loops (Directory Loop, File Loop) to process multiple files automatically.</p>
        </div>

        <h2>🎨 Mode 2: Node Image Editor (Visual Workflow)</h2>
        <div class="box">
            <p>This mode works like ComfyUI. It allows you to process images directly on the canvas without compiling an EXE.</p>
            <p><b>🧩 Standard Node Workflow:</b></p>
            <ul>
                <li><b>Step 1 (Input):</b> Add an <b>🖼️ Image Node</b> (for 1 file) or a <b>📂 List Node</b> (for folder batch). Connect its output to the Constructor's left port.</li>
                <li><b>Step 2 (Logic):</b> Right-click and add an AI Model or Standard Function. Connect its output to the Constructor's <b>Top Pink/Red Port</b>. <i>(You can chain multiple logic nodes together!)</i></li>
                <li><b>Step 3 (Engine):</b> Add a <b>⚙️ Constructor Engine</b>. This runs your images through the logic. Connect its right port to the Output node.</li>
                <li><b>Step 4 (Output):</b> Add a <b>✅ Final Output Viewer</b> to see your processed images and save them.</li>
            </ul>
            <p><b>💡 Quick Connection Template:</b><br>
            <code>Image Input [Right] ➔ [Left] Constructor [Right] ➔ [Left] Output Viewer</code><br>
            <code>AI/Custom Logic Node [Right] ➔ [Top] Constructor</code>
            </p>
        </div>

        <h2>🛠️ Universal Path Builder (Dynamic Macros)</h2>
        <p>When setting output paths in properties, use these dynamic tags to automatically route files:</p>
        <ul>
            <li><span class="code">{{current_dir}}</span> : The folder where the current file is located.</li>
            <li><span class="code">{{current_name}}</span> : The name of the file without extension (e.g. <i>image1</i>).</li>
            <li><span class="code">{{original_ext}}</span> : The original extension (e.g. <i>.jpg</i>).</li>
            <li><span class="code">{{preserve_structure}}</span> : Recreates original sub-folders inside your destination.</li>
            <li><span class="code">{{num_count}}</span> : Auto-incrementing number (1, 2, 3...).</li>
        </ul>

        <h2>🧩 Understanding Custom Code Variables</h2>
        <div class="box">
            <p>When you use the <b>Custom Code Editor Node</b>, the App Builder automatically passes background data to your script. Catch it using <code>locals().get()</code>:</p>
            <ul>
                <li><b>file_path</b> : The exact path of the current file being processed by the loop.</li>
                <li><b>current_dir</b> : The folder currently being scanned by the loop.</li>
                <li><b>return_val_0, return_val_1...</b> : These hold the <b>OUTPUTS</b> of the previous nodes. If Node 0 removes the background, its output is in <code>return_val_0</code>!</li>
            </ul>
        </div>
        
        <div class="warning">
            <b>⚠️ AI Hardware / GPU Warning (Important)</b><br>
            AI models process massive calculations and require heavy RAM/GPU (Nvidia CUDA).<br>
            <b>[Single Processing]</b>: Always test AI tools on a single file first.<br>
            <b>[Bulk Processing]</b>: Only run AI inside "Directory Loops" or "Batch Lists" if your system has a strong dedicated Graphics Card.
        </div>
        """

        html += "<h2>🤖 Available AI Models (from ai_functions.py)</h2>"
        if not ai_funcs:
            html += "<p>No AI functions found. Add them to ai_functions.py.</p>"
        for f in ai_funcs:
            args_str = ", ".join([f"<span class='code'>{a}</span>" for a in f['args']])
            html += f"<div class='box'><h3>🧠 {f['name']}</h3>"
            html += f"<p><b>Parameters:</b> {args_str}</p>"
            html += f"<div class='doc'>{f['doc']}</div></div>"

        html += "<h2>⚙️ Available Standard Functions (from functions.py)</h2>"
        if not custom_funcs:
            html += "<p>No standard functions found. Add them to functions.py.</p>"
        for f in custom_funcs:
            args_str = ", ".join([f"<span class='code'>{a}</span>" for a in f['args']])
            html += f"<div class='box'><h3>🔧 {f['name']}</h3>"
            html += f"<p><b>Parameters:</b> {args_str}</p>"
            html += f"<div class='doc'>{f['doc']}</div></div>"

        html += "<h2>🌐 Global Custom Codes (from customCode.py)</h2>"
        if not global_funcs:
            html += "<p>No custom global functions found.</p>"
        for f in global_funcs:
            args_str = ", ".join([f"<span class='code'>{a}</span>" for a in f['args']])
            html += f"<div class='box'><h3>🌐 {f['name']}</h3>"
            html += f"<p><b>Parameters:</b> {args_str}</p>"
            html += f"<div class='doc'>{f['doc']}</div></div>"

        return html

class ExampleTemplatesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_win = parent
        self.setWindowTitle("💡 Load UI Templates / Auto-Examples")
        self.resize(700, 600)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Select a pre-built example to load into the workspace.\n<b>⚠️ Warning:</b> Loading an example will replace your current unsaved work.")
        lbl.setStyleSheet("font-size: 14px; color: #ffb300; padding: 10px; background-color: #3e2723; border: 1px solid #ff9800; border-radius: 4px;")
        layout.addWidget(lbl)

        # --- NAYA SEARCH BAR ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search templates (e.g., 'resize', 'depth', 'remove')...")
        self.search_input.setStyleSheet("background-color: #333; color: white; padding: 8px; border-radius: 4px; border: 1px solid #555; font-size: 14px;")
        self.search_input.textChanged.connect(self.filter_templates)
        layout.addWidget(self.search_input)
        # -----------------------
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        self.cards = []  # Search filter apply karne ke liye cards store honge

        custom_funcs = parse_custom_functions()
        ai_funcs = parse_ai_functions()
        global_funcs = parse_custom_code_functions()
        
        # --- NAYA NODE EDITOR TEMPLATES SECTION ---
        self.add_section_header("<h3>🎴 Canvas Editor Workflows (Node Mode)</h3>")
        self.create_node_template_card("Single File + Basic Edit", "Image Node ➔ Remove Background ➔ Output Viewer", "single_basic", "#9c27b0")
        self.create_node_template_card("Single File + Chained Logic", "Image Node ➔ Resize ➔ AI Colorize ➔ Output Viewer", "single_chain", "#00bcd4")
        self.create_node_template_card("Batch Folder Processing", "Folder List Node ➔ Remove BG ➔ Convert PNG ➔ Output", "batch_chain", "#ff9800")
        
        self.add_section_header("<h3>⚙️ Standard File Operations (App Builder)</h3>")
        for f in custom_funcs:
            self.create_example_card(f, "Func")
            
        self.add_section_header("<h3>🤖 AI Processing Models</h3>")
        for f in ai_funcs:
            self.create_example_card(f, "AI")
            
        self.add_section_header("<h3>🌐 Global Custom Codes</h3>")
        for f in global_funcs:
            self.create_example_card(f, "Custom")
            
        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def add_section_header(self, text):
        lbl = QLabel(text)
        self.scroll_layout.addWidget(lbl)
        self.cards.append((lbl, ""))

    def filter_templates(self, text):
        search_term = text.lower()
        for widget, searchable_text in self.cards:
            if not searchable_text: 
                widget.setVisible(search_term == "") # Jab search karein toh category headers hide ho jayein
            else:
                widget.setVisible(search_term in searchable_text)

    def create_example_card(self, func_data, func_type):
        card = QWidget()
        card.setStyleSheet("background-color: #2d2d30; border-radius: 6px; border: 1px solid #555; margin-bottom: 5px;")
        card_layout = QVBoxLayout(card)
        
        if func_type == "AI": prefix, color = "🧠", "#e91e63"
        elif func_type == "Custom": prefix, color = "🌐", "#e65100"
        else: prefix, color = "🔧", "#4caf50"

        lbl_title = QLabel(f"{prefix} <b>{func_data['name']}</b>")
        lbl_title.setStyleSheet(f"font-size: 15px; color: {color};")
        card_layout.addWidget(lbl_title)
        
        desc = func_data['doc'].split('\n')[0] if func_data['doc'] else "No description available."
        lbl_desc = QLabel(f"<i>{desc[:80]}{'...' if len(desc)>80 else ''}</i>")
        lbl_desc.setStyleSheet("color: #aaa; margin-bottom: 5px;")
        card_layout.addWidget(lbl_desc)
        
        btn_load = QPushButton(f"Load {func_data['name']} Template")
        btn_load.setStyleSheet("background-color: #007acc; padding: 8px; font-weight: bold; font-size: 12px; border-radius: 4px;")
        btn_load.clicked.connect(lambda _, f=func_data, t=func_type: self.load_dynamic_template(f, t))
        card_layout.addWidget(btn_load)
        
        self.scroll_layout.addWidget(card)
        self.cards.append((card, f"{func_data['name'].lower()} {desc.lower()}"))

    def load_dynamic_template(self, func_data, func_type):
        if self.parent_win.is_modified:
            reply = QMessageBox.question(self, 'Unsaved Changes', "Project me unsaved changes.\n Would you like to save before load new example?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if reply == QMessageBox.Save:
                if not self.parent_win.save_project(): return
            elif reply == QMessageBox.Cancel: return
                
        func_name = func_data["name"]
        node_type = f"{func_type}: {func_name}"
        
        params = {}
        for arg in func_data["args"]:
            al = arg.lower()
            if any(x in al for x in ['output', 'output_dir', 'dest', 'dst', 'folder', 'destination']): params[arg] = "{dir_root}/Output"
            elif any(x in al for x in ['path', 'file', 'src', 'source', 'image_path']): params[arg] = "file_path"
            elif al == 'alpha': params[arg] = "1"
            elif any(x in al for x in ['width', 'height', 'size']): params[arg] = "None"
            elif 'orientation' in al or 'align' in al or 'position' in al: params[arg] = "center"
            elif 'preserve' in al: params[arg] = False
            elif 'ignore_case' in al: params[arg] = True
            elif 'mode' in al and 'blend' not in al: params[arg] = "exact"
            elif 'root_dir' in al: params[arg] = "dir_root"
            elif 'action' in al: params[arg] = "reduce"
            elif 'quality' in al: params[arg] = "base"
            elif 'model_type' in al: params[arg] = "DPT_Hybrid" if "depth" in func_name.lower() else "Human Segmentation"
            elif 'upscale' in al or 'outscale' in al: params[arg] = "2"
            elif 'noise_strength' in al: params[arg] = "25"
            elif 'mask_offset' in al or 'mask_blur' in al: params[arg] = "0"
            elif al == 'extract_upper_cloth': params[arg] = True
            elif al.startswith('extract_') or 'save_mask' in al: params[arg] = False
            elif func_name in ["rename_file_or_directory", "copy_file_or_directory", "move_file_or_directory"] and arg == "new_name": params[arg] = "{current_name}"
            elif 'ext' in al or 'extension' in al: params[arg] = ".jpg"
            else: params[arg] = ""
        params["log_console"] = True

        state = {
            "app_name": f"Auto UI: {func_name.replace('_', ' ').title()}",
            "author": "Dynamic Template Generator",
            "version": "1.0.0",
            "icon_path": "",
            "geometry": {"x": 200, "y": 100, "width": 700, "height": 550},
            "elements": [
                {"elem_id": "input_src", "type": "Input Text Field", "text": "Select Folder...", "x": 30, "y": 30, "width": 480, "height": 40, "bg_color": "#ffffff", "has_fill": True, "text_color": "#000000", "radius": 4, "border_width": 1, "border_color": "#555", "shape": "Rectangle", "font_size": 12, "alignment": "Left", "button_action": "None", "connected_button_id": "None", "dropdown_options": "", "node_x": -300, "node_y": 0},
                {"elem_id": "btn_browse", "type": "Button", "text": "Browse", "x": 520, "y": 30, "width": 140, "height": 40, "bg_color": "#007acc", "has_fill": True, "text_color": "#ffffff", "radius": 4, "border_width": 1, "border_color": "#555", "shape": "Rectangle", "font_size": 12, "alignment": "Center", "button_action": "Select Directory", "connected_button_id": "input_src", "dropdown_options": "", "node_x": -300, "node_y": 60},
                {"elem_id": "btn_trigger", "type": "Button", "text": f"Run {func_name}", "x": 30, "y": 90, "width": 630, "height": 50, "bg_color": "#e91e63" if func_type=="AI" else ("#e65100" if func_type=="Custom" else "#28a745"), "has_fill": True, "text_color": "#ffffff", "radius": 4, "border_width": 1, "border_color": "#555", "shape": "Rectangle", "font_size": 14, "alignment": "Center", "button_action": "Process_Auto", "connected_button_id": "None", "dropdown_options": "", "node_x": -300, "node_y": 120},
                {"elem_id": "console_log", "type": "Console", "text": "", "x": 30, "y": 160, "width": 630, "height": 340, "bg_color": "#000000", "has_fill": True, "text_color": "#00ff00", "radius": 4, "border_width": 1, "border_color": "#555", "shape": "Rectangle", "font_size": 10, "alignment": "Left", "button_action": "None", "connected_button_id": "None", "dropdown_options": "", "node_x": -300, "node_y": 180}
            ],
            "main_functions": [
                {
                    "func_name": "Process_Auto",
                    "input_linked_id": "input_src",
                    "console_linked_id": "console_log",
                    "x": 200, "y": -150, "width": 450, "height": 450,
                    "tree_state": [
                        {
                            "text": "File Loop: items [*.*] (<- dir_root)",
                            "node_data": {
                                "type": "File Loop",
                                "params": {"loop_name": "items", "target_dir": "dir_root", "ext": "*.*", "exclude_contains": "", "log_console": True}
                            },
                            "children": [{"text": node_type, "node_data": {"type": node_type, "params": params}}]
                        }
                    ]
                }
            ],
            "master_pipelines": [], "code_nodes": []
        }
        self.parent_win.load_project_from_dict(state)
        self.accept()
        QMessageBox.information(self.parent_win, "Loaded", f"Template for {func_name} loaded!")

    def create_node_template_card(self, title, desc, template_id, color):
        card = QWidget()
        card.setStyleSheet("background-color: #2d2d30; border-radius: 6px; border: 1px solid #555; margin-bottom: 5px;")
        card_layout = QVBoxLayout(card)
        
        lbl_title = QLabel(f"🎴 <b>{title}</b>")
        lbl_title.setStyleSheet(f"font-size: 15px; color: {color};")
        card_layout.addWidget(lbl_title)
        
        lbl_desc = QLabel(f"<i>{desc}</i>")
        lbl_desc.setStyleSheet("color: #aaa; margin-bottom: 5px;")
        card_layout.addWidget(lbl_desc)
        
        btn_load = QPushButton(f"Load Node Workflow")
        btn_load.setStyleSheet(f"background-color: {color}; color: white; padding: 8px; font-weight: bold; font-size: 12px; border-radius: 4px;")
        btn_load.clicked.connect(lambda _, t_id=template_id: self.load_specific_node_template(t_id))
        card_layout.addWidget(btn_load)
        
        self.scroll_layout.addWidget(card)
        self.cards.append((card, f"{title.lower()} {desc.lower()} node editor canvas comfyui"))

    def load_specific_node_template(self, template_id):
        if self.parent_win.is_modified:
            reply = QMessageBox.question(self, 'Unsaved Changes', "Project me unsaved changes.\n Would you like to save before load new Example?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if reply == QMessageBox.Save:
                if not self.parent_win.save_project(): return
            elif reply == QMessageBox.Cancel: return

        # Helper to generate IDs
        def make_id(prefix): return f"{prefix}_{uuid.uuid4().hex[:6]}"

        state = {
            "app_name": f"Workflow: {template_id.replace('_', ' ').title()}",
            "project_mode": "node_editor",
            "elements": [], "main_functions": [], "master_pipelines": [], "code_nodes": [],
            "canvas_nodes": [], "canvas_connections": []
        }

        if template_id == "single_basic":
            img_id = make_id("image_node")
            func_id = make_id("float_func")
            const_id = make_id("constructor")
            out_id = make_id("output")

            state["canvas_nodes"] = [
                {"type": "Image", "elem_id": img_id, "x": -450, "y": 50, "width": 320, "height": 380, "file_path": ""},
                {"type": "FloatingFunc", "elem_id": func_id, "x": -100, "y": -200, "width": 250, "height": 150,
                 "func_data": {"name": "remove_background", "args": ["image_path", "output_dir", "generate_mask"]},
                 "ntype": "Func", "params": {"generate_mask": "False"}},
                {"type": "Constructor", "elem_id": const_id, "x": -50, "y": 100, "width": 250, "height": 180},
                {"type": "Output Window", "elem_id": out_id, "x": 300, "y": 0, "width": 400, "height": 500}
            ]
            state["canvas_connections"] = [
                {"out_node": img_id, "out_role": "media_out", "in_node": const_id, "in_role": "media_in"},
                {"out_node": func_id, "out_role": "logic_out", "in_node": const_id, "in_role": "logic_in"},
                {"out_node": const_id, "out_role": "media_out", "in_node": out_id, "in_role": "media_in"}
            ]

        elif template_id == "single_chain":
            img_id = make_id("image_node")
            f1_id = make_id("float_func")
            f2_id = make_id("float_func")
            const_id = make_id("constructor")
            out_id = make_id("output")

            state["canvas_nodes"] = [
                {"type": "Image", "elem_id": img_id, "x": -550, "y": 100, "width": 320, "height": 380, "file_path": ""},
                {"type": "FloatingFunc", "elem_id": f1_id, "x": -250, "y": -250, "width": 250, "height": 180,
                 "func_data": {"name": "image_resize", "args": ["image_path", "width", "height", "output_dir"]},
                 "ntype": "Func", "params": {"width": "1024", "height": "None"}},
                {"type": "FloatingFunc", "elem_id": f2_id, "x": 50, "y": -250, "width": 250, "height": 150,
                 "func_data": {"name": "colorize_bw_image", "args": ["image_path", "output_dir"]},
                 "ntype": "AI", "params": {}},
                {"type": "Constructor", "elem_id": const_id, "x": -100, "y": 150, "width": 250, "height": 180},
                {"type": "Output Window", "elem_id": out_id, "x": 250, "y": 50, "width": 400, "height": 500}
            ]
            state["canvas_connections"] = [
                {"out_node": img_id, "out_role": "media_out", "in_node": const_id, "in_role": "media_in"},
                {"out_node": f1_id, "out_role": "logic_out", "in_node": f2_id, "in_role": "logic_in"},
                {"out_node": f2_id, "out_role": "logic_out", "in_node": const_id, "in_role": "logic_in"},
                {"out_node": const_id, "out_role": "media_out", "in_node": out_id, "in_role": "media_in"}
            ]

        elif template_id == "batch_chain":
            list_id = make_id("list_node")
            f1_id = make_id("float_func")
            f2_id = make_id("float_func")
            const_id = make_id("constructor")
            out_id = make_id("output")

            state["canvas_nodes"] = [
                {"type": "List", "elem_id": list_id, "x": -550, "y": 0, "width": 400, "height": 500, "path": "", "ext": ".*"},
                {"type": "FloatingFunc", "elem_id": f1_id, "x": -100, "y": -300, "width": 250, "height": 150,
                 "func_data": {"name": "remove_background", "args": ["image_path", "output_dir", "generate_mask"]},
                 "ntype": "Func", "params": {"generate_mask": "False"}},
                {"type": "FloatingFunc", "elem_id": f2_id, "x": 200, "y": -300, "width": 250, "height": 150,
                 "func_data": {"name": "image_converter", "args": ["image_path", "target_extension", "output_dir"]},
                 "ntype": "Func", "params": {"target_extension": ".png"}},
                {"type": "Constructor", "elem_id": const_id, "x": 50, "y": 150, "width": 250, "height": 180},
                {"type": "Output Window", "elem_id": out_id, "x": 400, "y": 0, "width": 400, "height": 500}
            ]
            state["canvas_connections"] = [
                {"out_node": list_id, "out_role": "media_out", "in_node": const_id, "in_role": "media_in"},
                {"out_node": f1_id, "out_role": "logic_out", "in_node": f2_id, "in_role": "logic_in"},
                {"out_node": f2_id, "out_role": "logic_out", "in_node": const_id, "in_role": "logic_in"},
                {"out_node": const_id, "out_role": "media_out", "in_node": out_id, "in_role": "media_in"}
            ]

        self.parent_win.load_project_from_dict(state)
        self.accept()
        QMessageBox.information(self.parent_win, "Workflow Loaded", f"Template loaded successfully! You are now in Node Image Editor Mode.")


class SearchPaletteDialog(QDialog):
    def __init__(self, items_dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #252526; color: white; border: 1px solid #007acc; border-radius: 8px;")
        self.resize(500, 350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 🔍 Search Input
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("🔍 Search elements, nodes, or AI models...")
        self.search_box.setStyleSheet("""
            background-color: #1e1e1e; padding: 12px; font-size: 15px; 
            border: 1px solid #555; border-radius: 4px; color: #d4d4d4;
        """)
        self.search_box.textChanged.connect(self.filter_list)
        layout.addWidget(self.search_box)
        
        # 📋 Suggestion List
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #1e1e1e; font-size: 14px; border: none; outline: none; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background-color: #007acc; border-radius: 4px; font-weight: bold; }
        """)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        
        self.items_dict = items_dict
        self.all_items = list(items_dict.keys())
        self.populate_list(self.all_items)
        self.selected_data = None

    def populate_list(self, items):
        self.list_widget.clear()
        for item in items:
            QListWidgetItem(item, self.list_widget)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def filter_list(self, text):
        filtered = [item for item in self.all_items if text.lower() in item.lower()]
        self.populate_list(filtered)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Down:
            row = self.list_widget.currentRow()
            if row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(row + 1)
                self.list_widget.scrollToItem(self.list_widget.item(row + 1))
            event.accept()
        elif event.key() == Qt.Key_Up:
            row = self.list_widget.currentRow()
            if row > 0:
                self.list_widget.setCurrentRow(row - 1)
                self.list_widget.scrollToItem(self.list_widget.item(row - 1))
            event.accept()
        elif event.key() in (Qt.Key_Enter, Qt.Key_Return):
            self.accept_selection()
            event.accept()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def accept_selection(self):
        curr = self.list_widget.currentItem()
        if curr:
            self.selected_data = self.items_dict[curr.text()]
            self.accept()


class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setStyleSheet("background-color: #333; color: white; border-radius: 4px;")

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        mimeData = QMimeData()
        mimeData.setText(item.text())
        
        data = item.data(Qt.UserRole)
        if data:
            mimeData.setData("application/x-logic-item", json.dumps(data).encode('utf-8'))
        
        from PyQt5.QtGui import QDrag
        drag = QDrag(self)
        drag.setMimeData(mimeData)
        drag.exec_(Qt.CopyAction)

class LogicTreeWidget(QTreeWidget):
    itemSelectedSignal = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.app_builder = None
        self.setStyleSheet("QTreeWidget { background-color: #1e1e1e; color: white; border: 1px solid #555; } QTreeWidget::item:selected { background-color: #007acc; }")
        self.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        selected = self.selectedItems()
        if selected: self.itemSelectedSignal.emit(selected[0])
        else: self.itemSelectedSignal.emit(None)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-logic-item"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-logic-item"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat("application/x-logic-item") or mime.hasText():
            text = mime.text()
            raw_data = mime.data("application/x-logic-item")
            data = json.loads(raw_data.data().decode('utf-8')) if raw_data else {"args": []}
            
            # 🚀 NAYA FIX: Custom Code Node drag karne par code editor window aur tree item dono banenge
            if text == "Custom Code Node":
                if self.app_builder:
                    c_id = f"code_{uuid.uuid4().hex[:6]}"
                    
                    # 1. Canvas par Green Code Editor Window spawn karein
                    center = self.app_builder.node_view.mapToScene(self.app_builder.node_view.viewport().rect().center())
                    cn = self.app_builder.spawn_code_node(elem_id=c_id, x=center.x() + 100, y=center.y() - 100, record=True)
                    
                    if cn:
                        # 2. Main Function Panel (Tree) ke andar item add karein
                        new_item = QTreeWidgetItem(["Func: run_custom_user_code"])
                        node_data = {
                            "type": "Func: run_custom_user_code",
                            "params": {"code_node_id": c_id, "log_console": True}
                        }
                        new_item.setData(0, Qt.UserRole, node_data)
                        new_item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_CommandLink))
                        
                        drop_target = self.itemAt(event.pos())
                        if drop_target:
                            drop_target.addChild(new_item)
                            drop_target.setExpanded(True)
                        else:
                            self.addTopLevelItem(new_item)
                            
                        self.app_builder.update_tree_title_from_params(new_item, node_data)
                        self.app_builder.record_state()
                        
                event.acceptProposedAction()
                return

            # Baaki standard items (Loops & Functions) ke liye drop logic
            new_item = QTreeWidgetItem([text])
            # --- AUTO-FILL TREE DEFAULTS ---
            params = {arg: data.get("defaults", {}).get(arg, "") for arg in data.get("args", [])}
            if "log_console" not in params: params["log_console"] = True
            
            node_data = {"type": text, "params": params}
            
            if text.startswith("Func:") or text.startswith("AI:") or text.startswith("Custom:"):
                func_nm = text.split(": ")[1]
                if func_nm == "run_custom_user_code":
                    c_id = f"code_{uuid.uuid4().hex[:6]}"
                    node_data["params"]["code_node_id"] = c_id
                    node_data["params"]["code_text"] = "None"
                    
                    if hasattr(self, 'app_builder') and self.app_builder:
                        center = self.app_builder.node_view.mapToScene(self.app_builder.node_view.viewport().rect().center())
                        self.app_builder.spawn_code_node(c_id, center.x() + 300, center.y() - 100)

            new_item.setData(0, Qt.UserRole, node_data)
            
            target = self.itemAt(event.pos())
            if target:
                target.addChild(new_item)
                target.setExpanded(True)
            else:
                self.addTopLevelItem(new_item)
                
            if self.app_builder:
                self.app_builder.update_tree_title_from_params(new_item, node_data)
                self.app_builder.record_state()
            event.acceptProposedAction()
        else:
            super().dragEvent(event)


class PortItem(QGraphicsEllipseItem):
    def __init__(self, parent_node, role, is_out):
        # ⚠️ FIX: Hit-area badha diya gaya hai taaki line easily draw ho sake (-8, -8, 16, 16)
        super().__init__(-8, -8, 16, 16, parent_node)
        self.parent_node = parent_node
        self.role = role
        self.is_out = is_out
        
        if 'trigger' in role or 'btn' in role: self.setBrush(QColor("#007acc"))
        elif 'console' in role: self.setBrush(QColor("#17a2b8"))
        elif 'code' in role: self.setBrush(QColor("#a5d6a7"))
        else: self.setBrush(QColor("#ffc107"))
            
        self.setPen(QPen(Qt.black, 1.5))
        self.setCursor(Qt.CrossCursor)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)


class CodeNodeProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0, elem_id=None, initial_code=None):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = elem_id or f"code_node_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        
        self.widget = QWidget()
        self.widget.resize(480, 380)
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #a5d6a7; border-radius: 6px;")
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"📝 Custom Code Editor Node\nID: {self.elem_id[-4:]}")
        self.title_bar.setStyleSheet("background-color: #4caf50; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        layout.addWidget(self.title_bar)
        
        chip_scroll = QScrollArea()
        chip_scroll.setWidgetResizable(True)
        chip_scroll.setFixedHeight(50)
        chip_scroll.setStyleSheet("border: none; background-color: #1e1e1e;")
        chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        chip_widget = QWidget()
        chip_layout = QHBoxLayout(chip_widget)
        chip_layout.setContentsMargins(5, 5, 5, 10)
        
        self.keywords = ['os', 'sys', 'cv2', 'shutil', 'np', 'print', 'result', 'return_val_0', 'return_val_1', 'file_path', 'current_dir', 'dir_root']
        chip_vars = ['return_val_0', 'return_val_1', 'file_path', 'current_dir', 'dir_root', 'result']
        
        for v in chip_vars:
            btn = QPushButton(f"✚ {v}")
            btn.setStyleSheet("QPushButton { background-color: #007acc; color: white; padding: 4px 8px; border-radius: 8px; font-size: 11px; font-weight: bold; border:none; } QPushButton:hover { background-color: #005f9e; }")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, text=v: self.editor.insertPlainText(text))
            chip_layout.addWidget(btn)
            
        chip_layout.addStretch()
        chip_scroll.setWidget(chip_widget)
        layout.addWidget(chip_scroll)
        
        self.editor = CodeTextEdit(self.keywords, self.widget)
        
        default_code = (
            "# -----------------------------------------------------\n"
            "# 📥 INPUT ENVIRONMENT (Injected by Loop Engine)\n"
            "# -----------------------------------------------------\n"
            "current_file = locals().get('file_path', None)\n"
            "active_folder = locals().get('current_dir', None)\n"
            "prev_output = locals().get('return_val_0', None)\n\n"
            "def custom_process(file_path, data):\n"
            "    import os\n"
            "    if not file_path:\n"
            "        return data\n"
            "    print(f'Processing: {os.path.basename(file_path)}')\n"
            "    return data\n\n"
            "result = custom_process(current_file, prev_output)\n"
        )
        
        if initial_code and initial_code != "None":
            self.editor.setPlainText(initial_code)
        else:
            self.editor.setPlainText(default_code)
            
        self.editor.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, monospace; font-size: 13px; border: 1px solid #555;")
        layout.addWidget(self.editor)
        
        self.setWidget(self.widget)
        self.widget.show()
        self.setPos(float(x), float(y))

        self._is_moving = False; self._is_resizing = False; self._margin = 10
        self.port_in = PortItem(self, 'code_in', False)
        self.port_in.setPos(0, 40)
        
    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #1e1e1e; border: 2px solid #ffc107; border-radius: 6px;" if state else "background-color: #1e1e1e; border: 2px solid #a5d6a7; border-radius: 6px;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
        if self.editor.geometry().contains(self.editor.mapFrom(self.widget, event.pos().toPoint() if hasattr(event.pos(), 'toPoint') else event.pos())):
            super().mousePressEvent(event); return
        self.app_builder.handle_code_node_selection(self)
        self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            self.widget.resize(int(max(300, self._start_size.width() + delta.x())), int(max(250, self._start_size.height() + delta.y())))
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update()
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False
        super().mouseReleaseEvent(event)

class GlobalIDEProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0, elem_id=None, initial_code=None):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = elem_id or f"global_ide_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        
        self.widget = QWidget()
        self.widget.resize(550, 450)
        self.widget.setStyleSheet("background-color: #1e1e1e; border: 2px solid #e65100; border-radius: 6px;")
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"🌐 Global Code IDE (Saves to customCode.py)")
        self.title_bar.setStyleSheet("background-color: #e65100; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        layout.addWidget(self.title_bar)
        
        chip_widget = QWidget()
        chip_layout = QHBoxLayout(chip_widget)
        chip_layout.setContentsMargins(0, 0, 0, 5)
        
        self.btn_save_global = QPushButton("💾 Smart Save to customCode.py")
        self.btn_save_global.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold; padding: 6px; border-radius: 4px; border: none;")
        self.btn_save_global.setCursor(Qt.PointingHandCursor)
        self.btn_save_global.clicked.connect(self.save_code_to_file)
        chip_layout.addWidget(self.btn_save_global)
        chip_layout.addStretch()
        layout.addWidget(chip_widget)
        
        self.keywords = ['os', 'sys', 'cv2', 'shutil', 'np', 'print']
        self.editor = CodeTextEdit(self.keywords, self.widget)
        
        default_code = "def my_custom_function(file_path):\n    import os\n    import cv2\n    # Write your logic here\n    print(f'Processing {file_path}')\n    return file_path\n"
        self.editor.setPlainText(initial_code if initial_code and initial_code != "None" else default_code)
        self.editor.setStyleSheet("background-color: #111111; color: #d4d4d4; font-family: Consolas, monospace; font-size: 14px; border: 1px solid #555;")
        layout.addWidget(self.editor)
        
        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False; self._is_resizing = False; self._margin = 10

    def save_code_to_file(self):
        code = self.editor.toPlainText()
        try:
            tree = ast.parse(code)
            new_func_names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
            if not new_func_names:
                QMessageBox.warning(self.widget, "Warning", "Koi valid function definition nahi mili code mein!\n(e.g., 'def my_func():' zaroor likhein)")
                return
            main_func_name = new_func_names[0] 

            target_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customCode.py")
            ensure_custom_code_file() 
            
            with open(target_file, "r", encoding="utf-8") as f: file_content = f.read()
            file_lines = file_content.splitlines()
            
            try: file_tree = ast.parse(file_content)
            except SyntaxError: file_tree = ast.parse("") 
                
            existing_func_node = next((n for n in file_tree.body if isinstance(n, ast.FunctionDef) and n.name == main_func_name), None)
            
            if existing_func_node:
                reply = QMessageBox.question(self.widget, 'Overwrite Function', 
                    f"Function '{main_func_name}' already exists customCode.py mein.\nWould you like to overwrite (replace) this?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return
                    
                start_line = existing_func_node.lineno - 1
                end_line = existing_func_node.end_lineno
                if existing_func_node.decorator_list:
                    start_line = existing_func_node.decorator_list[0].lineno - 1
                    
                new_lines = code.splitlines()
                file_lines = file_lines[:start_line] + new_lines + file_lines[end_line:]
                
                with open(target_file, "w", encoding="utf-8") as f: f.write("\n".join(file_lines))
            else:
                with open(target_file, "a", encoding="utf-8") as f: f.write("\n\n" + code)
            
            if hasattr(self.app_builder, 'refresh_custom_code_list'): self.app_builder.refresh_custom_code_list()
            QMessageBox.information(self.widget, "Success", f"Function '{main_func_name}' successfully saved to customCode.py!\nLeft panel updated.")
        except SyntaxError as e:
            QMessageBox.critical(self.widget, "Syntax Error", f"Invalid Python Code:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self.widget, "Error", f"An error occurred:\n{str(e)}")

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #1e1e1e; border: 2px solid #ffc107; border-radius: 6px;" if state else "background-color: #1e1e1e; border: 2px solid #e65100; border-radius: 6px;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y(); self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir: self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos(); event.accept(); return
        if self.editor.geometry().contains(self.editor.mapFrom(self.widget, event.pos().toPoint() if hasattr(event.pos(), 'toPoint') else event.pos())): super().mousePressEvent(event); return
        self.app_builder.handle_code_node_selection(self)
        self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            self.widget.resize(int(max(300, self._start_size.width() + delta.x())), int(max(250, self._start_size.height() + delta.y())))
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update()
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False
        super().mouseReleaseEvent(event)

class ElementNodeView(QGraphicsRectItem):
    def __init__(self, element_ref, app_builder):
        super().__init__(0, 0, 160, 40)
        self.element_ref = element_ref
        self.app_builder = app_builder
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setBrush(QColor("#2d2d30"))
        self.setPen(QPen(QColor("#555"), 2))
        
        icon_str = "🔳" if element_ref.elem_type == "Button" else "📝" if element_ref.elem_type == "Input Text Field" else "🔽" if element_ref.elem_type == "Dropdown" else "💻"
        t_val = element_ref.get_text()[:10].replace('\n', ' ') if element_ref.get_text() else element_ref.elem_type
        self.text_item = QGraphicsTextItem(f"{icon_str} UI: {t_val}\n({element_ref.elem_id[-4:]})", self)
        self.text_item.setDefaultTextColor(Qt.white)
        self.text_item.setPos(10, 2)
        
        self.port_out = None
        self.port_in = None
        
        if element_ref.elem_type == "Button":
            self.port_out = PortItem(self, 'btn_out', True)
            self.port_out.setPos(160, 20)
            self.port_in = PortItem(self, 'btn_in', False)
            self.port_in.setPos(0, 20)
        elif element_ref.elem_type in ["Input Text Field", "Dropdown"]:
            self.port_out = PortItem(self, 'text_out', True)
            self.port_out.setPos(160, 20)
        elif element_ref.elem_type == "Console":
            self.port_in = PortItem(self, 'console_in', False)
            self.port_in.setPos(0, 20)
            
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.scene(): self.scene().update()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            is_shift = bool(event.modifiers() & Qt.ShiftModifier)
            self.app_builder.handle_element_selection(self.element_ref, is_shift=is_shift, was_already_selected=self.element_ref.is_selected, force_single=not is_shift)

    def paint(self, painter, option, widget=None):
        if self.isSelected() or self.element_ref.is_selected:
            painter.setBrush(QColor("#3e3e42"))
            painter.setPen(QPen(QColor("#ffc107"), 2))
        else:
            painter.setBrush(QColor("#2d2d30"))
            painter.setPen(QPen(QColor("#555"), 2))
        painter.drawRect(self.rect())


class MasterPipelineProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0, func_name="Master_Pipeline_1", input_linked_id="None", console_linked_id="None", sequence=None):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"master_{uuid.uuid4().hex[:6]}"
        self.func_name = func_name
        self.input_linked_id = input_linked_id
        self.console_linked_id = console_linked_id
        self.is_selected = False
        
        self.widget = QWidget()
        self.widget.resize(250, 300)
        self.widget.setStyleSheet("background-color: #3e2723; border: 2px solid #ff9800; border-radius: 6px;")
        
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"👑 Master Pipeline:\n{self.func_name}")
        self.title_bar.setStyleSheet("background-color: #ff9800; color: black; padding: 5px; border-radius: 3px; font-weight: bold;")
        layout.addWidget(self.title_bar)
        
        ctrl_layout = QHBoxLayout()
        self.combo_funcs = QComboBox()
        self.combo_funcs.setStyleSheet("font-size: 10px; background-color: #222; color: white;")
        self.btn_add = QPushButton("+ Add")
        self.btn_add.setStyleSheet("background-color: #4caf50; font-size: 10px; color: white; padding: 3px;")
        self.btn_add.clicked.connect(self.add_func)
        ctrl_layout.addWidget(self.combo_funcs)
        ctrl_layout.addWidget(self.btn_add)
        layout.addLayout(ctrl_layout)
        
        self.sequence_list = QListWidget()
        self.sequence_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.sequence_list.setStyleSheet("background-color: #1e1e1e; color: white; font-size: 11px;")
        if sequence:
            self.sequence_list.addItems(sequence)
        
        self.sequence_list.model().rowsMoved.connect(lambda: self.app_builder.node_scene.update())
        layout.addWidget(self.sequence_list)
        
        self.btn_remove = QPushButton("🗑️ Remove Selected")
        self.btn_remove.setStyleSheet("background-color: #d32f2f; font-size: 10px; color: white;")
        self.btn_remove.clicked.connect(self.remove_func)
        layout.addWidget(self.btn_remove)
            
        self.setWidget(self.widget)
        self.setPos(float(x) if x is not None else 0.0, float(y) if y is not None else 0.0)
        self._is_moving = False; self._is_resizing = False; self._margin = 10

        self.port_trigger_in = PortItem(self, 'trigger_in', False)
        self.port_trigger_in.setPos(0, 40)
        self.port_dir_in = PortItem(self, 'dir_in', False)
        self.port_dir_in.setPos(0, 80)
        self.port_console_out = PortItem(self, 'console_out', True)
        self.port_console_out.setPos(250, 40)
        self.port_dir_out = PortItem(self, 'dir_out', True)
        self.port_dir_out.setPos(250, 80)

        self.update_combo_list()

    def update_combo_list(self):
        curr = self.combo_funcs.currentText()
        self.combo_funcs.clear()
        funcs = [mf.func_name for mf in self.app_builder.main_function_nodes]
        self.combo_funcs.addItems(funcs)
        if curr in funcs:
            self.combo_funcs.setCurrentText(curr)

    def add_func(self):
        func = self.combo_funcs.currentText()
        if func:
            self.sequence_list.addItem(func)
            self.app_builder.record_state()
            self.app_builder.node_scene.update()

    def remove_func(self):
        for item in self.sequence_list.selectedItems():
            self.sequence_list.takeItem(self.sequence_list.row(item))
        self.app_builder.record_state()
        self.app_builder.node_scene.update()

    def get_sequence(self):
        return [self.sequence_list.item(i).text() for i in range(self.sequence_list.count())]

    def update_title(self):
        self.title_bar.setText(f"👑 Master Pipeline:\n{self.func_name}")

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #3e2723; border: 2px solid #ffc107; border-radius: 6px;" if state else "background-color: #3e2723; border: 2px solid #ff9800; border-radius: 6px;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
            
        if event.pos().y() > 40:
            super().mousePressEvent(event); return
            
        self.app_builder.handle_master_func_selection(self)
        self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            self.widget.resize(int(max(200, self._start_size.width() + delta.x())), int(max(150, self._start_size.height() + delta.y())))
            self.port_console_out.setPos(self.widget.width(), 40)
            self.port_dir_out.setPos(self.widget.width(), 80)
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update()
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False
        super().mouseReleaseEvent(event)


class MainFunctionProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0, func_name="MyFunction", input_linked_id="None", console_linked_id="None", tree_state=None):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"mainfunc_{uuid.uuid4().hex[:6]}"
        self.func_name = func_name
        self.input_linked_id = input_linked_id
        self.console_linked_id = console_linked_id
        self.is_selected = False
        
        self.widget = QWidget()
        self.widget.resize(300, 400)
        self.widget.setStyleSheet("background-color: #2d2d30; border: 2px solid #555; border-radius: 6px;")
        
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"⚙️ Main Function: {self.func_name}")
        self.title_bar.setStyleSheet("background-color: #007acc; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        layout.addWidget(self.title_bar)
        
        self.tree = LogicTreeWidget(self.widget)
        self.tree.app_builder = self.app_builder
        self.tree.itemSelectedSignal.connect(self.app_builder.handle_tree_item_selection)
        layout.addWidget(self.tree)
        
        if tree_state: self.restore_tree_state(self.tree, tree_state)
            
        self.setWidget(self.widget)
        self.setPos(float(x) if x is not None else 0.0, float(y) if y is not None else 0.0)
        self._is_moving = False; self._is_resizing = False; self._margin = 10

        self.port_trigger_in = PortItem(self, 'trigger_in', False)
        self.port_trigger_in.setPos(0, 40)
        self.port_dir_in = PortItem(self, 'dir_in', False)
        self.port_dir_in.setPos(0, 80)
        self.port_console_out = PortItem(self, 'console_out', True)
        self.port_console_out.setPos(300, 40)

    def restore_tree_state(self, parent_widget, items_data):
        for data in items_data:
            item = QTreeWidgetItem([data["text"]])
            node_type = data["node_data"].get("type", "")
            if node_type == "Directory Loop": item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_DirIcon))
            elif node_type == "File Loop": item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_FileIcon))
            elif node_type == "Smart Filter Loop": item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_FileDialogDetailedView))
            elif node_type.startswith("Func:"): item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_CommandLink))
            elif node_type.startswith("AI:"): item.setIcon(0, QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation))
            
            item.setData(0, Qt.UserRole, data["node_data"])
            self.app_builder.update_tree_title_from_params(item, data["node_data"])
            
            if isinstance(parent_widget, QTreeWidget): parent_widget.addTopLevelItem(item)
            else: parent_widget.addChild(item)
            
            if "children" in data:
                self.restore_tree_state(item, data["children"])
                item.setExpanded(True)

    def extract_tree_state(self, parent_item=None):
        state = []
        count = parent_item.childCount() if parent_item else self.tree.topLevelItemCount()
        for i in range(count):
            item = parent_item.child(i) if parent_item else self.tree.topLevelItem(i)
            item_data = {
                "text": item.text(0),
                "node_data": item.data(0, Qt.UserRole),
                "children": self.extract_tree_state(item)
            }
            state.append(item_data)
        return state

    def update_title(self):
        self.title_bar.setText(f"⚙️ Main Function: {self.func_name}")

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #2d2d30; border: 2px solid #ffc107; border-radius: 6px;" if state else "background-color: #2d2d30; border: 2px solid #555; border-radius: 6px;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
            
        if self.tree.geometry().contains(self.tree.mapFrom(self.widget, event.pos().toPoint() if hasattr(event.pos(), 'toPoint') else event.pos())):
            super().mousePressEvent(event); return
            
        self.app_builder.handle_main_func_selection(self)
        self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            self.widget.resize(int(max(200, self._start_size.width() + delta.x())), int(max(150, self._start_size.height() + delta.y())))
            self.port_console_out.setPos(self.widget.width(), 40)
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update()
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False
        super().mouseReleaseEvent(event)


class MovableElement(QWidget):
    def __init__(self, parent, elem_type, select_callback, change_callback, text="Sample Text", x=20, y=20, w=140, h=40, 
                 bg_color="#007acc", has_fill=True, text_color="#ffffff", radius=4, border_width=1, border_color="#555555",
                 image_path="", shape="Rectangle", font_size=12, alignment="Center", 
                 elem_id=None, button_action="None", connected_button_id="None", dropdown_options="Option 1, Option 2"):
        super().__init__(parent)
        self.select_callback, self.change_callback = select_callback, change_callback
        self.elem_type, self.step_size = elem_type, 5
        self.elem_id = elem_id or f"{elem_type.replace(' ', '_').lower()}_{uuid.uuid4().hex[:6]}"
        self.button_action, self.connected_button_id = button_action, connected_button_id
        self.dropdown_options = dropdown_options
        
        self.bg_color, self.has_fill, self.text_color = bg_color, has_fill, text_color
        self.radius, self.border_width, self.border_color = radius, border_width, border_color
        self.font_size, self.alignment, self.is_selected = font_size, alignment, False
        self.image_path, self.shape, self.padding = image_path, shape, 10
        
        if self.shape in ["Square", "Circle"]:
            size = max(w, h); w, h = size, size
            if self.shape == "Circle": self.radius = size // 2
                
        self.setGeometry(x - self.padding, y - self.padding, w + (self.padding * 2), h + (self.padding * 2))
        self.setMouseTracking(True)
        
        if elem_type == "Button": self.inner_widget = QPushButton(text, self)
        elif elem_type in ["Label", "Image"]: self.inner_widget = QLabel(text if elem_type == "Label" else "No Image", self)
        elif elem_type == "Static Text": self.inner_widget = QLabel(text, self)
        elif elem_type == "Input Text Field":
            self.inner_widget = QLineEdit(self); self.inner_widget.setPlaceholderText(text)
        elif elem_type == "Dropdown":
            self.inner_widget = QComboBox(self)
            self.inner_widget.addItems([o.strip() for o in self.dropdown_options.split(',') if o.strip()])
        elif elem_type == "Plain Text Edit":
            self.inner_widget = QTextEdit(self)
            self.inner_widget.setPlainText(text)
        elif elem_type == "Console":
            self.inner_widget = QTextEdit(self); self.inner_widget.setReadOnly(True)
            self.inner_widget.setText("> System Ready...\n")
            if (self.bg_color == "#007acc"): 
                self.bg_color, self.text_color, self.alignment, self.font_size = "#000000", "#00FF00", "Left", 10
        
        self.inner_widget.setGeometry(self.padding, self.padding, w, h)
        self.inner_widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.apply_alignment(); self.apply_style()
        self.dragging, self.resizing, self.has_moved = False, False, False
        self.offset = QPoint()

    def update_image_rendering(self):
        if self.elem_type == "Image" and self.image_path and os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                target = QPixmap(self.inner_widget.size()); target.fill(Qt.transparent)
                painter = QPainter(target); painter.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath(); bw = self.border_width
                path.addRoundedRect(bw, bw, self.inner_widget.width() - 2*bw, self.inner_widget.height() - 2*bw, max(0, self.radius - bw), max(0, self.radius - bw))
                painter.setClipPath(path)
                scaled = pixmap.scaled(self.inner_widget.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap((self.inner_widget.width() - scaled.width()) // 2, (self.inner_widget.height() - scaled.height()) // 2, scaled)
                painter.end(); self.inner_widget.setPixmap(target)
            else: self.inner_widget.setText("Invalid Image")
        elif self.elem_type == "Image": self.inner_widget.setText("No Image")

    def apply_alignment(self):
        if self.elem_type == "Image": return
        align_flag = (Qt.AlignLeft | Qt.AlignVCenter) if self.alignment == "Left" else (Qt.AlignRight | Qt.AlignVCenter) if self.alignment == "Right" else (Qt.AlignHCenter | Qt.AlignVCenter)
        if isinstance(self.inner_widget, (QLabel, QLineEdit, QTextEdit)): self.inner_widget.setAlignment(align_flag)

    def apply_style(self):
        bg_style = self.bg_color if self.has_fill else "transparent"
        b_style = f"{self.border_width}px solid {self.border_color}"
        align_css = f"text-align: {self.alignment.lower()};" if self.elem_type == "Button" else ""
        self.inner_widget.setStyleSheet(f"background-color: {bg_style}; color: {self.text_color}; border-radius: {self.radius}px; border: {b_style}; font-size: {self.font_size}px; font-weight: bold; {align_css}")
        if self.elem_type == "Image": self.update_image_rendering()

    def set_selected(self, state):
        if self.is_selected != state: self.is_selected = state; self.update()

    def get_text(self):
        if isinstance(self.inner_widget, QLineEdit): return self.inner_widget.placeholderText()
        if isinstance(self.inner_widget, QTextEdit):
            if self.elem_type == "Plain Text Edit": return self.inner_widget.toPlainText()
            return ""
        if isinstance(self.inner_widget, QComboBox): 
            return self.dropdown_options[:15] + "..." if len(self.dropdown_options) > 15 else self.dropdown_options
        if hasattr(self.inner_widget, "text"): return self.inner_widget.text()
        return ""

    def set_text(self, val):
        if isinstance(self.inner_widget, QLineEdit): self.inner_widget.setPlaceholderText(val)
        elif hasattr(self.inner_widget, "setText") and self.elem_type not in ["Image", "Console", "Dropdown", "Plain Text Edit"]: self.inner_widget.setText(val)
        elif self.elem_type == "Plain Text Edit": self.inner_widget.setPlainText(val)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            is_shift = bool(event.modifiers() & Qt.ShiftModifier)
            inner_rect = self.inner_widget.geometry()
            self.resizing = event.pos().x() >= inner_rect.right() - 5 and event.pos().y() >= inner_rect.bottom() - 5
            self.dragging = not self.resizing; self.has_moved = False; self.offset = event.pos()
            if is_shift or not self.is_selected: self.select_callback(self, is_shift=is_shift, was_already_selected=self.is_selected, force_single=False)
            event.accept()

    def mouseMoveEvent(self, event):
        main_win = self.window()
        if self.dragging:
            self.has_moved = True
            new_pos = self.mapToParent(event.pos() - self.offset)
            snapped_x, snapped_y = round(new_pos.x() / self.step_size) * self.step_size, round(new_pos.y() / self.step_size) * self.step_size
            dx, dy = snapped_x - self.x(), snapped_y - self.y()
            if dx != 0 or dy != 0:
                for child in self.parent().findChildren(MovableElement):
                    if child.is_selected: child.move(max(0, child.x() + dx), max(0, child.y() + dy))
            if hasattr(main_win, 'node_scene'): main_win.node_scene.update()
            event.accept()
        elif self.resizing:
            new_w, new_h = max(70, event.pos().x() - self.padding), max(25, event.pos().y() - self.padding)
            if self.shape in ["Square", "Circle"]:
                size = max(new_w, new_h); new_w, new_h = size, size
            snapped_w, snapped_h = round(new_w / self.step_size) * self.step_size, round(new_h / self.step_size) * self.step_size
            if self.shape == "Circle": self.radius = snapped_w // 2
            self.resize(snapped_w + (self.padding * 2), snapped_h + (self.padding * 2))
            self.inner_widget.resize(snapped_w, snapped_h)
            
            # 🔥 DYNAMIC RESIZE FOR PLAIN TEXT EDIT IN APP BUILDER
            if self.elem_type == "Plain Text Edit":
                self.font_size = max(10, int(snapped_h * 0.2))
                
            self.apply_style()
            if hasattr(main_win, 'node_scene'): main_win.node_scene.update()
            event.accept()
        else:
            inner_rect = self.inner_widget.geometry()
            self.setCursor(Qt.SizeFDiagCursor if event.pos().x() >= inner_rect.right() - 5 and event.pos().y() >= inner_rect.bottom() - 5 else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragging and not self.has_moved and not bool(event.modifiers() & Qt.ShiftModifier) and self.is_selected:
                self.select_callback(self, is_shift=False, was_already_selected=True, force_single=True)
            if (self.dragging and self.has_moved) or self.resizing: self.change_callback()
            self.dragging, self.resizing, self.has_moved = False, False, False
            event.accept()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.is_selected:
            painter = QPainter(self); painter.setPen(QPen(QColor("#ffc107"), 2, Qt.DashLine))
            padded_rect = self.inner_widget.geometry().adjusted(-self.padding, -self.padding, self.padding, self.padding)
            painter.drawRect(padded_rect); painter.fillRect(padded_rect.right() - 4, padded_rect.bottom() - 4, 8, 8, QColor("#ffc107"))


class TargetAppBody(QWidget):
    def __init__(self, parent, deselect_callback, multi_select_box_callback):
        super().__init__(parent)
        self.deselect_callback, self.multi_select_box_callback = deselect_callback, multi_select_box_callback
        self.setStyleSheet("background-color: #1e1e1e;")
        self.setMouseTracking(True)
        self.rubber_banding, self.origin, self.current_rect = False, QPoint(), QRectF()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.childAt(event.pos()) is None:
            if not bool(event.modifiers() & Qt.ShiftModifier): self.deselect_callback()
            self.rubber_banding, self.origin, self.current_rect = True, event.pos(), QRectF(event.pos(), event.pos())
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.rubber_banding:
            self.current_rect = QRectF(self.origin, event.pos()).normalized()
            self.update(); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.rubber_banding:
            self.rubber_banding = False
            self.multi_select_box_callback(self.current_rect, bool(event.modifiers() & Qt.ShiftModifier))
            self.current_rect = QRectF(); self.update(); event.accept()
        else: super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rubber_banding:
            painter = QPainter(self); painter.setPen(QPen(QColor("#007acc"), 1, Qt.DashLine))
            painter.setBrush(QColor(0, 122, 204, 40)); painter.drawRect(self.current_rect)


class TargetAppProxy(QGraphicsProxyWidget):
    def __init__(self, app_data, close_callback, deselect_prop_callback, multi_select_box_callback):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable); self.setAcceptHoverEvents(True)
        self.app_data, self.close_callback = app_data, close_callback 
        self._is_resizing, self._is_moving, self._resize_dir, self._margin = False, False, "", 10 
        
        self.window_widget = QWidget(); self.window_widget.resize(650, 500)
        self.window_widget.setStyleSheet("QWidget#MainWindow { background-color: #2b2b2b; border: 2px solid #111111; }")
        main_layout = QVBoxLayout(self.window_widget); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        self.title_bar = QWidget(); self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet("background-color: #343a40; border-bottom: 2px solid #111111;")
        title_layout = QHBoxLayout(self.title_bar); title_layout.setContentsMargins(10, 0, 5, 0)
        
        icon_label = QLabel()
        icon_path = self.app_data.get('icon_path', "")
        if icon_path and os.path.exists(icon_path): pixmap = QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else: pixmap = QApplication.style().standardIcon(QStyle.SP_DesktopIcon).pixmap(20, 20)
        icon_label.setPixmap(pixmap); icon_label.setStyleSheet("border: none; background: transparent;")
        title_layout.addWidget(icon_label)
        
        app_name = self.app_data.get('app_name', 'Untitled App')
        version = self.app_data.get('version', '1.0.0')
        self.title_label_text = QLabel(f"{app_name} (v{version})")
        self.title_label_text.setStyleSheet("color: white; font-weight: bold; border: none; padding-left: 5px;")
        title_layout.addWidget(self.title_label_text); title_layout.addStretch()
        
        self.btn_close = QPushButton("✖"); self.btn_close.setFixedSize(25, 25)
        self.btn_close.setStyleSheet("QPushButton { color: white; background-color: transparent; border: none; font-weight: bold; } QPushButton:hover { background-color: #dc3545; }")
        self.btn_close.clicked.connect(self.trigger_close); title_layout.addWidget(self.btn_close)
        
        main_layout.addWidget(self.title_bar)
        self.app_body = TargetAppBody(self.window_widget, deselect_prop_callback, multi_select_box_callback)
        main_layout.addWidget(self.app_body, 1)
        self.setWidget(self.window_widget)

    def trigger_close(self):
        if self.close_callback: self.close_callback()

    def get_project_state(self):
        elements_state = []
        for child in self.app_body.findChildren(MovableElement):
            inner = child.inner_widget.geometry()
            elements_state.append({
                "elem_id": child.elem_id, "type": child.elem_type, "text": child.get_text(),
                "x": child.x() + child.padding, "y": child.y() + child.padding, "width": inner.width(), "height": inner.height(),
                "bg_color": child.bg_color, "has_fill": child.has_fill, "text_color": child.text_color,
                "radius": child.radius, "border_width": child.border_width, "border_color": child.border_color,
                "shape": child.shape, "image_path": child.image_path, "font_size": child.font_size, "alignment": child.alignment,
                "button_action": child.button_action, "connected_button_id": child.connected_button_id,
                "dropdown_options": child.dropdown_options
            })
        state = self.app_data.copy()
        state["geometry"] = {"x": self.pos().x(), "y": self.pos().y(), "width": self.window_widget.width(), "height": self.window_widget.height()}
        state["elements"] = elements_state
        return state

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        if self._resize_dir == "bottomright": self.setCursor(Qt.SizeFDiagCursor)
        elif self._resize_dir == "bottom": self.setCursor(Qt.SizeVerCursor)
        elif self._resize_dir == "right": self.setCursor(Qt.SizeHorCursor)
        else: self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.window_widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
        if QRectF(0, 0, self.geometry().width() - 35, 35).contains(event.pos()):
            self._is_moving = True; self._start_geom_pos = self.pos(); self._start_pos = event.scenePos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        main_win = self.window()
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            self.window_widget.resize(int(max(300, self._start_size.width() + delta.x())), int(max(200, self._start_size.height() + delta.y())))
            if hasattr(main_win, 'node_scene'): main_win.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            if hasattr(main_win, 'node_scene'): main_win.node_scene.update()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_resizing = False; self._is_moving = False
        super().mouseReleaseEvent(event)


class NodeScene(QGraphicsScene):
    def __init__(self, app_builder=None, parent=None):
        super().__init__(parent)
        self.app_builder = app_builder
        self.setSceneRect(-32000, -32000, 64000, 64000)
        self.grid_size = 20
        self.setBackgroundBrush(QColor("#1e1e1e"))
        self.temp_wire_start = None
        self.temp_wire_pos = None

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        top_y, bottom_y = int(rect.top()), int(rect.bottom())
        left_x, right_x = int(rect.left()), int(rect.right())

        lines_light, lines_dark = [], []
        for x in range(left, right_x, self.grid_size):
            if x % (self.grid_size * 5) == 0: lines_dark.append((x, top_y, x, bottom_y))
            else: lines_light.append((x, top_y, x, bottom_y))
        for y in range(top, bottom_y, self.grid_size):
            if y % (self.grid_size * 5) == 0: lines_dark.append((left_x, y, right_x, y))
            else: lines_light.append((left_x, y, right_x, y))

        painter.setPen(QPen(QColor("#2d2d2d"), 1, Qt.SolidLine))
        for line in lines_light: painter.drawLine(*line)
        painter.setPen(QPen(QColor("#151515"), 2, Qt.SolidLine))
        for line in lines_dark: painter.drawLine(*line)

    def drawForeground(self, painter, rect):
        if not self.app_builder:
            return

        painter.setRenderHint(QPainter.Antialiasing)
        
        def draw_wire(p1, p2, color, style=Qt.SolidLine):
            painter.setBrush(Qt.NoBrush) 
            pen = QPen(color, 3, style, Qt.RoundCap)
            painter.setPen(pen)
            path = QPainterPath(p1)
            dx = max(abs(p2.x() - p1.x()) * 0.5, 20)
            path.cubicTo(p1.x() + dx, p1.y(), p2.x() - dx, p2.y(), p2.x(), p2.y())
            painter.drawPath(path)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(p1, 4, 4)
            painter.drawEllipse(p2, 4, 4)
            painter.setBrush(Qt.NoBrush)

        if self.temp_wire_start and self.temp_wire_pos:
            color = self.temp_wire_start.brush().color()
            p1 = self.temp_wire_start.scenePos()
            draw_wire(p1, self.temp_wire_pos, color)

        # ⚠️ FIX: DRAW COMFY-UI GENERIC WIRES (Ise current_project ki permission se azaad kar diya hai)
        if hasattr(self.app_builder, 'canvas_connections'):
            for p1, p2 in self.app_builder.canvas_connections:
                if p1.scene() and p2.scene():
                    wire_color = p1.brush().color()
                    draw_wire(p1.scenePos(), p2.scenePos(), wire_color)

        # App Builder specific wires tabhi draw hongi jab koi TargetAppProxy active hoga
        if not self.app_builder.current_project:
            return

        def find_code_links(nodes):
            links = []
            for n in nodes:
                c_id = n.get("node_data", {}).get("params", {}).get("code_node_id")
                if c_id: links.append(c_id)
                if n.get("children"): links.extend(find_code_links(n["children"]))
            return links
            
        for mf in self.app_builder.main_function_nodes:
            state = mf.extract_tree_state()
            c_ids = find_code_links(state)
            for c_id in c_ids:
                for cn in self.app_builder.code_nodes:
                    if cn.elem_id == c_id:
                        p1 = mf.scenePos() + QPointF(mf.widget.width(), mf.widget.height()/2)
                        p2 = cn.port_in.scenePos()
                        draw_wire(p1, p2, QColor("#a5d6a7"), Qt.DashLine)

        all_logic_nodes = self.app_builder.main_function_nodes + self.app_builder.master_pipeline_nodes

        for mf in all_logic_nodes:
            for en in self.app_builder.element_nodes:
                if en.element_ref.elem_type == "Button" and en.element_ref.button_action == mf.func_name:
                    if hasattr(en, 'port_out') and en.port_out:
                        draw_wire(en.port_out.scenePos(), mf.port_trigger_in.scenePos(), QColor("#007acc"))

            if mf.input_linked_id != "None":
                found_input = False
                for en in self.app_builder.element_nodes:
                    if en.element_ref.elem_id == mf.input_linked_id:
                        if hasattr(en, 'port_out') and en.port_out:
                            draw_wire(en.port_out.scenePos(), mf.port_dir_in.scenePos(), QColor("#ffc107"))
                        found_input = True
                        break
                if not found_input and hasattr(mf, 'tree'): 
                    for mp in self.app_builder.master_pipeline_nodes:
                        if mp.elem_id == mf.input_linked_id:
                            if hasattr(mp, 'port_dir_out') and mp.port_dir_out:
                                draw_wire(mp.port_dir_out.scenePos(), mf.port_dir_in.scenePos(), QColor("#ffc107"))
                            break

            if mf.console_linked_id != "None":
                for en in self.app_builder.element_nodes:
                    if en.element_ref.elem_id == mf.console_linked_id:
                        if hasattr(en, 'port_in') and en.port_in:
                            draw_wire(mf.port_console_out.scenePos(), en.port_in.scenePos(), QColor("#17a2b8"))
                        break
            
            if hasattr(mf, 'get_sequence'): 
                for target_name in mf.get_sequence():
                    for target_mf in self.app_builder.main_function_nodes:
                        if target_mf.func_name == target_name:
                            p1 = mf.scenePos() + QPointF(mf.widget.width() - 10, mf.widget.height() * 0.8)
                            p2 = target_mf.port_trigger_in.scenePos()
                            draw_wire(p1, p2, QColor("#e83e8c"), Qt.DashLine)
            else: 
                state = mf.extract_tree_state()
                def find_ui_links(nodes):
                    linked_ids = set()
                    for n in nodes:
                        params = n.get("node_data", {}).get("params", {})
                        for val in params.values():
                            val_str = str(val)
                            if "self." in val_str and "{" not in val_str:
                                matches = re.findall(r'self\.([a-zA-Z0-9_]+)', val_str)
                                for m in matches: linked_ids.add(m)
                            elif "self." in val_str and "{" in val_str and "}" in val_str:
                                matches = re.findall(r'self\.([a-zA-Z0-9_]+)\.(?:text|toPlainText|currentText)', val_str)
                                for m in matches: linked_ids.add(m)
                        if n.get("children"):
                            linked_ids.update(find_ui_links(n["children"]))
                    return linked_ids

                for e_id in find_ui_links(state):
                    for el in self.app_builder.element_nodes:
                        if el.element_ref.elem_id == e_id:
                            p2 = mf.pos() + QPointF(mf.widget.width()/2, 0)
                            draw_wire(el.port_out.scenePos(), p2, QColor("#ffc107"), Qt.DotLine)

        for en in self.app_builder.element_nodes:
            if en.element_ref.elem_type in ["Input Text Field"] and en.element_ref.connected_button_id != "None":
                for tgt_en in self.app_builder.element_nodes:
                    if tgt_en.element_ref.elem_id == en.element_ref.connected_button_id:
                        if hasattr(en, 'port_out') and en.port_out and hasattr(tgt_en, 'port_in') and tgt_en.port_in:
                            draw_wire(en.port_out.scenePos(), tgt_en.port_in.scenePos(), QColor("#28a745"), Qt.DashLine)
                        break

    def mousePressEvent(self, event):
        items = self.items(event.scenePos())
        for item in items:
            if isinstance(item, PortItem):
                self.temp_wire_start = item
                self.temp_wire_pos = event.scenePos()
                if not item.is_out:
                    self.app_builder.break_connection_at_input(item)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.temp_wire_start:
            self.temp_wire_pos = event.scenePos()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.temp_wire_start:
            items = self.items(event.scenePos())
            target_port = None
            for item in items:
                if isinstance(item, PortItem) and item != self.temp_wire_start:
                    target_port = item
                    break
            
            if target_port:
                self.app_builder.make_connection(self.temp_wire_start, target_port)
            else:
                self.app_builder.break_connection(self.temp_wire_start)
            
            self.temp_wire_start = None
            self.temp_wire_pos = None
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

class NodeEditorView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.RubberBandDrag) 
        self.setAcceptDrops(True) # ⚠️ REQUIRED FOR DRAG & DROP ON CANVAS

    def dragEnterEvent(self, event):
        super().dragEnterEvent(event)
        
        if not event.isAccepted():
            # Yahan self.scene() kaam karega kyunki ye View class hai
            current_mode = getattr(self.scene().app_builder, 'current_mode', 'app_builder')
            if event.mimeData().hasFormat("application/x-logic-item") and current_mode == "node_editor":
                event.acceptProposedAction()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        if not event.isAccepted():
            current_mode = getattr(self.scene().app_builder, 'current_mode', 'app_builder')
            if event.mimeData().hasFormat("application/x-logic-item") and current_mode == "node_editor":
                event.acceptProposedAction()

    def dropEvent(self, event):
        super().dropEvent(event)
        
        if not event.isAccepted():
            current_mode = getattr(self.scene().app_builder, 'current_mode', 'app_builder')
            mime = event.mimeData()
            
            if mime.hasFormat("application/x-logic-item") and current_mode == "node_editor":
                raw_data = mime.data("application/x-logic-item")
                data = json.loads(raw_data.data().decode('utf-8'))
                text = mime.text()
                scene_pos = self.mapToScene(event.pos())
                
                if text.startswith("AI:") or text.startswith("Func:") or text.startswith("Custom:"):
                    ntype = "AI" if text.startswith("AI:") else ("Custom" if text.startswith("Custom:") else "Func")
                    self.scene().app_builder.spawn_floating_logic_node(data, ntype, scene_pos.x(), scene_pos.y())
                event.acceptProposedAction()

    def contextMenuEvent(self, event):
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #252526; color: white; border: 1px solid #454545; font-size: 13px; } QMenu::item:selected { background-color: #007acc; }")
        
        current_mode = getattr(self.scene().app_builder, 'current_mode', 'app_builder')
        
        # Mode check karke sirf wahi menu dikhayega
        if current_mode == "app_builder":
            ui_menu = menu.addMenu("🖥️ Add UI Element")
            for e in ["Button", "Label", "Static Text", "Input Text Field", "Dropdown", "Image", "Console", "Plain Text Edit"]:
                ui_menu.addAction(e, lambda checked=False, val=e: self.scene().app_builder.spawn_element_in_app(val))
        else:
            canvas_menu = menu.addMenu("🎴 Add Canvas Node")
            for e in ["List", "Image", "Constructor", "Output Window", "Prompt", "Plain Text Edit"]:
                canvas_menu.addAction(e, lambda checked=False, val=e: self.scene().app_builder.spawn_canvas_node(val))
                
        menu.addSeparator()
        
        ai_menu = menu.addMenu("🧠 Add AI Model")
        for f in parse_ai_functions():
            ai_menu.addAction(f['name'], lambda checked=False, val=f: self.scene().app_builder.spawn_floating_logic_node(val, "AI"))
            
        func_menu = menu.addMenu("🔧 Add Standard Function")
        for f in parse_custom_functions():
            func_menu.addAction(f['name'], lambda checked=False, val=f: self.scene().app_builder.spawn_floating_logic_node(val, "Func"))

        menu.exec_(event.globalPos())

    def wheelEvent(self, event):
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(zoom_factor, zoom_factor)

    # --- NEW: KEYBOARD SHORTCUTS FOR DELETION ---
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if hasattr(self.scene(), 'app_builder'):
                self.scene().app_builder.universal_delete()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            super().mousePressEvent(QMouseEvent(event.type(), event.pos(), Qt.LeftButton, Qt.LeftButton, event.modifiers()))
        else: super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            super().mouseReleaseEvent(QMouseEvent(event.type(), event.pos(), Qt.LeftButton, Qt.LeftButton, event.modifiers()))
            self.setDragMode(QGraphicsView.RubberBandDrag)
        else: super().mouseReleaseEvent(event)

class ClickableThumb(QWidget):
    def __init__(self, file_path, click_callback, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.click_callback = click_callback
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background-color: #333; border: 1px solid #555; border-radius: 4px;")
        self.setFixedSize(120, 140)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        
        # Load image fast using QImage
        img = QImage(file_path)
        if not img.isNull():
            pixmap = QPixmap.fromImage(img).scaled(100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_label.setPixmap(pixmap)
            dim_str = f"{img.width()}x{img.height()}"
        else:
            self.img_label.setText("📄 File")
            dim_str = "N/A"
            
        layout.addWidget(self.img_label)
        
        name = os.path.basename(file_path)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("border: none; font-size: 10px; color: white;")
        name_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_lbl)
        
        dim_lbl = QLabel(dim_str)
        dim_lbl.setStyleSheet("border: none; font-size: 9px; color: #aaa;")
        dim_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(dim_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.click_callback(self.file_path)
class CanvasImageNodeProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"image_node_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        self.file_path = ""
        
        self.widget = QWidget()
        self.widget.resize(320, 380)
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #9c27b0; border-radius: 6px; color: white;")
        
        self.main_layout = QVBoxLayout(self.widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"🖼️ Single Image Node")
        self.title_bar.setStyleSheet("background-color: #9c27b0; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        self.main_layout.addWidget(self.title_bar)
        
        self.preview_img = QLabel("Double Click to Browse")
        self.preview_img.setAlignment(Qt.AlignCenter)
        self.preview_img.setStyleSheet("background-color: #111; border: 1px solid #555;")
        self.main_layout.addWidget(self.preview_img, 1)
        
        self.info_lbl = QLabel("Waiting for image selection...")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("font-size: 11px; color: #ccc; border: none; padding: 5px;")
        self.main_layout.addWidget(self.info_lbl)
        
        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False; self._is_resizing = False; self._margin = 10
        
        self.port_out = PortItem(self, 'media_out', True)
        self.port_out.setPos(self.widget.width(), 40)
        
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self.prompt_for_image)

    def prompt_for_image(self):
        path, _ = QFileDialog.getOpenFileName(self.widget, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp *.heic)")
        if path:
            self.file_path = path
            self.load_image()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.preview_img.geometry().contains(event.pos().toPoint() if hasattr(event.pos(), 'toPoint') else event.pos()):
            self.prompt_for_image()
        super().mouseDoubleClickEvent(event)

    def load_image(self):
        img = QImage(self.file_path)
        if not img.isNull():
            pix = QPixmap.fromImage(img).scaled(self.widget.width()-20, self.widget.height()-80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_img.setPixmap(pix)
            weight_kb = os.path.getsize(self.file_path) / 1024
            dim_str = f"{img.width()}x{img.height()}"
            self.info_lbl.setText(f"<b>Path:</b> ...{self.file_path[-30:]}<br><b>Size:</b> {weight_kb:.1f} KB | <b>Res:</b> {dim_str}")
        else:
            self.preview_img.setText("Invalid Image")

    def get_payload(self):
        if self.file_path and os.path.exists(self.file_path):
            return {"type": "single", "data": [self.file_path]}
        return None

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #ffc107; border-radius: 6px; color: white;" if state else "background-color: #252526; border: 2px solid #9c27b0; border-radius: 6px; color: white;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
        if event.pos().y() <= 35: 
            self.app_builder.handle_canvas_node_selection(self); self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            new_w, new_h = max(250, self._start_size.width() + delta.x()), max(300, self._start_size.height() + delta.y())
            self.widget.resize(int(new_w), int(new_h)); self.port_out.setPos(new_w, 40)
            if self.file_path: self.load_image()
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update(); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False; super().mouseReleaseEvent(event)


class CanvasListNodeProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"list_node_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        self.file_list = []
        
        self.widget = QWidget()
        self.widget.resize(400, 500)
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #007acc; border-radius: 6px; color: white;")
        
        self.main_layout = QVBoxLayout(self.widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"📂 Batch List Node")
        self.title_bar.setStyleSheet("background-color: #007acc; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        self.main_layout.addWidget(self.title_bar)
        
        # --- VIEW 1: FULL GRID DIRECTORY VIEW ---
        self.grid_container = QWidget()
        grid_layout = QVBoxLayout(self.grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Paste directory path here...")
        self.path_input.setStyleSheet("background-color: #1e1e1e; border: 1px solid #555; padding: 4px;")
        
        btn_browse = QPushButton("📁 Browse")
        btn_browse.setStyleSheet("background-color: #444; border: 1px solid #666; padding: 4px;")
        btn_browse.clicked.connect(self.browse_folder)
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(btn_browse)
        grid_layout.addLayout(path_layout)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Format:"))
        self.ext_combo = QComboBox()
        self.ext_combo.addItems([".*", ".jpg", ".jpeg", ".png", ".webp", ".bmp"])
        self.ext_combo.setStyleSheet("background-color: #1e1e1e;")
        filter_layout.addWidget(self.ext_combo)
        
        btn_load = QPushButton("⬇️ Load Deep Scan")
        btn_load.setStyleSheet("background-color: #28a745; font-weight: bold; padding: 4px;")
        btn_load.clicked.connect(self.load_directory)
        filter_layout.addWidget(btn_load)
        grid_layout.addLayout(filter_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: 1px solid #444; background-color: #1e1e1e;")
        
        self.scroll_content = QWidget()
        self.thumbs_layout = QGridLayout(self.scroll_content)
        self.scroll_content.setLayout(self.thumbs_layout)
        self.scroll_area.setWidget(self.scroll_content)
        grid_layout.addWidget(self.scroll_area)
        
        self.status_lbl = QLabel("Loaded: 0 Files")
        self.status_lbl.setStyleSheet("color: #aaa; font-size:10px;")
        grid_layout.addWidget(self.status_lbl)
        
        self.main_layout.addWidget(self.grid_container)
        
        # --- VIEW 2: FULLSCREEN PREVIEW ---
        self.preview_container = QWidget()
        self.preview_container.setVisible(False)
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_back = QPushButton("🔙 Back to Grid")
        btn_back.setStyleSheet("background-color: #d32f2f; font-weight: bold; padding: 5px;")
        btn_back.clicked.connect(self.hide_preview)
        preview_layout.addWidget(btn_back)
        
        self.preview_img = QLabel()
        self.preview_img.setAlignment(Qt.AlignCenter)
        self.preview_img.setStyleSheet("background-color: #111; border: 1px solid #555;")
        preview_layout.addWidget(self.preview_img, 1)
        
        self.preview_info = QLabel()
        self.preview_info.setWordWrap(True)
        self.preview_info.setStyleSheet("font-size: 11px; color: #ccc; border: none; padding: 5px;")
        preview_layout.addWidget(self.preview_info)
        
        self.main_layout.addWidget(self.preview_container)
        
        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False; self._is_resizing = False; self._margin = 10
        
        self.port_out = PortItem(self, 'media_out', True)
        self.port_out.setPos(self.widget.width(), 40)
        
    def browse_folder(self):
        path = QFileDialog.getExistingDirectory(self.widget, "Select Directory")
        if path:
            self.path_input.setText(path)
            
    def load_directory(self):
        path = self.path_input.text().strip()
        ext = self.ext_combo.currentText().replace(".*", "")
        self.file_list = []
        
        if not os.path.exists(path):
            self.status_lbl.setText("❌ Invalid Directory")
            return
            
        for i in reversed(range(self.thumbs_layout.count())): 
            w = self.thumbs_layout.itemAt(i).widget()
            if w: w.deleteLater()
            
        row, col, max_cols, count = 0, 0, 3, 0
        
        for root_dir, _, files in os.walk(path):
            for file in files:
                if count >= 100: break # UI Safety limit for thumbnails
                if ext == "" or file.lower().endswith(ext.lower()):
                    full_path = os.path.join(root_dir, file)
                    self.file_list.append(full_path)
                    
                    thumb = ClickableThumb(full_path, self.show_preview)
                    self.thumbs_layout.addWidget(thumb, row, col)
                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1
                    count += 1
            if count >= 100: break
            
        self.status_lbl.setText(f"Loaded: {len(self.file_list)} Files Ready")
            
    def show_preview(self, file_path):
        self.grid_container.setVisible(False)
        self.preview_container.setVisible(True)
        img = QImage(file_path)
        if not img.isNull():
            pix = QPixmap.fromImage(img).scaled(self.widget.width()-20, self.widget.height()-120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_img.setPixmap(pix)
            dim_str = f"{img.width()} x {img.height()} px"
        else:
            self.preview_img.setText("No Preview Available")
            dim_str = "Unknown"
            
        weight_kb = os.path.getsize(file_path) / 1024
        file_name = os.path.basename(file_path)
        info = f"<b>Name:</b> {file_name}<br><b>Size:</b> {weight_kb:.2f} KB | <b>Dim:</b> {dim_str}<br><b>Path:</b> {file_path}"
        self.preview_info.setText(info)
        
    def hide_preview(self):
        self.preview_container.setVisible(False)
        self.grid_container.setVisible(True)

    def get_payload(self):
        if self.file_list: return {"type": "list", "data": self.file_list}
        return None

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #ffc107; border-radius: 6px; color: white;" if state else "background-color: #252526; border: 2px solid #007acc; border-radius: 6px; color: white;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
        if event.pos().y() <= 35: 
            self.app_builder.handle_canvas_node_selection(self); self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            new_w, new_h = max(300, self._start_size.width() + delta.x()), max(400, self._start_size.height() + delta.y())
            self.widget.resize(int(new_w), int(new_h)); self.port_out.setPos(new_w, 40)
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos)); self.app_builder.node_scene.update(); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False; super().mouseReleaseEvent(event)


# ----------------------------------------------------
# 🎨 PAINT DIALOG CLASSES (Add this right before CanvasFloatingFuncProxy)
# ----------------------------------------------------
class InteractivePaintLabel(QLabel):
    def __init__(self, img_path, b_size):
        super().__init__()
        from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
        from PyQt5.QtCore import Qt, QPoint
        self.brush_size = b_size
        self.drawing = False
        self.last_point = QPoint()

        self.orig_pixmap = QPixmap(img_path)
        max_w, max_h = 800, 550
        if self.orig_pixmap.width() > max_w or self.orig_pixmap.height() > max_h:
            self.orig_pixmap = self.orig_pixmap.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.setFixedSize(self.orig_pixmap.size())
        self.display_pixmap = self.orig_pixmap.copy()
        self.mask_img = QImage(self.orig_pixmap.size(), QImage.Format_Grayscale8)
        self.mask_img.fill(Qt.black)

        self.setPixmap(self.display_pixmap)
        self.setCursor(Qt.CrossCursor)
        self.setStyleSheet("border: 2px solid #555;")

    def clear_mask(self):
        from PyQt5.QtCore import Qt
        self.display_pixmap = self.orig_pixmap.copy()
        self.mask_img.fill(Qt.black)
        self.setPixmap(self.display_pixmap)

    def mousePressEvent(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = event.pos()
            self.draw_point(event.pos())

    def mouseMoveEvent(self, event):
        from PyQt5.QtCore import Qt
        if (event.buttons() & Qt.LeftButton) and self.drawing:
            self.draw_line(self.last_point, event.pos())
            self.last_point = event.pos()

    def mouseReleaseEvent(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.LeftButton:
            self.drawing = False

    def draw_point(self, point):
        self.draw_line(point, point)

    def draw_line(self, p1, p2):
        from PyQt5.QtGui import QPainter, QPen, QColor
        from PyQt5.QtCore import Qt
        painter = QPainter(self.display_pixmap)
        pen = QPen(QColor(255, 0, 50, 150), self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(p1, p2)
        painter.end()

        mask_painter = QPainter(self.mask_img)
        mask_pen = QPen(Qt.white, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        mask_painter.setPen(mask_pen)
        mask_painter.drawLine(p1, p2)
        mask_painter.end()
        self.setPixmap(self.display_pixmap)

class InteractivePaintDialog(QDialog):
    def __init__(self, img_path):
        super().__init__()
        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton
        from PyQt5.QtCore import Qt
        self.setWindowTitle("🎨 Draw Mask for AI Inpaint")
        self.setModal(True)
        self.setFixedSize(850, 650)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        ctrl_layout = QHBoxLayout()
        brush_lbl = QLabel("🖌️ Brush Size:")
        brush_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        ctrl_layout.addWidget(brush_lbl)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(5, 150)
        self.slider.setValue(30)
        self.slider.setFixedWidth(200)
        self.slider.setStyleSheet("QSlider::handle:horizontal { background: #007acc; width: 16px; border-radius: 8px; margin: -4px 0; } QSlider::groove:horizontal { height: 8px; background: #555; border-radius: 4px; }")
        ctrl_layout.addWidget(self.slider)
        
        self.size_val_lbl = QLabel("30 px")
        self.size_val_lbl.setStyleSheet("font-weight: bold; color: #007acc; font-size: 14px; min-width: 50px;")
        ctrl_layout.addWidget(self.size_val_lbl)
        self.slider.valueChanged.connect(self.update_brush)
        ctrl_layout.addStretch()
        
        self.btn_clear = QPushButton("🧹 Clear Canvas")
        self.btn_clear.setStyleSheet("background-color: #dc3545; color: white; padding: 8px 15px; border-radius: 4px;")
        self.btn_clear.clicked.connect(self.clear_canvas)
        
        self.btn_save = QPushButton("✅ Done (Save Mask)")
        self.btn_save.setStyleSheet("background-color: #28a745; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self.accept)
        
        ctrl_layout.addWidget(self.btn_clear)
        ctrl_layout.addWidget(self.btn_save)
        self.layout.addLayout(ctrl_layout)

        self.paint_label = InteractivePaintLabel(img_path, self.slider.value())
        img_container = QHBoxLayout()
        img_container.addStretch()
        img_container.addWidget(self.paint_label)
        img_container.addStretch()
        self.layout.addLayout(img_container, 1)

    def update_brush(self, val):
        self.paint_label.brush_size = val
        self.size_val_lbl.setText(f"{val} px")

    def clear_canvas(self):
        self.paint_label.clear_mask()

# ----------------------------------------------------
# 🔄 REPLACE YOUR EXISTING CanvasFloatingFuncProxy WITH THIS:
# ----------------------------------------------------
class CanvasFloatingFuncProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, func_data, ntype, x=0, y=0):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.func_data = func_data
        self.ntype = ntype
        self.elem_id = f"float_func_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        
        self.widget = QWidget()
        self.widget.resize(250, 200)
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #e91e63; border-radius: 6px; color: white;")
        
        self.main_layout = QVBoxLayout(self.widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        icon = "🧠" if ntype == "AI" else ("🌐" if ntype == "Custom" else "🔧")
        self.title_bar = QLabel(f"{icon} {func_data['name']}")
        self.title_bar.setStyleSheet("background-color: #e91e63; color: white; padding: 5px; border-radius: 3px; font-weight: bold; font-size: 11px;")
        self.main_layout.addWidget(self.title_bar)
        
        self.param_inputs = {}
        form_layout = QFormLayout()
        form_layout.setContentsMargins(2, 5, 2, 5)
        
        for arg in func_data.get("args", []):
            if arg.lower() in ["log_console", "code_node_id"]: continue
            
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            inp = QLineEdit()
            
            # --- AUTO-FILL DEFAULT VALUES ---
            default_val = func_data.get("defaults", {}).get(arg, "")
            if default_val != "":
                inp.setText(str(default_val))
            # --------------------------------
            
            inp.setStyleSheet("background-color: #1e1e1e; border: 1px solid #555; font-size: 10px; padding: 2px;")
            row_layout.addWidget(inp)
            
            # 🔥 DYNAMIC DRAW BUTTON IN UI
            if arg.lower() in ["mask_path", "mask_image_path"]:
                btn_draw = QPushButton("🖌️ Draw")
                btn_draw.setStyleSheet("background-color: #e91e63; color: white; font-size: 10px; font-weight: bold; border-radius: 2px; padding: 2px 5px;")
                btn_draw.setCursor(Qt.PointingHandCursor)
                btn_draw.clicked.connect(lambda _, i=inp: self.open_mask_drawer(i))
                row_layout.addWidget(btn_draw)
            
            lbl = QLabel(arg)
            lbl.setStyleSheet("font-size: 10px; border: none;")
            form_layout.addRow(lbl, row_widget)
            self.param_inputs[arg] = inp
            
        self.main_layout.addLayout(form_layout)
        self.main_layout.addStretch()
        
        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False; self._is_resizing = False; self._margin = 10
        
        self.port_in = PortItem(self, 'logic_in', False)
        self.port_in.setPos(0, 25)
        self.port_out = PortItem(self, 'logic_out', True)
        self.port_out.setPos(self.widget.width(), 25)
        self.widget.resize(250, 50 + (len(self.param_inputs) * 30))

    def open_mask_drawer(self, input_field):
        import os, tempfile, uuid, cv2
        image_path = None
        
        # Connect ki hui Image ko dhoondna
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p1 == self.port_out and hasattr(p2.parent_node, 'port_in'):
                constructor = p2.parent_node
                for cp1, cp2 in getattr(self.app_builder, 'canvas_connections', []):
                    if cp2 == constructor.port_in:
                        if hasattr(cp1.parent_node, 'file_path') and cp1.parent_node.file_path:
                            image_path = cp1.parent_node.file_path
                            break
                break
                
        if not image_path or not os.path.exists(image_path):
            QMessageBox.warning(self.widget, "No Image Found", "Pehle 'Image Node' ko 'Constructor' se connect karein, fir Draw button dabayein!")
            return
            
        dialog = InteractivePaintDialog(image_path)
        if dialog.exec_() == QDialog.Accepted:
            temp_dir = os.path.join(tempfile.gettempdir(), "ui_masks")
            os.makedirs(temp_dir, exist_ok=True)
            out_path = os.path.join(temp_dir, f"drawn_mask_{uuid.uuid4().hex[:6]}.png")
            
            dialog.paint_label.mask_img.save(out_path)
            
            mask_arr = cv2.imread(out_path, cv2.IMREAD_GRAYSCALE)
            orig_cv = cv2.imread(image_path)
            orig_h, orig_w = orig_cv.shape[:2]
            mask_resized = cv2.resize(mask_arr, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
            _, final_mask = cv2.threshold(mask_resized, 127, 255, cv2.THRESH_BINARY)
            cv2.imwrite(out_path, final_mask)
            
            input_field.setText(out_path)
            QMessageBox.information(self.widget, "Success", "Mask perfectly generated and linked! Ab Constructor par 'Run' dabayein.")

    def get_function_chain(self):
        chain = [{
            "name": self.func_data["name"],
            "type": self.ntype,
            "params": {k: getattr(self.param_inputs[k], "text", lambda: "")() for k in self.param_inputs}
        }]
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p1 == self.port_out and isinstance(p2.parent_node, CanvasFloatingFuncProxy):
                chain.extend(p2.parent_node.get_function_chain())
        return chain

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #ffc107; border-radius: 6px; color: white;" if state else "background-color: #252526; border: 2px solid #e91e63; border-radius: 6px; color: white;")

    def mousePressEvent(self, event):
        if event.pos().y() <= 35: 
            self.app_builder.handle_canvas_node_selection(self) 
            self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update(); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_moving = False; super().mouseReleaseEvent(event)


class CanvasConstructorNodeProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"constructor_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        self.output_payload = None 
        
        self.widget = QWidget()
        self.widget.resize(250, 180)
        self.widget.setStyleSheet("background-color: #1e1e1e; border: 2px solid #ff9800; border-radius: 6px; color: white;")
        
        self.main_layout = QVBoxLayout(self.widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"⚙️ Constructor Engine")
        self.title_bar.setStyleSheet("background-color: #ff9800; color: black; padding: 5px; border-radius: 3px; font-weight: bold;")
        self.main_layout.addWidget(self.title_bar)
        
        # 🔥 SMART STATUS UI
        self.lbl_in = QLabel("📥 Input: None")
        self.lbl_func = QLabel("🧠 Logic: None")
        self.lbl_status = QLabel("🟢 Status: Idle")
        
        self.lbl_in.setStyleSheet("color: #4fc3f7; font-size: 11px;")
        self.lbl_func.setStyleSheet("color: #ff8a65; font-size: 11px;")
        self.lbl_status.setStyleSheet("color: #aed581; font-size: 11px; font-weight: bold;")
        
        for lbl in [self.lbl_in, self.lbl_func, self.lbl_status]:
            lbl.setWordWrap(True)
            self.main_layout.addWidget(lbl)
        
        self.btn_run = QPushButton("▶️ Run & Process")
        self.btn_run.setStyleSheet("background-color: #28a745; font-weight: bold; padding: 8px; border-radius: 3px; margin-top: 5px;")
        self.btn_run.clicked.connect(self.execute_node)
        self.main_layout.addWidget(self.btn_run)
        
        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False
        
        # 3 Ports: In (Left), Logic (Top), Out (Right)
        self.port_in = PortItem(self, 'media_in', False)
        self.port_in.setPos(0, 60)
        
        self.port_logic = PortItem(self, 'logic_in', False)
        self.port_logic.setPos(125, 0)
        self.port_logic.setBrush(QColor("#e91e63"))
        
        self.port_out = PortItem(self, 'media_out', True)
        self.port_out.setPos(self.widget.width(), 60)

    # 🔥 EXECUTE AND TRACK LOGIC
    def execute_node(self):
        self.lbl_status.setText("Status: Fetching Data...")
        QApplication.processEvents()
        
        input_payload = None
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p2 == self.port_in:
                if hasattr(p1.parent_node, 'output_payload') and p1.parent_node.output_payload:
                    input_payload = p1.parent_node.output_payload 
                elif hasattr(p1.parent_node, 'get_payload'):
                    input_payload = p1.parent_node.get_payload() 
                break

        logic_chain = []
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p2 == self.port_logic and isinstance(p1.parent_node, CanvasFloatingFuncProxy):
                logic_chain = p1.parent_node.get_function_chain()
                break

        if not input_payload:
            self.lbl_status.setText("❌ Error: No Media Input"); self.lbl_in.setText("📥 Input: None"); return
        if not logic_chain:
            self.lbl_status.setText("❌ Error: No Logic Connected"); self.lbl_func.setText("🧠 Logic: None"); return

        is_list = (input_payload["type"] == "list")
        total_items = len(input_payload["data"])
        
        if is_list: self.lbl_in.setText(f"📥 Input: {total_items} items (List)")
        else: self.lbl_in.setText(f"📥 Input: ...{str(input_payload['data'][0])[-20:]}")
            
        func_names = [f["name"] for f in logic_chain]
        self.lbl_func.setText(f"🧠 Logic: {' ➔ '.join(func_names)}")
        
        self.lbl_status.setText(f"⚙️ Processing 0/{total_items}...")
        
        # --- NEW: Trigger Animation on Output Node ---
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p1 == self.port_out and hasattr(p2.parent_node, 'set_processing_state'):
                p2.parent_node.set_processing_state()

        self.btn_run.setEnabled(False) # Multiple clicks rokne ke liye button disable karein
        QApplication.processEvents()
        
        # --- BACKGROUND THREAD START KAREIN ---
        self.worker = AIWorkerThread(input_payload, logic_chain, is_list)
        self.worker.progress.connect(self.update_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def update_worker_progress(self, current, total):
        self.lbl_status.setText(f"⚙️ Processing {current}/{total}...")

    def on_worker_finished(self, final_payload):
        self.output_payload = final_payload
        self.lbl_status.setText("✅ Processed Successfully")
        self.btn_run.setEnabled(True) # Button wapas enable karein
        
        # Send to Output Node
        output_found = False
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p1 == self.port_out and hasattr(p2.parent_node, 'receive_payload'):
                p2.parent_node.receive_payload(self.output_payload)
                output_found = True
                
        if not output_found: self.lbl_status.setText("✅ Done (No Output Linked)")

    def on_worker_error(self, err_msg):
        self.lbl_status.setText("❌ Execution Failed")
        self.btn_run.setEnabled(True)
        
        # Error aane par animation rokne ke liye
        for p1, p2 in getattr(self.app_builder, 'canvas_connections', []):
            if p1 == self.port_out and hasattr(p2.parent_node, 'receive_payload'):
                p2.parent_node.receive_payload(None)
                
        QMessageBox.critical(self.widget, "Node Error", f"Failed:\n{err_msg}")

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #1e1e1e; border: 2px solid #ffc107; border-radius: 6px; color: white;" if state else "background-color: #1e1e1e; border: 2px solid #ff9800; border-radius: 6px; color: white;")

    def mousePressEvent(self, event):
        if event.pos().y() <= 35: 
            self.app_builder.handle_canvas_node_selection(self) 
            self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update(); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_moving = False; super().mouseReleaseEvent(event)


# ----------------------------------------------------
# ⚙️ BACKGROUND AI WORKER THREAD (PREVENTS UI FREEZE)
# ----------------------------------------------------
from PyQt5.QtCore import QThread, pyqtSignal

class AIWorkerThread(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, input_payload, logic_chain, is_list):
        super().__init__()
        self.input_payload = input_payload
        self.logic_chain = logic_chain
        self.is_list = is_list

    def run(self):
        import sys, os, tempfile, uuid
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        import functions, ai_functions, customCode
        
        temp_dir = os.path.join(tempfile.gettempdir(), f"node_out_{uuid.uuid4().hex[:6]}")
        os.makedirs(temp_dir, exist_ok=True)
        
        processed_data = []
        total_items = len(self.input_payload["data"])
        
        try:
            for idx, file_path in enumerate(self.input_payload["data"]):
                self.progress.emit(idx + 1, total_items) # UI ko update bhejo
                
                current_img = file_path
                for logic in self.logic_chain:
                    func_name = logic["name"]
                    module = ai_functions if logic["type"] == "AI" else (customCode if logic["type"] == "Custom" else functions)
                    func = getattr(module, func_name)
                    
                    kwargs = {}
                    for k, v in logic["params"].items():
                        v_str = str(v)
                        if not v_str: continue # Skip empty strings for defaults
                        if v_str in ["True", "False"]: kwargs[k] = (v_str == "True")
                        elif v_str == "None": kwargs[k] = None
                        else:
                            try: kwargs[k] = int(v_str) if v_str.isdigit() else float(v_str)
                            except ValueError: kwargs[k] = v_str
                            
                    kwargs['image_path'] = current_img
                    kwargs['output_dir'] = temp_dir 
                    
                    result = func(**kwargs)
                    if isinstance(result, str) and os.path.exists(result): current_img = result
                    elif isinstance(result, list) and result: current_img = result[0] 
                    
                processed_data.append(current_img)
                
            output_payload = {"type": "list" if self.is_list or len(processed_data)>1 else "single", "data": processed_data}
            self.finished.emit(output_payload) # Kaam khatam hone par final data bhejo
            
        except Exception as e:
            self.error.emit(str(e)) # Error aane par UI ko batao
# ----------------------------------------------------

# ----------------------------------------------------
# 🌌 PREMIUM PULSING DOTS ANIMATION WIDGET
# ----------------------------------------------------
class PulsingDotsAnimation(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import QTimer
        import random
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.step = 0
        self.cols = 12
        self.rows = 8
        self.dots = []
        
        # Random parameters assign karna har dot ke liye
        for r in range(self.rows):
            for c in range(self.cols):
                self.dots.append({
                    'r': r, 'c': c,
                    'phase': random.uniform(0, 6.28), # Random start cycle
                    'speed': random.uniform(0.05, 0.2), # Random pulsing speed
                    'base_size': random.uniform(2, 6) # Random base size
                })

    def start_anim(self):
        self.step = 0
        self.timer.start(40) # ~25 FPS for smooth animation

    def stop_anim(self):
        self.timer.stop()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor
        from PyQt5.QtCore import Qt
        import math
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        # Center "Generating..." Text
        painter.setPen(QColor("#ff9800"))
        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "Generating...")

        painter.setPen(Qt.NoPen)
        
        # Grid Spacing
        cell_w = w / (self.cols + 2)
        cell_h = h / (self.rows + 2)
        offset_x = cell_w * 1.5
        offset_y = cell_h * 1.5

        # Har dot ko math (sine wave) se animate karna
        for dot in self.dots:
            size_wave = math.sin(self.step * dot['speed'] + dot['phase'])
            radius = dot['base_size'] + (size_wave * dot['base_size'] * 0.7)
            
            # Opacity fade calculation
            alpha = int(60 + (size_wave + 1) * 90) 
            
            # --- NEW: Output panel background tone (#252526) ka lighter shade ---
            painter.setBrush(QColor(130, 130, 138, min(255, max(0, alpha)))) 
            
            cx = offset_x + dot['c'] * cell_w
            cy = offset_y + dot['r'] * cell_h
            painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
            
        self.step += 1
# ----------------------------------------------------

class CanvasOutputNodeProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"output_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        self.current_payload = None
        
        self.widget = QWidget()
        self.widget.resize(400, 500)
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #4caf50; border-radius: 6px; color: white;")
        
        self.main_layout = QVBoxLayout(self.widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_bar = QLabel(f"✅ Final Output Viewer")
        self.title_bar.setStyleSheet("background-color: #4caf50; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        self.main_layout.addWidget(self.title_bar)
        
        # 🗂️ DYNAMIC UI STACK
        from PyQt5.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        
       # 1. EMPTY STATE
        self.empty_view = QLabel("Awaiting Payload...\n(Connect Engine & Execute)")
        self.empty_view.setAlignment(Qt.AlignCenter)
        self.empty_view.setStyleSheet("color: #777; font-size: 14px;")
        self.stack.addWidget(self.empty_view)
        
        # --- PREMIUM LOADING ANIMATION STATE ---
        self.loading_view = PulsingDotsAnimation(self.widget)
        self.stack.addWidget(self.loading_view)
        # ---------------------------------------
        
        # 2. SINGLE VIEW
        self.single_view = QWidget()
        sv_layout = QVBoxLayout(self.single_view)
        sv_layout.setContentsMargins(0,0,0,0)
        self.single_img_lbl = QLabel()
        self.single_img_lbl.setAlignment(Qt.AlignCenter)
        self.single_img_lbl.setStyleSheet("background-color: #111; border: 1px solid #444;")
        sv_layout.addWidget(self.single_img_lbl, 1)
        
        self.btn_save_single = QPushButton("💾 Save Image")
        self.btn_save_single.setStyleSheet("background-color: #007acc; padding: 10px; font-weight: bold; font-size: 14px; border-radius: 4px;")
        self.btn_save_single.clicked.connect(self.save_data)
        sv_layout.addWidget(self.btn_save_single)
        self.stack.addWidget(self.single_view)
        
        # 3. GRID/LIST VIEW
        self.grid_view = QWidget()
        gv_layout = QVBoxLayout(self.grid_view)
        gv_layout.setContentsMargins(0,0,0,0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        gv_layout.addWidget(self.scroll, 1)
        
        self.btn_save_batch = QPushButton("💾 Export Batch Folder")
        self.btn_save_batch.setStyleSheet("background-color: #007acc; padding: 10px; font-weight: bold; font-size: 14px; border-radius: 4px;")
        self.btn_save_batch.clicked.connect(self.save_data)
        gv_layout.addWidget(self.btn_save_batch)
        self.stack.addWidget(self.grid_view)
        
        self.main_layout.addWidget(self.stack, 1)
        
        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False; self._is_resizing = False; self._margin = 10
        
        self.port_in = PortItem(self, 'media_in', False)
        self.port_in.setPos(0, 40)

    # --- NEW ANIMATION METHODS ---
    # --- ANIMATION CONTROLS ---
    def set_processing_state(self):
        self.stack.setCurrentWidget(self.loading_view)
        self.loading_view.start_anim()

    def receive_payload(self, payload):
        self.loading_view.stop_anim()
        self.current_payload = payload
        if not payload or not payload["data"]:
            self.stack.setCurrentWidget(self.empty_view)
            return
            
        if payload["type"] == "single" or len(payload["data"]) == 1:
            self.stack.setCurrentWidget(self.single_view)
            img_path = payload["data"][0]
            if os.path.exists(img_path):
                img = QImage(img_path)
                pix = QPixmap.fromImage(img).scaled(self.widget.width()-20, self.widget.height()-100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.single_img_lbl.setPixmap(pix)
        else:
            self.stack.setCurrentWidget(self.grid_view)
            for i in reversed(range(self.grid_layout.count())): 
                w = self.grid_layout.itemAt(i).widget(); w.deleteLater() if w else None
            
            row, col, max_cols = 0, 0, 3
            for file_path in payload["data"]:
                if os.path.exists(file_path):
                    thumb = ClickableThumb(file_path, lambda x: None)
                    self.grid_layout.addWidget(thumb, row, col)
                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1

    def save_data(self):
        if not self.current_payload: return
        
        if self.current_payload["type"] == "single" or len(self.current_payload["data"]) == 1:
            src = self.current_payload["data"][0]
            dst, _ = QFileDialog.getSaveFileName(self.widget, "Save Processed Image", os.path.basename(src), "Images (*.png *.jpg *.jpeg)")
            if dst: 
                shutil.copy(src, dst)
                QMessageBox.information(self.widget, "Success", "Image saved successfully!")
        else:
            dst_folder = QFileDialog.getExistingDirectory(self.widget, "Select Folder to Save All Images")
            if dst_folder:
                for src in self.current_payload["data"]:
                    shutil.copy(src, os.path.join(dst_folder, os.path.basename(src)))
                QMessageBox.information(self.widget, "Success", f"Batch exported successfully to:\n{dst_folder}")

    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: #252526; border: 2px solid #ffc107; border-radius: 6px; color: white;" if state else "background-color: #252526; border: 2px solid #4caf50; border-radius: 6px; color: white;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
        if event.pos().y() <= 35: 
            self.app_builder.handle_canvas_node_selection(self) 
            self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            new_w, new_h = max(250, self._start_size.width() + delta.x()), max(300, self._start_size.height() + delta.y())
            self.widget.resize(int(new_w), int(new_h))
            if self.current_payload and self.current_payload["type"] == "single":
                self.receive_payload(self.current_payload)
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos))
            self.app_builder.node_scene.update()
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False
        super().mouseReleaseEvent(event)

class CanvasTextNodeProxy(QGraphicsProxyWidget):
    def __init__(self, app_builder, x=0, y=0):
        super().__init__()
        self.setFlag(QGraphicsProxyWidget.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.app_builder = app_builder
        self.elem_id = f"text_node_{uuid.uuid4().hex[:6]}"
        self.is_selected = False
        self.current_font_size = 18

        self.widget = QWidget()
        self.widget.resize(250, 150)
        self.widget.setStyleSheet("background-color: transparent; border: 2px dashed #777; border-radius: 6px;")

        self.main_layout = QVBoxLayout(self.widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        self.text_edit = QTextEdit("Write something here...")
        self.text_edit.setStyleSheet(f"background-color: rgba(30, 30, 30, 180); color: white; border: none; font-size: {self.current_font_size}px; font-weight: bold;")
        self.main_layout.addWidget(self.text_edit)

        self.setWidget(self.widget)
        self.setPos(float(x), float(y))
        self._is_moving = False; self._is_resizing = False; self._margin = 15
        
    def set_selected(self, state):
        self.is_selected = state
        self.widget.setStyleSheet("background-color: transparent; border: 2px dashed #ffc107; border-radius: 6px;" if state else "background-color: transparent; border: 2px dashed #777; border-radius: 6px;")

    def hoverMoveEvent(self, event):
        pos = event.pos(); rect = self.geometry(); w, h = rect.width(), rect.height(); x, y = pos.x(), pos.y()
        self._resize_dir = ""
        if y >= h - self._margin: self._resize_dir += "bottom"
        if x >= w - self._margin: self._resize_dir += "right"
        self.setCursor(Qt.SizeFDiagCursor if self._resize_dir == "bottomright" else Qt.SizeVerCursor if self._resize_dir == "bottom" else Qt.SizeHorCursor if self._resize_dir == "right" else Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self._resize_dir:
            self._is_resizing = True; self._start_size = self.widget.size(); self._start_pos = event.scenePos()
            event.accept(); return
        
        # Agar text box ke margins pe click karein toh move ho
        if event.pos().x() < 15 or event.pos().x() > self.widget.width() - 15 or event.pos().y() < 15 or event.pos().y() > self.widget.height() - 15:
            self.app_builder.handle_canvas_node_selection(self); self._is_moving = True; self._start_pos = event.scenePos(); self._start_geom_pos = self.pos()
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.scenePos() - self._start_pos
            new_w, new_h = max(100, self._start_size.width() + delta.x()), max(50, self._start_size.height() + delta.y())
            self.widget.resize(int(new_w), int(new_h))
            
            # 🔥 DYNAMIC FONT RESIZE ALGORITHM
            self.current_font_size = max(10, int(new_h * 0.2))
            self.text_edit.setStyleSheet(f"background-color: rgba(30, 30, 30, 180); color: white; border: none; font-size: {self.current_font_size}px; font-weight: bold;")
            
            self.app_builder.node_scene.update()
        elif self._is_moving:
            self.setPos(self._start_geom_pos + (event.scenePos() - self._start_pos)); self.app_builder.node_scene.update(); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_moving or self._is_resizing: self.app_builder.record_state()
        self._is_moving = False; self._is_resizing = False; super().mouseReleaseEvent(event)
        
class AppBuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        ensure_functions_file()
        ensure_ai_functions_file()
        ensure_custom_code_file()
        
        self.setWindowTitle("App Builder")
        self.setGeometry(150, 150, 1400, 900)
        
        self.current_project = None 
        self.selected_elements = []
        self.main_function_nodes = []
        self.master_pipeline_nodes = []
        self.element_nodes = []
        self.code_nodes = []
        
        self.selected_tree_item = None
        self.selected_main_func = None
        self.selected_master_pipe = None
        self.selected_code_node = None

        self.canvas_nodes = []
        self.selected_canvas_node = None

        self.undo_stack = []
        self.max_undo_steps = 50
        self.is_internal_change = False
        self.clipboard_data = None
        self.is_modified = False

        self.node_scene = NodeScene(self)
        self.node_view = NodeEditorView(self.node_scene, self)
        self.setCentralWidget(self.node_view)

        self.projects_data = {} # ⚠️ Multi-Tab Memory Storage
        self.current_tab_id = -1
        
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        
        # ⚠️ CHROME STYLE TAB BEHAVIOR
        self.tab_bar.setExpanding(False)         # Tabs ko full width lene se rokega (Left align karega)
        self.tab_bar.setElideMode(Qt.ElideRight) # Agar text bada hai ya tabs zyada hain toh "..." laga dega

        self.tab_bar.tabCloseRequested.connect(self.close_project_tab)
        self.tab_bar.currentChanged.connect(self.switch_project_tab)
        
        # Added min-width, max-width, border-radius, and hover effect for better UI
        self.tab_bar.setStyleSheet("""
            QTabBar::tab { 
                background: #2d2d30; 
                color: white; 
                padding: 8px 15px; 
                border: 1px solid #111; 
                border-top-left-radius: 6px; 
                border-top-right-radius: 6px;
                min-width: 120px;
                max-width: 220px;
            } 
            QTabBar::tab:selected { 
                background: #007acc; 
                font-weight: bold; 
            }
            QTabBar::tab:hover:!selected {
                background: #3e3e42;
            }
        """)
        main_layout.addWidget(self.tab_bar)
        
        self.node_scene = NodeScene(self)
        self.node_view = NodeEditorView(self.node_scene, self)
        main_layout.addWidget(self.node_view)
        
        self.setCentralWidget(main_widget)

        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.btn_build_app = QAction("🚀 Start Build App", self)
        self.btn_build_app.triggered.connect(self.start_build_app) # Button hamesha active rahega
        self.toolbar.addAction(self.btn_build_app)

        self.btn_node_editor = QAction("🎨 Node Image Editor", self)
        self.btn_node_editor.triggered.connect(self.start_node_editor) # Naya Node Tab logic
        self.toolbar.addAction(self.btn_node_editor)

        self.btn_open_file = QAction("📂 Open File", self)
        self.btn_open_file.triggered.connect(self.open_file)
        self.toolbar.addAction(self.btn_open_file)
        
        self.btn_save_project = QAction("💾 Save Project", self)
        self.btn_save_project.triggered.connect(self.save_project)
        self.btn_save_project.setEnabled(False)
        self.toolbar.addAction(self.btn_save_project)

        self.btn_save_as = QAction("💾 Save As...", self)
        self.btn_save_as.triggered.connect(self.save_project_as)
        self.btn_save_as.setEnabled(False)
        self.toolbar.addAction(self.btn_save_as)
        
        # --- NEW CLOSE PROJECT BUTTON ---
        self.btn_close_project = QAction("❌ Close Project", self)
        self.btn_close_project.triggered.connect(self.close_project_workspace)
        self.btn_close_project.setEnabled(False)
        self.toolbar.addAction(self.btn_close_project)

        self.btn_preview_app = QAction("👁️ Preview App", self)
        self.btn_preview_app.triggered.connect(self.preview_app)
        self.btn_preview_app.setEnabled(False)
        self.toolbar.addAction(self.btn_preview_app)

        self.btn_publish_app = QAction("📦 Publish App (EXE)", self)
        self.btn_publish_app.triggered.connect(self.publish_app)
        self.btn_publish_app.setEnabled(False)
        self.toolbar.addAction(self.btn_publish_app)

        self.btn_undo = QAction("↩️ Undo", self)
        self.btn_undo.setShortcut(QKeySequence.Undo)
        self.btn_undo.triggered.connect(self.perform_undo)
        self.btn_undo.setEnabled(False)
        self.toolbar.addAction(self.btn_undo)

        # --- HELP BUTTON ---
        self.btn_help = QAction("❓ Help / Instructions", self)
        self.btn_help.triggered.connect(self.show_help)
        self.toolbar.addAction(self.btn_help)

        # --- EXAMPLES BUTTON ---
        self.btn_load_ex = QAction("💡 Load UI Examples", self)
        self.btn_load_ex.triggered.connect(self.show_examples_dialog)
        self.toolbar.addAction(self.btn_load_ex)

        self.shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        self.shortcut_copy.activated.connect(self.copy_selection)
        
        self.shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        self.shortcut_paste.activated.connect(self.paste_selection)

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.save_project)

        self.shortcut_save_as = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.shortcut_save_as.activated.connect(self.save_project_as)

        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_search.activated.connect(self.open_search_palette)

        self.left_dock = QDockWidget("Workspace Tools", self)
        self.left_dock.setFeatures(QDockWidget.NoDockWidgetFeatures) 
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # --- NAYA REFRESH BUTTON ---
        btn_refresh = QPushButton("🔄 Refresh Backend Files")
        btn_refresh.setStyleSheet("background-color: #555; color: white; font-weight: bold; margin-bottom: 10px; padding: 5px;")
        btn_refresh.clicked.connect(self.refresh_all_lists)
        left_layout.addWidget(btn_refresh)
        # ---------------------------

        self.current_mode = "app_builder" # Default Start Mode

        # --- CONTAINER 1: APP BUILDER MODE ---
        self.app_mode_widget = QWidget()
        app_layout = QVBoxLayout(self.app_mode_widget)
        app_layout.setContentsMargins(0, 0, 0, 0)
        
        app_layout.addWidget(QLabel("<b>🖥️ UI Elements (App Builder):</b>"))
        ui_grid = QGridLayout()
        ui_elems = ["Button", "Label", "Static Text", "Input Field", "Dropdown", "Image", "Console", "Plain Text Edit"]
        for i, elem in enumerate(ui_elems):
            btn = QPushButton(f"➕ {elem.split(' ')[0]}")
            btn.setStyleSheet("background-color: #3e3e42; color: white; padding: 4px; font-size: 11px; border-radius: 3px;")
            real_elem = "Input Text Field" if elem == "Input Field" else elem
            btn.clicked.connect(lambda checked, e=real_elem: self.spawn_element_in_app(e))
            ui_grid.addWidget(btn, i // 2, i % 2)
        app_layout.addLayout(ui_grid)
        left_layout.addWidget(self.app_mode_widget)

        # --- CONTAINER 2: NODE IMAGE EDITOR MODE ---
        self.node_mode_widget = QWidget()
        node_layout = QVBoxLayout(self.node_mode_widget)
        node_layout.setContentsMargins(0, 0, 0, 0)
        
        node_layout.addWidget(QLabel("<b>🎴 ComfyUI Nodes (Image Edit):</b>"))
        canvas_grid = QGridLayout()
        canvas_elems = ["List", "Image", "Constructor", "Output Window", "Prompt", "Plain Text Edit"]
        for i, elem in enumerate(canvas_elems):
            display_name = "Output" if elem == "Output Window" else elem
            btn = QPushButton(f"🎴 {display_name}")
            btn.setStyleSheet("background-color: #007acc; color: white; padding: 4px; font-size: 11px; font-weight: bold; border-radius: 3px;")
            btn.clicked.connect(lambda checked, e=elem: self.spawn_canvas_node(e))
            canvas_grid.addWidget(btn, i // 2, i % 2)
        node_layout.addLayout(canvas_grid)
        left_layout.addWidget(self.node_mode_widget)
        
        # Default visibility
        self.node_mode_widget.setVisible(False)

        left_layout.addSpacing(15)
        
        left_layout.addWidget(QLabel("<b>🤖 AI Models (AI_Models/):</b>"))
        left_layout.addWidget(QLabel("<small>Drag AI nodes into Main Function:</small>"))
        
        self.ai_list = DraggableListWidget()
        self.ai_list.setStyleSheet("background-color: #2c1a3b; color: white; border-radius: 4px;") 
        parsed_ai_funcs = parse_ai_functions()
        for f in parsed_ai_funcs:
            item = QListWidgetItem(f"AI: {f['name']}")
            item.setData(Qt.UserRole, f)
            self.ai_list.addItem(item)
        left_layout.addWidget(self.ai_list)
        left_layout.addSpacing(15)
        
        left_layout.addWidget(QLabel("<b>Backend Attributes:</b>"))
        left_layout.addWidget(QLabel("<small>Drag these into Main Function:</small>"))

        # --- NEW GLOBAL USER CODE SECTION ---
        self.btn_ide = QPushButton("🌐 + Global Code IDE") # btn_ide ko self.btn_ide banaya
        self.btn_ide.setStyleSheet("background-color: #e65100; color: white; font-weight: bold; margin-bottom: 5px;")
        self.btn_ide.clicked.connect(self.spawn_global_ide)
        left_layout.addWidget(self.btn_ide)
        left_layout.addWidget(QLabel("<b>🛠️ Global User Code Edits:</b>"))
        left_layout.addWidget(QLabel("<small>Drag custom functions to Logic:</small>"))
        self.custom_code_list = DraggableListWidget()
        self.custom_code_list.setStyleSheet("background-color: #2b3a42; color: white; border-radius: 4px;") 
        left_layout.addWidget(self.custom_code_list)
        left_layout.addSpacing(15)
        self.refresh_custom_code_list()
        # ------------------------------------
        
        self.logic_list = DraggableListWidget()
        item_dir = QListWidgetItem("Directory Loop")
        item_dir.setData(Qt.UserRole, {"args": []})
        self.logic_list.addItem(item_dir)

        item_file = QListWidgetItem("File Loop")
        item_file.setData(Qt.UserRole, {"args": []})
        self.logic_list.addItem(item_file)

        item_smart = QListWidgetItem("Smart Filter Loop")
        item_smart.setData(Qt.UserRole, {"args": []})
        self.logic_list.addItem(item_smart)

        # ⚠️ YEH WALA ITEM ADD KAREIN:
        item_code = QListWidgetItem("Custom Code Node")
        item_code.setData(Qt.UserRole, {"args": []})
        self.logic_list.addItem(item_code)

        parsed_funcs = parse_custom_functions()
        for f in parsed_funcs:
            item = QListWidgetItem(f"Func: {f['name']}")
            item.setData(Qt.UserRole, f)
            self.logic_list.addItem(item)
            
        left_layout.addWidget(self.logic_list)
        
        self.btn_main = QPushButton("⚙️ + Main Function Panel") # btn_main ko self.btn_main banaya
        self.btn_main.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; margin-top: 10px;")
        self.btn_main.clicked.connect(self.spawn_main_function_node)
        left_layout.addWidget(self.btn_main)

        self.btn_master = QPushButton("👑 + Master Pipeline Panel") # btn_master ko self.btn_master banaya
        self.btn_master.setStyleSheet("background-color: #ff9800; color: black; font-weight: bold; margin-top: 5px;")
        self.btn_master.clicked.connect(self.spawn_master_pipeline_node)
        left_layout.addWidget(self.btn_master)

        left_layout.addStretch()
        self.left_dock.setWidget(left_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.left_dock)

        self.right_dock = QDockWidget("Properties", self)
        self.right_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        
        right_widget = QWidget()
        self.property_container_layout = QVBoxLayout(right_widget)
        self.property_container_layout.addWidget(QLabel("Select an element/node to edit."))
        self.property_container_layout.addStretch()
        
        self.right_dock.setWidget(right_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.right_dock)

        self.left_dock.hide()
        self.right_dock.hide()
        self.statusBar().showMessage("Ready")

    def refresh_all_lists(self):
        # 1. AI Models Refresh
        self.ai_list.clear()
        for f in parse_ai_functions():
            item = QListWidgetItem(f"AI: {f['name']}")
            item.setData(Qt.UserRole, f)
            self.ai_list.addItem(item)
            
        # 2. Logic List Refresh (Loops + Standard Functions)
        self.logic_list.clear()
        for i_name in ["Directory Loop", "File Loop", "Smart Filter Loop", "Custom Code Node"]:
            item = QListWidgetItem(i_name)
            item.setData(Qt.UserRole, {"args": []})
            self.logic_list.addItem(item)
        for f in parse_custom_functions():
            item = QListWidgetItem(f"Func: {f['name']}")
            item.setData(Qt.UserRole, f)
            self.logic_list.addItem(item)
            
        # 3. Custom Code Refresh
        self.refresh_custom_code_list()
        
        # Bottom bar me success message show karega
        self.statusBar().showMessage("🔄 All Backend Files Refreshed Successfully!", 3000)

    def refresh_custom_code_list(self):
        self.custom_code_list.clear()
        for f in parse_custom_code_functions():
            item = QListWidgetItem(f"Custom: {f['name']}")
            item.setData(Qt.UserRole, f)
            self.custom_code_list.addItem(item)

    def spawn_global_ide(self, elem_id=None, x=None, y=None, initial_code=None, record=True):
        if record: self.record_state()
        if x is None:
            center_pos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            x, y = center_pos.x() + 350, center_pos.y() - 150
        ide = GlobalIDEProxy(self, x, y, elem_id, initial_code)
        
        # ⚠️ FIX: Ye bhi hamesha aage rahega
        ide.setZValue(100)
        
        self.node_scene.addItem(ide)
        self.code_nodes.append(ide)
        self.node_scene.update()
        return ide

    def show_help(self):
        custom_funcs = parse_custom_functions()
        ai_funcs = parse_ai_functions()
        global_funcs = parse_custom_code_functions()
        dlg = HelpDialog(custom_funcs, ai_funcs, global_funcs, self)
        dlg.exec_()

    def show_examples_dialog(self):
        dlg = ExampleTemplatesDialog(self)
        dlg.exec_()

    # 🔥 SMART SEARCH PALETTE TRIGGER
    # 🔥 SMART SEARCH PALETTE TRIGGER (UPDATED)
    def open_search_palette(self):
        items_dict = {}
        
        if self.current_mode == "app_builder":
            # 1. UI Elements
            ui_elems = ["Button", "Label", "Static Text", "Input Field", "Dropdown", "Image", "Console"]
            for e in ui_elems:
                icon = "🔳" if e == "Button" else "📝" if e == "Input Field" else "🔽" if e == "Dropdown" else "💻"
                items_dict[f"{icon} UI Element: {e}"] = {"category": "ui", "val": "Input Text Field" if e == "Input Field" else e}
            
            # 2. Main Panels & IDE
            items_dict["⚙️ Panel: Main Function"] = {"category": "panel", "val": "main_func"}
            items_dict["👑 Panel: Master Pipeline"] = {"category": "panel", "val": "master_pipe"}
            items_dict["🌐 Panel: Global Code IDE"] = {"category": "panel", "val": "global_ide"}
            
            # 3. Logic Loops
            loops = ["Directory Loop", "File Loop", "Smart Filter Loop", "Custom Code Node"]
            for lp in loops:
                items_dict[f"🔄 Loop/Logic: {lp}"] = {"category": "tree_item", "val": lp}
                
            # 4. Backend Functions (AI, Custom, Standard)
            for f in parse_ai_functions():
                items_dict[f"🧠 AI Model: {f['name']}"] = {"category": "tree_func", "type": "AI", "data": f}
            for f in parse_custom_functions():
                items_dict[f"🔧 Standard Func: {f['name']}"] = {"category": "tree_func", "type": "Func", "data": f}
            for f in parse_custom_code_functions():
                items_dict[f"🌐 Custom Code: {f['name']}"] = {"category": "tree_func", "type": "Custom", "data": f}
                
        else:
            # Node Image Edit Mode
            # 1. Canvas Nodes
            canvas_elems = ["List", "Image", "Constructor", "Output Window", "Prompt"]
            for e in canvas_elems:
                items_dict[f"🎴 Canvas Node: {e}"] = {"category": "canvas", "val": e}
            
            # 2. Backend Functions (As Floating Logic Nodes)
            for f in parse_ai_functions():
                items_dict[f"🧠 AI Model: {f['name']}"] = {"category": "logic", "type": "AI", "data": f}
            for f in parse_custom_functions():
                items_dict[f"🔧 Standard Func: {f['name']}"] = {"category": "logic", "type": "Func", "data": f}
            for f in parse_custom_code_functions():
                items_dict[f"🌐 Custom Code: {f['name']}"] = {"category": "logic", "type": "Custom", "data": f}

        # 🔍 Open Search Dialog
        palette = SearchPaletteDialog(items_dict, self)
        main_geometry = self.geometry()
        x = main_geometry.x() + (main_geometry.width() - palette.width()) // 2
        y = main_geometry.y() + (main_geometry.height() - palette.height()) // 2
        palette.move(x, y)
        
        if palette.exec_() == QDialog.Accepted and palette.selected_data:
            sel = palette.selected_data
            scene_pos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            
            if sel["category"] == "ui":
                self.spawn_element_in_app(sel["val"])
                
            elif sel["category"] == "canvas":
                self.spawn_canvas_node(sel["val"])
                
            elif sel["category"] == "logic":
                self.spawn_floating_logic_node(sel["data"], sel["type"], scene_pos.x(), scene_pos.y())
                
            elif sel["category"] == "panel":
                if sel["val"] == "main_func": self.spawn_main_function_node()
                elif sel["val"] == "master_pipe": self.spawn_master_pipeline_node()
                elif sel["val"] == "global_ide": self.spawn_global_ide()
                
            elif sel["category"] in ["tree_item", "tree_func"]:
                # 🔥 SMART FEATURE: Add loop or function directly to the selected Main Function Panel
                if not self.selected_main_func:
                    QMessageBox.warning(self, "No Panel Selected", "Please select a 'Main Function Panel' (Blue Box) first to add logic/loops inside it!")
                    return
                    
                target_tree = self.selected_main_func.tree
                drop_target = self.selected_tree_item if self.selected_tree_item else None
                
                if sel["category"] == "tree_item":
                    text = sel["val"]
                    node_data = {"type": text, "params": {"log_console": True}}
                    
                    if text == "Custom Code Node":
                        c_id = f"code_{uuid.uuid4().hex[:6]}"
                        self.spawn_code_node(elem_id=c_id, x=scene_pos.x() + 100, y=scene_pos.y() - 100, record=True)
                        node_data["params"]["code_node_id"] = c_id
                        node_data["params"]["code_text"] = "None"
                        text = "Func: run_custom_user_code"
                        node_data["type"] = text
                        
                    new_item = QTreeWidgetItem([text])
                    new_item.setData(0, Qt.UserRole, node_data)
                    self.update_tree_title_from_params(new_item, node_data)
                    
                    if drop_target:
                        drop_target.addChild(new_item)
                        drop_target.setExpanded(True)
                    else:
                        target_tree.addTopLevelItem(new_item)
                        
                elif sel["category"] == "tree_func":
                    f_data = sel["data"]
                    text = f"{sel['type']}: {f_data['name']}"
                    params = {arg: "" for arg in f_data.get("args", [])}
                    params["log_console"] = True
                    node_data = {"type": text, "params": params}
                    
                    new_item = QTreeWidgetItem([text])
                    new_item.setData(0, Qt.UserRole, node_data)
                    self.update_tree_title_from_params(new_item, node_data)
                    
                    if drop_target:
                        drop_target.addChild(new_item)
                        drop_target.setExpanded(True)
                    else:
                        target_tree.addTopLevelItem(new_item)
                        
                self.record_state()
                self.node_scene.update()
                
    def load_project_from_dict(self, project_state):
        try:
            geometry = project_state.pop("geometry", None)
            elements = project_state.pop("elements", [])
            main_functions = project_state.pop("main_functions", [])
            master_pipelines = project_state.pop("master_pipelines", [])
            code_nodes_data = project_state.pop("code_nodes", [])
            
            canvas_nodes_data = project_state.pop("canvas_nodes", [])
            canvas_connections_data = project_state.pop("canvas_connections", [])
            
            self.spawn_workspace(project_state, geometry=geometry, elements=elements)
            
            # ⚠️ YEH FIX HUA: Orange (Global) vs Green (Custom) alag-alag khulenge
            for cn_data in code_nodes_data:
                if cn_data.get("type") == "global_ide":
                    cn = self.spawn_global_ide(cn_data["elem_id"], cn_data["x"], cn_data["y"], cn_data.get("code_text"), record=False)
                else:
                    cn = self.spawn_code_node(cn_data["elem_id"], cn_data["x"], cn_data["y"], cn_data.get("code_text"), record=False)
                if cn: cn.widget.resize(cn_data.get("width", 480), cn_data.get("height", 380))
            
            for mf in main_functions:
                self.spawn_main_function_node(
                    x=mf["x"], y=mf["y"], w=mf["width"], h=mf["height"],
                    func_name=mf["func_name"], input_linked_id=mf["input_linked_id"],
                    console_linked_id=mf["console_linked_id"], tree_state=mf["tree_state"], record=False
                )
            for mp in master_pipelines:
                self.spawn_master_pipeline_node(
                    x=mp["x"], y=mp["y"], w=mp["width"], h=mp["height"],
                    func_name=mp["func_name"], input_linked_id=mp["input_linked_id"],
                    console_linked_id=mp["console_linked_id"], sequence=mp.get("sequence", []), record=False
                )

            # Canvas Nodes
            if not hasattr(self, 'canvas_nodes'): self.canvas_nodes = []
            for cdata in canvas_nodes_data:
                ctype = cdata.get("type")
                node = None
                if ctype == "List":
                    node = CanvasListNodeProxy(self, cdata["x"], cdata["y"])
                    node.path_input.setText(cdata.get("path", ""))
                    node.ext_combo.setCurrentText(cdata.get("ext", ".*"))
                    if cdata.get("path"): node.load_directory()
                elif ctype == "Image":
                    node = CanvasImageNodeProxy(self, cdata["x"], cdata["y"])
                    node.file_path = cdata.get("file_path", "")
                    if node.file_path: node.load_image()
                elif ctype == "Constructor":
                    node = CanvasConstructorNodeProxy(self, cdata["x"], cdata["y"])
                elif ctype == "Output Window":
                    node = CanvasOutputNodeProxy(self, cdata["x"], cdata["y"])
                elif ctype == "FloatingFunc":
                    node = CanvasFloatingFuncProxy(self, cdata.get("func_data", {}), cdata.get("ntype", "Func"), cdata["x"], cdata["y"])
                    for k, v in cdata.get("params", {}).items():
                        if k in node.param_inputs: node.param_inputs[k].setText(v)
                        
                if node:
                    node.elem_id = cdata.get("elem_id", node.elem_id)
                    node.widget.resize(cdata.get("width", node.widget.width()), cdata.get("height", node.widget.height()))
                    self.node_scene.addItem(node)
                    self.canvas_nodes.append(node)
            
            # Wires Restore
            if not hasattr(self, 'canvas_connections'): self.canvas_connections = []
            for conn in canvas_connections_data:
                out_n = next((n for n in self.canvas_nodes if n.elem_id == conn["out_node"]), None)
                in_n = next((n for n in self.canvas_nodes if n.elem_id == conn["in_node"]), None)
                if out_n and in_n:
                    def get_port(n, role, is_out):
                        for attr in dir(n):
                            val = getattr(n, attr)
                            if isinstance(val, PortItem) and val.role == role and val.is_out == is_out: return val
                        return None
                    p1 = get_port(out_n, conn["out_role"], True)
                    p2 = get_port(in_n, conn["in_role"], False)
                    if p1 and p2: self.canvas_connections.append((p1, p2))

            self.node_scene.update()
            
            # Reset Mod Status
            if getattr(self, 'current_tab_id', -1) != -1:
                self.projects_data[self.current_tab_id]["is_modified"] = False
            self.is_modified = False
            idx = self.tab_bar.currentIndex()
            if idx >= 0:
                current_text = self.tab_bar.tabText(idx)
                self.tab_bar.setTabText(idx, current_text.replace("*", ""))
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{str(e)}")

    def copy_selection(self):
        if self.selected_main_func:
            self.clipboard_data = {
                "type": "main_func",
                "func_name": self.selected_main_func.func_name + "_copy",
                "input_linked_id": "None", 
                "console_linked_id": "None",
                "w": self.selected_main_func.widget.width(),
                "h": self.selected_main_func.widget.height(),
                "tree_state": self.selected_main_func.extract_tree_state()
            }
            self.statusBar().showMessage(f"Copied Function: {self.selected_main_func.func_name}", 2000)
        elif self.selected_master_pipe:
            self.clipboard_data = {
                "type": "master_pipe",
                "func_name": self.selected_master_pipe.func_name + "_copy",
                "input_linked_id": "None",
                "console_linked_id": "None",
                "w": self.selected_master_pipe.widget.width(),
                "h": self.selected_master_pipe.widget.height(),
                "sequence": self.selected_master_pipe.get_sequence()
            }
            self.statusBar().showMessage(f"Copied Master Pipeline: {self.selected_master_pipe.func_name}", 2000)
        elif self.selected_elements:
            el = self.selected_elements[0]
            inner = el.inner_widget.geometry()
            self.clipboard_data = {
                "type": "element",
                "elem_type": el.elem_type,
                "text": el.get_text() + " (Copy)",
                "w": inner.width(),
                "h": inner.height(),
                "bg_color": el.bg_color,
                "has_fill": el.has_fill,
                "text_color": el.text_color,
                "radius": el.radius,
                "border_width": el.border_width,
                "border_color": el.border_color,
                "shape": el.shape,
                "image_path": el.image_path,
                "font_size": el.font_size,
                "alignment": el.alignment,
                "dropdown_options": el.dropdown_options
            }
            self.statusBar().showMessage(f"Copied UI Element: {el.elem_type}", 2000)

    def paste_selection(self):
        if not self.clipboard_data or not self.current_project:
            return
            
        cpos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
        
        if self.clipboard_data["type"] == "main_func":
            new_state = json.loads(json.dumps(self.clipboard_data["tree_state"]))
            loop_map = {}
            def map_loops(n_list):
                for n in n_list:
                    if n["node_data"]["type"] in ["Directory Loop", "File Loop", "Smart Filter Loop"]:
                        old_nm = n["node_data"]["params"].get("loop_name", "")
                        if old_nm:
                            new_nm = f"{old_nm}_{uuid.uuid4().hex[:3]}"
                            loop_map[old_nm] = new_nm
                            n["node_data"]["params"]["loop_name"] = new_nm
                    if n.get("children"):
                        map_loops(n["children"])
            map_loops(new_state)
            
            def update_refs(n_list):
                for n in n_list:
                    params = n["node_data"]["params"]
                    for k, v in params.items():
                        if isinstance(v, str):
                            for old_nm, new_nm in loop_map.items():
                                if v == old_nm:
                                    params[k] = new_nm
                                elif old_nm in v:
                                    params[k] = v.replace(old_nm, new_nm)
                    if n.get("children"):
                        update_refs(n["children"])
            update_refs(new_state)

            self.spawn_main_function_node(
                x=cpos.x() - 150 + random.randint(-40, 40), 
                y=cpos.y() - 200 + random.randint(-40, 40),
                w=self.clipboard_data["w"], 
                h=self.clipboard_data["h"],
                func_name=self.clipboard_data["func_name"],
                input_linked_id="None",
                console_linked_id="None",
                tree_state=new_state
            )
            self.clipboard_data["func_name"] += "_cp"

        elif self.clipboard_data["type"] == "master_pipe":
            self.spawn_master_pipeline_node(
                x=cpos.x() - 125 + random.randint(-40, 40), 
                y=cpos.y() - 150 + random.randint(-40, 40),
                w=self.clipboard_data["w"], 
                h=self.clipboard_data["h"],
                func_name=self.clipboard_data["func_name"],
                input_linked_id="None",
                console_linked_id="None",
                sequence=self.clipboard_data["sequence"]
            )
            self.clipboard_data["func_name"] += "_cp"
            
        elif self.clipboard_data["type"] == "element":
            self.spawn_element_in_app(
                elem_type=self.clipboard_data["elem_type"],
                text=self.clipboard_data["text"],
                x=30 + random.randint(10, 50), 
                y=30 + random.randint(10, 50),
                w=self.clipboard_data["w"], 
                h=self.clipboard_data["h"],
                bg_color=self.clipboard_data["bg_color"],
                has_fill=self.clipboard_data["has_fill"],
                text_color=self.clipboard_data["text_color"],
                radius=self.clipboard_data["radius"],
                border_width=self.clipboard_data["border_width"],
                border_color=self.clipboard_data["border_color"],
                image_path=self.clipboard_data["image_path"],
                shape=self.clipboard_data["shape"],
                font_size=self.clipboard_data["font_size"],
                alignment=self.clipboard_data["alignment"],
                dropdown_options=self.clipboard_data.get("dropdown_options", "Option 1, Option 2")
            )

    def update_master_combos(self):
        func_names = [mf.func_name for mf in self.main_function_nodes]
        for mp in self.master_pipeline_nodes:
            current_sel = mp.combo_funcs.currentText()
            mp.combo_funcs.clear()
            mp.combo_funcs.addItems(func_names)
            if current_sel in func_names:
                mp.combo_funcs.setCurrentText(current_sel)

    def make_connection(self, port1, port2):
        if port1.is_out == port2.is_out: return
        out_port = port1 if port1.is_out else port2
        in_port = port2 if not port2.is_out else port1
        
        # ⚠️ NAYA LOGIC: ComfyUI Nodes ki universal wire mapping
        if out_port.parent_node in getattr(self, 'canvas_nodes', []) or in_port.parent_node in getattr(self, 'canvas_nodes', []):
            if not hasattr(self, 'canvas_connections'): self.canvas_connections = []
            self.canvas_connections = [c for c in self.canvas_connections if c[1] != in_port]
            self.canvas_connections.append((out_port, in_port))
            self.record_state() # ⚠️ NAYA: Taaki connection history me save ho jaye
            self.node_scene.update()
            return

        if out_port.role == 'btn_out' and in_port.role == 'trigger_in':
            out_port.parent_node.element_ref.button_action = in_port.parent_node.func_name
        elif out_port.role in ['text_out', 'dir_out'] and in_port.role == 'dir_in':
            out_id = out_port.parent_node.element_ref.elem_id if hasattr(out_port.parent_node, 'element_ref') else out_port.parent_node.elem_id
            in_port.parent_node.input_linked_id = out_id
        elif out_port.role == 'console_out' and in_port.role == 'console_in':
            out_id = out_port.parent_node.element_ref.elem_id if hasattr(out_port.parent_node, 'element_ref') else out_port.parent_node.elem_id
            in_port.parent_node.console_linked_id = out_id
        elif out_port.role == 'text_out' and in_port.role == 'btn_in':
            out_port.parent_node.element_ref.connected_button_id = in_port.parent_node.element_ref.elem_id
            
        self.record_state()
        self.update_property_panel()

    def break_connection_at_input(self, in_port):
        # ⚠️ ComfyUI Node wire breaking (Input side)
        if in_port.parent_node in getattr(self, 'canvas_nodes', []):
            if hasattr(self, 'canvas_connections'):
                self.canvas_connections = [c for c in self.canvas_connections if c[1] != in_port]
            self.node_scene.update()
            return
            
        if in_port.role == 'trigger_in':
            for en in self.element_nodes:
                if en.element_ref.elem_type == "Button" and en.element_ref.button_action == in_port.parent_node.func_name:
                    en.element_ref.button_action = "None"
        elif in_port.role == 'dir_in':
            in_port.parent_node.input_linked_id = "None"
        elif in_port.role == 'console_in':
            for mf in self.main_function_nodes + self.master_pipeline_nodes:
                if mf.console_linked_id == in_port.parent_node.element_ref.elem_id:
                    mf.console_linked_id = "None"
        elif in_port.role == 'btn_in':
            for en in self.element_nodes:
                if en.element_ref.elem_type in ["Input Text Field", "Dropdown"] and en.element_ref.connected_button_id == in_port.parent_node.element_ref.elem_id:
                    en.element_ref.connected_button_id = "None"
                    
        self.record_state()
        self.update_property_panel()

    def break_connection(self, port):
        if not port.is_out:
            self.break_connection_at_input(port)
        else:
            # ⚠️ ComfyUI Node wire breaking (Output side)
            if port.parent_node in getattr(self, 'canvas_nodes', []):
                if hasattr(self, 'canvas_connections'):
                    self.canvas_connections = [c for c in self.canvas_connections if c[0] != port]
                self.node_scene.update()
                return

            out_id = port.parent_node.element_ref.elem_id if hasattr(port.parent_node, 'element_ref') else port.parent_node.elem_id
            
            if port.role == 'btn_out':
                port.parent_node.element_ref.button_action = "None"
            elif port.role in ['text_out', 'dir_out']:
                for mf in self.main_function_nodes + self.master_pipeline_nodes:
                    if mf.input_linked_id == out_id:
                        mf.input_linked_id = "None"
                if port.role == 'text_out':
                    for en in self.element_nodes:
                        if port.parent_node.element_ref.connected_button_id == en.element_ref.elem_id:
                            port.parent_node.element_ref.connected_button_id = "None"
            elif port.role == 'console_out':
                port.parent_node.console_linked_id = "None"
        self.record_state()
        self.update_property_panel()

    def record_state(self):
        if getattr(self, 'is_internal_change', False): return
        
        if getattr(self, 'current_mode', 'app_builder') != "node_editor" and not self.current_project: 
            return
            
        state = {}
        if self.current_project:
            state = self.current_project.get_project_state()
            for el_state in state.get("elements", []):
                for en in self.element_nodes:
                    if en.element_ref.elem_id == el_state["elem_id"]:
                        el_state["node_x"] = en.pos().x()
                        el_state["node_y"] = en.pos().y()
        else:
            idx = self.tab_bar.currentIndex()
            tab_name = self.tab_bar.tabText(idx).split(" [")[0].replace("*", "") if idx >= 0 else "Node_Project"
            state = {"app_name": tab_name, "project_mode": "node_editor", "elements": []}

        state["main_functions"] = [{"func_name": mf.func_name, "input_linked_id": mf.input_linked_id, "console_linked_id": mf.console_linked_id, "x": mf.pos().x(), "y": mf.pos().y(), "width": mf.widget.width(), "height": mf.widget.height(), "tree_state": mf.extract_tree_state()} for mf in self.main_function_nodes]
        state["master_pipelines"] = [{"func_name": mp.func_name, "input_linked_id": mp.input_linked_id, "console_linked_id": mp.console_linked_id, "x": mp.pos().x(), "y": mp.pos().y(), "width": mp.widget.width(), "height": mp.widget.height(), "sequence": mp.get_sequence()} for mp in self.master_pipeline_nodes]
        
        # ⚠️ YEH FIX HUA: Ab ye yaad rakhega ki Global IDE hai ya Custom Code Node
        state["code_nodes"] = [
            {"type": "global_ide" if isinstance(cn, GlobalIDEProxy) else "code_node", "elem_id": cn.elem_id, "x": cn.pos().x(), "y": cn.pos().y(), "width": cn.widget.width(), "height": cn.widget.height(), "code_text": cn.editor.toPlainText()} 
            for cn in self.code_nodes
        ]
            
        if self.undo_stack and self.undo_stack[-1] == state: return
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_undo_steps: self.undo_stack.pop(0)
        if hasattr(self, 'btn_undo'): self.btn_undo.setEnabled(True)
        
        self.is_modified = True
        if getattr(self, 'current_tab_id', -1) != -1 and self.current_tab_id in getattr(self, 'projects_data', {}):
            self.projects_data[self.current_tab_id]["is_modified"] = True
            
        # ⚠️ TAB PE '*' LAGANA (Unsaved indicator)
        idx = self.tab_bar.currentIndex()
        if idx >= 0:
            current_text = self.tab_bar.tabText(idx)
            if not current_text.startswith("*"):
                self.tab_bar.setTabText(idx, "*" + current_text)
        

    def perform_undo(self):
        if not self.undo_stack or not self.current_project: return
        state = self.undo_stack.pop()
        previous_state = state if not self.undo_stack else self.undo_stack[-1]

        self.is_internal_change = True
        for child in self.current_project.app_body.findChildren(MovableElement): child.deleteLater()
        for mf in self.main_function_nodes: self.node_scene.removeItem(mf)
        for mp in self.master_pipeline_nodes: self.node_scene.removeItem(mp)
        for en in self.element_nodes: self.node_scene.removeItem(en)
        for cn in self.code_nodes: self.node_scene.removeItem(cn)
        
        self.main_function_nodes.clear()
        self.master_pipeline_nodes.clear()
        self.element_nodes.clear()
        self.code_nodes.clear()
        self.handle_canvas_click_deselect()

        geometry = previous_state.get("geometry", None)
        if geometry:
            self.current_project.setPos(geometry["x"], geometry["y"])
            self.current_project.window_widget.resize(geometry["width"], geometry["height"])
            
        for el in previous_state.get("elements", []):
            self.spawn_element_in_app(
                elem_type=el["type"], text=el["text"], x=el["x"], y=el["y"], w=el["width"], h=el["height"],
                bg_color=el.get("bg_color", "#007acc"), has_fill=el.get("has_fill", True), text_color=el.get("text_color", "#ffffff"),
                radius=el.get("radius", 4), border_width=el.get("border_width", 1), border_color=el.get("border_color", "#555555"),
                image_path=el.get("image_path", ""), shape=el.get("shape", "Rectangle"), font_size=el.get("font_size", 12),
                alignment=el.get("alignment", "Center"), elem_id=el.get("elem_id"), button_action=el.get("button_action", "None"),
                connected_button_id=el.get("connected_button_id", "None"), dropdown_options=el.get("dropdown_options", "Option 1, Option 2"),
                record=False, force_single=False, node_x=el.get("node_x"), node_y=el.get("node_y")
            )

        for mf_data in previous_state.get("main_functions", []):
            self.spawn_main_function_node(
                x=mf_data["x"], y=mf_data["y"], w=mf_data["width"], h=mf_data["height"],
                func_name=mf_data["func_name"], input_linked_id=mf_data["input_linked_id"],
                console_linked_id=mf_data["console_linked_id"], tree_state=mf_data["tree_state"], record=False
            )
            
        for mp_data in previous_state.get("master_pipelines", []):
            self.spawn_master_pipeline_node(
                x=mp_data["x"], y=mp_data["y"], w=mp_data["width"], h=mp_data["height"],
                func_name=mp_data["func_name"], input_linked_id=mp_data["input_linked_id"],
                console_linked_id=mp_data["console_linked_id"], sequence=mp_data.get("sequence", []), record=False
            )
            
        for cn_data in previous_state.get("code_nodes", []):
            if cn_data.get("type") == "global_ide":
                cn = self.spawn_global_ide(cn_data["elem_id"], cn_data["x"], cn_data["y"], cn_data.get("code_text"), record=False)
            else:
                cn = self.spawn_code_node(cn_data["elem_id"], cn_data["x"], cn_data["y"], cn_data.get("code_text"), record=False)
            if cn: cn.widget.resize(cn_data.get("width", 480), cn_data.get("height", 380))

        self.is_internal_change = False
        if not self.undo_stack: self.btn_undo.setEnabled(False)
        self.update_master_combos()
        self.node_scene.update()

    def spawn_element_in_app(self, elem_type, text="Sample Text", x=30, y=30, w=140, h=40, 
                             bg_color="#007acc", has_fill=True, text_color="#ffffff", radius=4, border_width=1, border_color="#555555", 
                             image_path="", shape="Rectangle", font_size=12, alignment="Center", 
                             elem_id=None, button_action="None", connected_button_id="None", dropdown_options="Option 1, Option 2", 
                             record=True, force_single=True, node_x=None, node_y=None):
        if not self.current_project: return
        if record: self.record_state()
        if elem_type == "Image" and text == "Sample Text": text = "No Image"
        if elem_type == "Console": text = ""
            
        element = MovableElement(
            parent=self.current_project.app_body, elem_type=elem_type, select_callback=self.handle_element_selection, change_callback=self.record_state,
            text=text, x=x, y=y, w=w, h=h, bg_color=bg_color, has_fill=has_fill, text_color=text_color, radius=radius,
            border_width=border_width, border_color=border_color, image_path=image_path, shape=shape,
            font_size=font_size, alignment=alignment, elem_id=elem_id, button_action=button_action, connected_button_id=connected_button_id,
            dropdown_options=dropdown_options
        )
        element.show()
        
        if elem_type in ["Button", "Input Text Field", "Console", "Dropdown"]:
            enode = ElementNodeView(element, self)
            if node_x is not None and node_y is not None:
                enode.setPos(node_x, node_y)
            else:
                cpos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
                enode.setPos(cpos.x() - 300, cpos.y() + len(self.element_nodes)*60)
            self.node_scene.addItem(enode)
            self.element_nodes.append(enode)
            
        if force_single: self.handle_element_selection(element, is_shift=False, was_already_selected=False, force_single=True)
        self.node_scene.update()

    def spawn_code_node(self, elem_id=None, x=None, y=None, initial_code=None, record=True):
        if record: self.record_state()
        if x is None:
            center_pos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            x, y = center_pos.x() + 200, center_pos.y()
            
        cn = CodeNodeProxy(self, x, y, elem_id, initial_code)
        cn.setZValue(100)
        self.node_scene.addItem(cn)
        self.code_nodes.append(cn)
        self.node_scene.update()
        return cn

    def spawn_main_function_node(self, x=None, y=None, w=300, h=400, func_name=None, input_linked_id="None", console_linked_id="None", tree_state=None, record=True):
        if not self.current_project: return
        if record: self.record_state()
        if x is None or not isinstance(x, (int, float)):
            center_pos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            x, y = center_pos.x() - 150, center_pos.y() - 200
            
        func_name = func_name or f"my_function_{len(self.main_function_nodes)+1}"
        mf = MainFunctionProxy(self, x, y, func_name, input_linked_id, console_linked_id, tree_state)
        mf.widget.resize(w, h)
        self.node_scene.addItem(mf)
        self.main_function_nodes.append(mf)
        self.update_master_combos()
        self.handle_main_func_selection(mf)
        self.node_scene.update()

    def spawn_master_pipeline_node(self, x=None, y=None, w=250, h=300, func_name=None, input_linked_id="None", console_linked_id="None", sequence=None, record=True):
        if not self.current_project: return
        if record: self.record_state()
        if x is None or not isinstance(x, (int, float)):
            center_pos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            x, y = center_pos.x() + 200, center_pos.y() - 150
            
        func_name = func_name or f"Master_Pipeline_{len(self.master_pipeline_nodes)+1}"
        mp = MasterPipelineProxy(self, x, y, func_name, input_linked_id, console_linked_id, sequence)
        mp.widget.resize(w, h)
        self.node_scene.addItem(mp)
        self.master_pipeline_nodes.append(mp)
        self.handle_master_func_selection(mp)
        self.node_scene.update()

    def handle_element_selection(self, element, is_shift=False, was_already_selected=False, force_single=False):
        if self.selected_main_func: self.selected_main_func.set_selected(False); self.selected_main_func = None
        if self.selected_master_pipe: self.selected_master_pipe.set_selected(False); self.selected_master_pipe = None
        if self.selected_code_node: self.selected_code_node.set_selected(False); self.selected_code_node = None
        self.selected_tree_item = None

        if force_single:
            for el in self.selected_elements:
                if el != element: el.set_selected(False)
            self.selected_elements = [element]
            element.set_selected(True)
        elif is_shift:
            if was_already_selected:
                element.set_selected(False)
                if element in self.selected_elements: self.selected_elements.remove(element)
            else:
                element.set_selected(True)
                if element not in self.selected_elements: self.selected_elements.append(element)
        else:
            if not was_already_selected:
                for el in self.selected_elements:
                    if el != element: el.set_selected(False)
                self.selected_elements = [element]
                element.set_selected(True)
        self.update_property_panel()
        self.node_scene.update()

    def handle_main_func_selection(self, mf_node):
        for el in self.selected_elements: el.set_selected(False)
        self.selected_elements.clear()
        if self.selected_master_pipe: self.selected_master_pipe.set_selected(False); self.selected_master_pipe = None
        if self.selected_code_node: self.selected_code_node.set_selected(False); self.selected_code_node = None
        if self.selected_main_func and self.selected_main_func != mf_node: self.selected_main_func.set_selected(False)
        self.selected_main_func = mf_node; self.selected_tree_item = None
        mf_node.set_selected(True)
        self.update_property_panel()

    def handle_master_func_selection(self, mp_node):
        for el in self.selected_elements: el.set_selected(False)
        self.selected_elements.clear()
        if self.selected_main_func: self.selected_main_func.set_selected(False); self.selected_main_func = None
        if self.selected_code_node: self.selected_code_node.set_selected(False); self.selected_code_node = None
        if self.selected_master_pipe and self.selected_master_pipe != mp_node: self.selected_master_pipe.set_selected(False)
        self.selected_master_pipe = mp_node; self.selected_tree_item = None
        mp_node.set_selected(True)
        self.update_property_panel()
        
    def handle_code_node_selection(self, cn_node):
        for el in self.selected_elements: el.set_selected(False)
        self.selected_elements.clear()
        if self.selected_main_func: self.selected_main_func.set_selected(False); self.selected_main_func = None
        if self.selected_master_pipe: self.selected_master_pipe.set_selected(False); self.selected_master_pipe = None
        if self.selected_code_node and self.selected_code_node != cn_node: self.selected_code_node.set_selected(False)
        self.selected_code_node = cn_node; self.selected_tree_item = None
        cn_node.set_selected(True)
        self.update_property_panel()

    def handle_tree_item_selection(self, item):
        for el in self.selected_elements: el.set_selected(False)
        self.selected_elements.clear()
        if self.selected_code_node: self.selected_code_node.set_selected(False); self.selected_code_node = None
        self.selected_tree_item = item
        self.update_property_panel()

    def handle_box_selection(self, rect, is_shift=False):
        if not self.current_project: return
        if not is_shift:
            for el in self.selected_elements: el.set_selected(False)
            self.selected_elements.clear()
            if self.selected_main_func: self.selected_main_func.set_selected(False); self.selected_main_func = None
            if self.selected_master_pipe: self.selected_master_pipe.set_selected(False); self.selected_master_pipe = None
            if self.selected_code_node: self.selected_code_node.set_selected(False); self.selected_code_node = None

        for child in self.current_project.app_body.findChildren(MovableElement):
            child_global_rect = child.geometry()
            if rect.intersects(QRectF(child_global_rect)):
                if not child.is_selected:
                    child.set_selected(True)
                    self.selected_elements.append(child)
        self.update_property_panel()
        self.node_scene.update()

    def update_tree_title_from_params(self, item, data):
        lname = data['params'].get('loop_name', '')
        tgt = data['params'].get('target_dir', 'current_dir')
        if tgt == "current_dir": tgt_str = "Auto-Parent"
        elif tgt == "dir_root": tgt_str = "Main Input"
        else: tgt_str = tgt

        node_type = data.get("type", "")
        if node_type in ["Directory Loop", "Smart Filter Loop"]:
            prefix = "Dir Loop" if node_type == "Directory Loop" else "Smart Loop"
            item.setText(0, f"{prefix}: {lname} (<- {tgt_str})")
        elif node_type == "File Loop":
            item.setText(0, f"File Loop: {lname} [{data['params'].get('ext', '*.*')}] (<- {tgt_str})")

    def update_property_panel(self):
        def clear_layout(layout):
            if layout is not None:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                    elif child.layout():
                        clear_layout(child.layout())
                        child.layout().deleteLater()

        clear_layout(self.property_container_layout)

        all_dir_loops = []
        all_file_loops = []
        if self.selected_main_func:
            def extract_loops(item_node):
                count = item_node.childCount()
                for i in range(count):
                    child = item_node.child(i)
                    node_d = child.data(0, Qt.UserRole)
                    if node_d["type"] in ["Directory Loop", "Smart Filter Loop"]:
                        nm = node_d.get("params", {}).get("loop_name")
                        if nm: all_dir_loops.append(nm)
                    elif node_d["type"] == "File Loop":
                        nm = node_d.get("params", {}).get("loop_name")
                        if nm: all_file_loops.append(nm)
                    extract_loops(child)
            
            tree_root = self.selected_main_func.tree.invisibleRootItem()
            if tree_root.childCount() > 0:
                extract_loops(tree_root)

        # --- CODE NODE PROPERTIES ---
        if self.selected_code_node:
            cn = self.selected_code_node
            self.property_container_layout.addWidget(QLabel("<b>📝 Custom Code Node Panel</b>"))
            self.property_container_layout.addWidget(QLabel("<i>Write your code directly inside the floating node on the canvas.</i>"))
            btn_del = QPushButton("🗑️ Delete Code Node"); btn_del.setStyleSheet("background-color: #dc3545; color: white; margin-top: 20px;")
            
            def del_cn():
                # Also delete from tree
                for mf in self.main_function_nodes:
                    tree_root = mf.tree.invisibleRootItem()
                    def search_tree(parent_item):
                        for i in range(parent_item.childCount()):
                            child = parent_item.child(i)
                            node_d = child.data(0, Qt.UserRole)
                            if node_d.get("params", {}).get("code_node_id") == cn.elem_id:
                                return child
                            found = search_tree(child)
                            if found: return found
                        return None
                    
                    found_item = search_tree(tree_root)
                    if found_item:
                        p = found_item.parent()
                        if p: p.removeChild(found_item)
                        else: mf.tree.takeTopLevelItem(mf.tree.indexOfTopLevelItem(found_item))
                
                self.node_scene.removeItem(cn)
                if cn in self.code_nodes: self.code_nodes.remove(cn)
                self.selected_code_node = None
                self.update_property_panel()
                self.node_scene.update()
                
            btn_del.clicked.connect(del_cn)
            self.property_container_layout.addWidget(btn_del)
            self.property_container_layout.addStretch()
            return

        if self.selected_tree_item:
            item = self.selected_tree_item
            data = item.data(0, Qt.UserRole)
            self.property_container_layout.addWidget(QLabel(f"<b>Node: {data['type']}</b>"))
            
            inputs_map = {}
            
            def apply_updates_silent(*args):
                for param_key, widget_ref in inputs_map.items():
                    if isinstance(widget_ref, QSpinBox):
                        data["params"][param_key] = widget_ref.value()
                    elif isinstance(widget_ref, QLineEdit):
                        data["params"][param_key] = widget_ref.text()
                    elif isinstance(widget_ref, QCheckBox):
                        data["params"][param_key] = widget_ref.isChecked()
                    elif isinstance(widget_ref, QComboBox):
                        data["params"][param_key] = widget_ref.currentText()
                item.setData(0, Qt.UserRole, data)
                self.update_tree_title_from_params(item, data)
                self.node_scene.update()

            if data["type"] in ["Directory Loop", "File Loop", "Smart Filter Loop"]:
                layout_name = QHBoxLayout()
                layout_name.addWidget(QLabel("Loop Name:"))
                name_in = QLineEdit(str(data["params"].get("loop_name", "")))
                name_in.editingFinished.connect(apply_updates_silent)
                layout_name.addWidget(name_in)
                self.property_container_layout.addLayout(layout_name)
                inputs_map["loop_name"] = name_in

                layout_tgt = QHBoxLayout()
                layout_tgt.addWidget(QLabel("Target Directory:"))
                target_in = QLineEdit(str(data["params"].get("target_dir", "current_dir")))
                target_in.editingFinished.connect(apply_updates_silent)
                layout_tgt.addWidget(target_in)
                
                conn_combo = QComboBox()
                conn_combo.addItem("Auto (Parent Dir)", "current_dir")
                conn_combo.addItem("Main Input (Root)", "dir_root")
                for l_name in all_dir_loops:
                    if l_name != data["params"].get("loop_name"):
                        conn_combo.addItem(f"Dir Loop: {l_name}", l_name)
                conn_combo.addItem("Browse Folder...", "BROWSE_DIR")
                
                for el in self.current_project.app_body.findChildren(MovableElement):
                    if el.elem_type in ["Input Text Field", "Dropdown"]:
                        lbl_type = "Input" if el.elem_type == "Input Text Field" else "Dropdown"
                        acc_meth = "text()" if el.elem_type == "Input Text Field" else "currentText()"
                        conn_combo.addItem(f"UI {lbl_type}: {el.get_text()[:10]}", f"self.{el.elem_id}.{acc_meth}.strip()")
                for mp in self.master_pipeline_nodes:
                    conn_combo.addItem(f"Master: {mp.func_name}", mp.elem_id)
                        
                layout_tgt.addWidget(conn_combo)
                self.property_container_layout.addLayout(layout_tgt)
                inputs_map["target_dir"] = target_in
                
                current_val = str(data["params"].get("target_dir", "current_dir"))
                idx_found = False
                for ci in range(conn_combo.count()):
                    if conn_combo.itemData(ci) == current_val:
                        conn_combo.setCurrentIndex(ci)
                        idx_found = True
                        break
                
                def on_tgt_changed(idx, combo=conn_combo, field=target_in):
                    val = combo.currentData()
                    if val == "BROWSE_DIR":
                        path = QFileDialog.getExistingDirectory(self, "Select Target Directory")
                        if path: field.setText(path)
                        combo.setCurrentIndex(0)
                    else:
                        field.setText(val)
                    apply_updates_silent()
                conn_combo.currentIndexChanged.connect(on_tgt_changed)

                if data["type"] == "Smart Filter Loop":
                    layout_type = QHBoxLayout()
                    layout_type.addWidget(QLabel("Target Type:"))
                    combo_type = QComboBox()
                    combo_type.addItems(["Files", "Directories", "Both"])
                    combo_type.setCurrentText(str(data["params"].get("target_type", "Files")))
                    combo_type.currentIndexChanged.connect(apply_updates_silent)
                    layout_type.addWidget(combo_type)
                    self.property_container_layout.addLayout(layout_type)
                    inputs_map["target_type"] = combo_type

                if data["type"] in ["File Loop", "Smart Filter Loop"]:
                    layout_ext = QHBoxLayout()
                    layout_ext.addWidget(QLabel("Extensions (e.g. png, jpg):"))
                    ext_in = QLineEdit(str(data["params"].get("ext_filter", data["params"].get("ext", "*.*"))))
                    ext_in.editingFinished.connect(apply_updates_silent)
                    layout_ext.addWidget(ext_in)
                    self.property_container_layout.addLayout(layout_ext)
                    if data["type"] == "File Loop":
                        inputs_map["ext"] = ext_in
                    else:
                        inputs_map["ext_filter"] = ext_in

                if data["type"] in ["Directory Loop", "File Loop", "Smart Filter Loop"]:
                    layout_exclude = QHBoxLayout()
                    layout_exclude.addWidget(QLabel("Exclude Name Contains:"))
                    exclude_in = QLineEdit(str(data["params"].get("exclude_contains", "")))
                    exclude_in.setPlaceholderText("e.g. system, thumb, .ini")
                    exclude_in.editingFinished.connect(apply_updates_silent)
                    layout_exclude.addWidget(exclude_in)
                    self.property_container_layout.addLayout(layout_exclude)
                    inputs_map["exclude_contains"] = exclude_in

                if data["type"] == "Smart Filter Loop":
                    layout_exact = QHBoxLayout()
                    layout_exact.addWidget(QLabel("Exact Name:"))
                    exact_in = QLineEdit(str(data["params"].get("name_exact", "")))
                    exact_in.editingFinished.connect(apply_updates_silent)
                    layout_exact.addWidget(exact_in)
                    self.property_container_layout.addLayout(layout_exact)
                    inputs_map["name_exact"] = exact_in

                    layout_cont = QHBoxLayout()
                    layout_cont.addWidget(QLabel("Name Contains:"))
                    cont_in = QLineEdit(str(data["params"].get("name_contains", "")))
                    cont_in.editingFinished.connect(apply_updates_silent)
                    layout_cont.addWidget(cont_in)
                    self.property_container_layout.addLayout(layout_cont)
                    inputs_map["name_contains"] = cont_in

            elif data["type"].startswith("Func:") or data["type"].startswith("AI:") or data["type"].startswith("Custom:"):
                is_ai = data["type"].startswith("AI:")
                is_custom = data["type"].startswith("Custom:")
                func_n = data["type"].split(": ")[1]
                
                # --- AI NODE VISUALS ---
                if is_ai:
                    lbl = QLabel(f"🧠 AI Model Configuration")
                    lbl.setStyleSheet("color: #e91e63; font-weight:bold; font-size: 13px; margin-bottom: 2px;")
                    self.property_container_layout.addWidget(lbl)
                    
                    warn_lbl = QLabel(
                        "⚠️ <b>System Requirements / सिस्टम आवश्यकताएँ:</b><br>"
                        "<span style='font-size: 10px;'>"
                        "<b>[EN]</b> AI models consume heavy GPU (Nvidia CUDA) and RAM. If your PC lacks a dedicated graphics card, please process a <b>Single File</b> at a time. Run <b>Bulk / Folder Loops</b> only if you have a strong system configuration, otherwise your system may freeze/crash.<br><br>"
                        "<b>[HI]</b> AI models processing ke liye heavy GPU aur RAM use karte hain. Agar aapke PC mein heavy graphics card nahi hai, toh kripya ise sirf <b>Single File</b> par hi chalayein. Strong configuration hone par hi <b>Bulk / Folder Loop</b> use karein, warna system hang ho sakta hai."
                        "</span>"
                    )
                    warn_lbl.setWordWrap(True)
                    warn_lbl.setStyleSheet("color: #ffb300; background-color: #3e2723; padding: 6px; border-radius: 4px; border: 1px solid #ff9800; margin-bottom: 8px; line-height: 1.2;")
                    self.property_container_layout.addWidget(warn_lbl)
                
                # --- CODE NODE PROPERTIES ---
                if func_n == "run_custom_user_code":
                    c_id = data["params"].get("code_node_id")
                    lbl = QLabel(f"🔗 Linked to Canvas Node:<br><b>{c_id}</b>")
                    lbl.setStyleSheet("color: #a5d6a7; padding: 10px; border: 1px solid #555; background: #1e1e1e; border-radius: 4px; margin-top: 10px;")
                    self.property_container_layout.addWidget(lbl)
                    
                    btn_del = QPushButton("🗑️ Delete Node Link"); btn_del.setStyleSheet("background-color: #dc3545; color: white;")
                    btn_del.clicked.connect(lambda _, i=item: self.delete_tree_item(i))
                    self.property_container_layout.addWidget(btn_del)
                    self.property_container_layout.addStretch()
                    return
                # ----------------------------
                
                self.property_container_layout.addWidget(QLabel("<b>Function Parameters:</b>"))
                for arg in data["params"].keys():
                    if arg == "log_console" or arg.lower() == "root_dir" or arg == "code_node_id": continue
                    arg_lower = arg.lower()

                    is_bool_param = isinstance(data["params"][arg], bool) or arg_lower in ['preserve_tree', 'preserve', 'generate_mask', 'generate', 'ignore_case', 'save_mask_only'] or arg_lower.startswith('extract_')
                    if is_bool_param:
                        chk = QCheckBox(f"Enable {arg.replace('_', ' ').title()}")
                        curr_val = data["params"][arg]
                        if isinstance(curr_val, str):
                            is_checked = (curr_val.lower() == 'true')
                        else:
                            is_checked = bool(curr_val)
                        chk.setChecked(is_checked)
                        chk.setStyleSheet("color: #4caf50; font-weight: bold; margin-bottom: 8px;")
                        chk.stateChanged.connect(apply_updates_silent)
                        self.property_container_layout.addWidget(chk)
                        inputs_map[arg] = chk
                        continue
                    
                    is_path_param = any(x in arg_lower for x in ['path', 'dir', 'file', 'src', 'dst', 'source', 'dest', 'folder', 'output', 'root', 'input'])
                    
                    is_dynamic_builder = arg_lower in ["new_name", "mask_image_path", "mask_path", "blend_image_path", "output_dir", "destination", "destination_dir"]
                    
                    if is_dynamic_builder:
                        builder_layout = QVBoxLayout()
                        builder_layout.setContentsMargins(0, 10, 0, 15)
                        
                        help_lbl = QLabel(f"🛠️ Universal Path/Name Builder ({arg}):")
                        help_lbl.setStyleSheet("color: #17a2b8; font-weight: bold;")
                        builder_layout.addWidget(help_lbl)
                        
                        arg_in = QLineEdit(str(data["params"][arg]))
                        arg_in.setPlaceholderText("e.g. {current_dir}/{current_name}_mask{original_ext}")
                        arg_in.editingFinished.connect(apply_updates_silent)
                        builder_layout.addWidget(arg_in)
                        
                        btn_layout1 = QHBoxLayout()
                        btn_orig = QPushButton("+ File Name")
                        btn_orig.clicked.connect(lambda _, t=arg_in: [t.insert("{current_name}"), apply_updates_silent()])
                        
                        btn_ext = QPushButton("+ Ext")
                        btn_ext.setToolTip("Inserts original extension e.g., .jpg")
                        btn_ext.clicked.connect(lambda _, t=arg_in: [t.insert("{original_ext}"), apply_updates_silent()])
                        
                        btn_pdir = QPushButton("+ Dir Name")
                        btn_pdir.clicked.connect(lambda _, t=arg_in: [t.insert("{current_dir_name}"), apply_updates_silent()])
                        
                        btn_path = QPushButton("+ Dir Path")
                        btn_path.setToolTip("Inserts full current folder path")
                        btn_path.clicked.connect(lambda _, t=arg_in: [t.insert("{current_dir}/"), apply_updates_silent()])
                        
                        btn_preserve = QPushButton("+ Preserve Tree")
                        btn_preserve.setToolTip("Recreates original folder structure inside this path")
                        btn_preserve.clicked.connect(lambda _, t=arg_in: [t.insert("/{preserve_structure}" if t.text() and not t.text().endswith('/') else "{preserve_structure}"), apply_updates_silent()])
                        
                        for btn in [btn_orig, btn_ext, btn_pdir, btn_path, btn_preserve]:
                            btn.setStyleSheet("background-color: #444; font-size: 10px; padding: 4px;")
                            btn_layout1.addWidget(btn)
                        builder_layout.addLayout(btn_layout1)
                        
                        btn_layout2 = QHBoxLayout()
                        btn_num = QPushButton("+ Num (1,2)")
                        btn_num.clicked.connect(lambda _, t=arg_in: [t.insert("{num_count}"), apply_updates_silent()])
                        btn_alpha = QPushButton("+ Alpha (a,b)")
                        btn_alpha.clicked.connect(lambda _, t=arg_in: [t.insert("{alpha_count}"), apply_updates_silent()])
                        btn_rand_num = QPushButton("+ Rand Num(N)")
                        btn_rand_num.clicked.connect(lambda _, t=arg_in: [t.insert("{rand_num_4}"), apply_updates_silent()])
                        btn_rand_alpha = QPushButton("+ Rand Alpha(N)")
                        btn_rand_alpha.clicked.connect(lambda _, t=arg_in: [t.insert("{rand_alpha_4}"), apply_updates_silent()])
                        
                        for btn in [btn_num, btn_alpha, btn_rand_num, btn_rand_alpha]:
                            btn.setStyleSheet("background-color: #444; font-size: 10px; padding: 4px;")
                            btn_layout2.addWidget(btn)
                        builder_layout.addLayout(btn_layout2)
                        
                        btn_layout3 = QHBoxLayout()
                        loop_combo = QComboBox()
                        loop_combo.setStyleSheet("font-size: 10px;")
                        loop_combo.addItem("Select Dir Loop Name...")
                        for l_name in all_dir_loops:
                            loop_combo.addItem(f"Dir Name: {l_name}", f"{{{l_name}_name}}")
                        
                        btn_insert_loop = QPushButton("+ Add Dir Name")
                        btn_insert_loop.setStyleSheet("background-color: #17a2b8; font-size: 10px; color: white; padding: 4px;")
                        btn_insert_loop.clicked.connect(lambda _, t=arg_in, c=loop_combo: [t.insert(c.currentData()), apply_updates_silent()] if c.currentIndex() > 0 else None)
                        
                        ui_combo = QComboBox()
                        ui_combo.setStyleSheet("font-size: 10px;")
                        for el in self.current_project.app_body.findChildren(MovableElement):
                            if el.elem_type in ["Input Text Field", "Dropdown"]:
                                lbl_type = "Input" if el.elem_type == "Input Text Field" else "Dropdown"
                                acc_meth = "text()" if el.elem_type == "Input Text Field" else "currentText()"
                                ui_combo.addItem(f"UI {lbl_type}: {el.get_text()[:10]}", f"self.{el.elem_id}.{acc_meth}.strip()")
                        
                        btn_ui_insert = QPushButton("+ Add UI")
                        btn_ui_insert.setStyleSheet("background-color: #17a2b8; font-size: 10px; color: white; padding: 4px;")
                        btn_ui_insert.clicked.connect(lambda _, t=arg_in, c=ui_combo: [t.insert(f"{{{c.currentData()}}}"), apply_updates_silent()] if c.count() > 0 else None)
                        
                        btn_layout3.addWidget(loop_combo)
                        btn_layout3.addWidget(btn_insert_loop)
                        btn_layout3.addWidget(ui_combo)
                        btn_layout3.addWidget(btn_ui_insert)
                        builder_layout.addLayout(btn_layout3)
                        
                        btn_layout4 = QHBoxLayout()
                        btn_browse_dir = QPushButton("📂 Browse Dir")
                        btn_browse_dir.setStyleSheet("background-color: #555; font-size: 10px; color: white; padding: 4px;")
                        btn_browse_dir.clicked.connect(lambda _, f=arg_in: [f.setText(QFileDialog.getExistingDirectory(self, "Select Directory") or f.text()), apply_updates_silent()])
                        
                        btn_browse_file = QPushButton("📄 Browse File")
                        btn_browse_file.setStyleSheet("background-color: #555; font-size: 10px; color: white; padding: 4px;")
                        btn_browse_file.clicked.connect(lambda _, f=arg_in: [f.setText(QFileDialog.getOpenFileName(self, "Select File")[0] or f.text()), apply_updates_silent()])
                        
                        btn_layout4.addWidget(btn_browse_dir)
                        btn_layout4.addWidget(btn_browse_file)
                        builder_layout.addLayout(btn_layout4)
                        
                        self.property_container_layout.addLayout(builder_layout)
                        inputs_map[arg] = arg_in
                    else:
                        layout = QHBoxLayout()
                        layout.addWidget(QLabel(f"{arg}:"))
                        arg_in = QLineEdit(str(data["params"][arg]))
                        arg_in.editingFinished.connect(apply_updates_silent)
                        layout.addWidget(arg_in)
                        
                        conn_combo = QComboBox()
                        
                        if is_path_param:
                            conn_combo.addItem("Browse File...", "BROWSE_FILE")
                            conn_combo.addItem("Browse Folder...", "BROWSE_DIR")
                            conn_combo.addItem("Auto (Current Loop File)", "file_path")
                            conn_combo.addItem("Auto (Current Loop Dir)", "current_dir")
                            conn_combo.addItem("Main Input (Root)", "dir_root")
                            
                            for l_name in all_file_loops:
                                conn_combo.addItem(f"File Loop: {l_name}", l_name)
                            for l_name in all_dir_loops:
                                conn_combo.addItem(f"Dir Loop: {l_name}", l_name)
                        else:
                            conn_combo.addItem("Manual Input", "Manual")
                            
                            if arg_lower == 'alpha':
                                conn_combo.addItem("Auto (1)", "1")
                            elif any(x in arg_lower for x in ['width', 'height', 'size', 'amount', 'num', 'val']):
                                conn_combo.addItem("Auto (None)", "None")
                                
                            elif arg_lower == 'model_type':
                                if "depth" in func_n.lower():
                                    for opt in ["DPT_Large", "DPT_Hybrid", "MiDaS_small"]:
                                        conn_combo.addItem(f"Model: {opt}", opt)
                                else:
                                    for opt in ["Human Segmentation", "Cloth Segmentation", "General Object"]:
                                        conn_combo.addItem(f"Model: {opt}", opt)
                            elif arg_lower == 'quality':
                                for opt in ["small", "base", "large"]: conn_combo.addItem(f"Quality: {opt}", opt)
                            elif arg_lower == 'action':
                                for opt in ["reduce", "add"]: conn_combo.addItem(f"Action: {opt}", opt)
                            elif arg_lower in ['upscale', 'outscale']:
                                for opt in ["2", "4", "8"]: conn_combo.addItem(f"Scale: {opt}x", opt)
                            elif "orientation" in arg_lower or "align" in arg_lower or "position" in arg_lower:
                                for opt in ["center", "left", "right", "top", "bottom", "left-top", "top-left", "top-right", "right-top", "right-bottom", "bottom-right", "bottom-left", "left-bottom"]:
                                    conn_combo.addItem(f"Preset: {opt}", opt)
                                    
                            elif "blending_mode" in arg_lower or "blend_mode" in arg_lower:
                                for opt in ['multiply', 'soft_light', 'hard_light', 'overlay', 'dodge', 'addition', 'subtract', 'darken_only', 'lighten_only', 'difference', 'divide', 'grain_extract', 'grain_merge', 'normal']:
                                    conn_combo.addItem(f"Mode: {opt}", opt)
                                    
                            elif "ext" in arg_lower or "extension" in arg_lower:
                                for opt in ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif', '.bmp', '.jxl', '.heic', '.heif']:
                                    conn_combo.addItem(f"Ext: {opt}", opt)
                                    
                            elif "match_type" in arg_lower:
                                conn_combo.addItem("Type: contains", "contains")
                                conn_combo.addItem("Type: exact", "exact")
                            elif arg_lower == "mode":
                                for opt in ["exact", "contains", "extension"]:
                                    conn_combo.addItem(f"Mode: {opt}", opt)

                        for el in self.current_project.app_body.findChildren(MovableElement):
                            if el.elem_type in ["Input Text Field", "Dropdown", "Plain Text Edit"]:
                                if el.elem_type == "Input Text Field":
                                    lbl_type, acc_meth = "Input", "text()"
                                elif el.elem_type == "Dropdown":
                                    lbl_type, acc_meth = "Dropdown", "currentText()"
                                else:  # Plain Text Edit ke liye
                                    lbl_type, acc_meth = "TextEdit", "toPlainText()"
                                    
                                ui_combo.addItem(f"UI {lbl_type}: {el.get_text()[:10]}", f"self.{el.elem_id}.{acc_meth}.strip()")
                        
                        layout.addWidget(conn_combo)
                        self.property_container_layout.addLayout(layout)
                        inputs_map[arg] = arg_in
                        
                        current_val = str(data["params"][arg])
                        if current_val == "None":
                            idx = conn_combo.findData("None")
                            if idx >= 0: conn_combo.setCurrentIndex(idx)
                        else:
                            for ci in range(conn_combo.count()):
                                if conn_combo.itemData(ci) == current_val:
                                    conn_combo.setCurrentIndex(ci)
                                    break
                        
                        def on_conn_changed(idx, combo=conn_combo, field=arg_in):
                            val = combo.currentData()
                            if val == "BROWSE_FILE":
                                path, _ = QFileDialog.getOpenFileName(self, "Select File")
                                if path: field.setText(path)
                                combo.setCurrentIndex(0)
                            elif val == "BROWSE_DIR":
                                path = QFileDialog.getExistingDirectory(self, "Select Directory")
                                if path: field.setText(path)
                                combo.setCurrentIndex(0)
                            elif val == "None":
                                field.setText("None")
                            elif val != "Manual":
                                field.setText(val)
                            apply_updates_silent()
                        conn_combo.currentIndexChanged.connect(on_conn_changed)

            chk_log = QCheckBox("Log Output to Console")
            chk_log.setChecked(data["params"].get("log_console", True))
            chk_log.stateChanged.connect(apply_updates_silent)
            self.property_container_layout.addWidget(chk_log)
            inputs_map["log_console"] = chk_log

            btn_update = QPushButton("💾 Update Properties")
            btn_update.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
            
            def apply_updates():
                for param_key, widget_ref in inputs_map.items():
                    if isinstance(widget_ref, QSpinBox):
                        data["params"][param_key] = widget_ref.value()
                    elif isinstance(widget_ref, QLineEdit):
                        data["params"][param_key] = widget_ref.text()
                    elif isinstance(widget_ref, QCheckBox):
                        data["params"][param_key] = widget_ref.isChecked()
                    elif isinstance(widget_ref, QComboBox):
                        data["params"][param_key] = widget_ref.currentText()
                item.setData(0, Qt.UserRole, data)
                self.record_state()
                self.update_tree_title_from_params(item, data)
                self.node_scene.update()
                QMessageBox.information(self, "Success", "Node parameters updated successfully!")
                
            btn_update.clicked.connect(apply_updates)
            self.property_container_layout.addWidget(btn_update)

            btn_del = QPushButton("🗑️ Delete Block"); btn_del.setStyleSheet("background-color: #dc3545; color: white;")
            btn_del.clicked.connect(lambda _, i=item: self.delete_tree_item(i))
            self.property_container_layout.addWidget(btn_del)
            self.property_container_layout.addStretch()
            return

        # --- MASTER PIPELINE PROPERTIES ---
        if self.selected_master_pipe:
            mp = self.selected_master_pipe
            self.property_container_layout.addWidget(QLabel("<b>👑 Master Pipeline Panel</b>"))
            
            layout1 = QHBoxLayout(); layout1.addWidget(QLabel("Pipeline Name:")); 
            func_input = QLineEdit(mp.func_name)
            def update_mp_nm(val, m=mp):
                self.update_mf_param(m, 'func_name', val)
                self.node_scene.update()
            func_input.textChanged.connect(update_mp_nm)
            layout1.addWidget(func_input); self.property_container_layout.addLayout(layout1)

            layout2 = QHBoxLayout(); layout2.addWidget(QLabel("Directory Input:"))
            in_combo = QComboBox(); in_combo.addItem("None", "None")
            for el in self.current_project.app_body.findChildren(MovableElement):
                if el.elem_type == "Input Text Field": in_combo.addItem(f"{el.get_text()[:10]} ({el.elem_id[-4:]})", el.elem_id)
            in_combo.setCurrentIndex(max(0, in_combo.findData(mp.input_linked_id)))
            in_combo.currentIndexChanged.connect(lambda idx, m=mp, cb=in_combo: [self.update_mf_param(m, 'input_linked_id', cb.itemData(idx)), self.node_scene.update()])
            layout2.addWidget(in_combo); self.property_container_layout.addLayout(layout2)

            layout3 = QHBoxLayout(); layout3.addWidget(QLabel("Console Output:"))
            con_combo = QComboBox(); con_combo.addItem("None", "None")
            for el in self.current_project.app_body.findChildren(MovableElement):
                if el.elem_type == "Console": con_combo.addItem(f"Console ({el.elem_id[-4:]})", el.elem_id)
            con_combo.setCurrentIndex(max(0, con_combo.findData(mp.console_linked_id)))
            con_combo.currentIndexChanged.connect(lambda idx, m=mp, cb=con_combo: [self.update_mf_param(m, 'console_linked_id', cb.itemData(idx)), self.node_scene.update()])
            layout3.addWidget(con_combo); self.property_container_layout.addLayout(layout3)

            btn_del = QPushButton("🗑️ Delete Pipeline Panel"); btn_del.setStyleSheet("background-color: #dc3545; color: white;")
            btn_del.clicked.connect(lambda _, m=mp: self.delete_main_func(m))
            self.property_container_layout.addWidget(btn_del)
            self.property_container_layout.addStretch()
            return

        # --- MAIN FUNCTION PANEL PROPERTIES ---
        if self.selected_main_func:
            mf = self.selected_main_func
            self.property_container_layout.addWidget(QLabel("<b>⚙️ Main Function Panel</b>"))
            
            layout1 = QHBoxLayout(); layout1.addWidget(QLabel("Func Name:")); 
            func_input = QLineEdit(mf.func_name)
            def update_mf_nm(val, m=mf):
                self.update_mf_param(m, 'func_name', val)
                self.update_master_combos()
                self.node_scene.update()
            func_input.textChanged.connect(update_mf_nm)
            layout1.addWidget(func_input); self.property_container_layout.addLayout(layout1)

            layout2 = QHBoxLayout(); layout2.addWidget(QLabel("Directory Input:"))
            in_combo = QComboBox(); in_combo.addItem("None", "None")
            for el in self.current_project.app_body.findChildren(MovableElement):
                if el.elem_type == "Input Text Field": in_combo.addItem(f"{el.get_text()[:10]} ({el.elem_id[-4:]})", el.elem_id)
            for mp in self.master_pipeline_nodes:
                in_combo.addItem(f"Master: {mp.func_name}", mp.elem_id)
            in_combo.setCurrentIndex(max(0, in_combo.findData(mf.input_linked_id)))
            in_combo.currentIndexChanged.connect(lambda idx, m=mf, cb=in_combo: [self.update_mf_param(m, 'input_linked_id', cb.itemData(idx)), self.node_scene.update()])
            layout2.addWidget(in_combo); self.property_container_layout.addLayout(layout2)

            layout3 = QHBoxLayout(); layout3.addWidget(QLabel("Console Output:"))
            con_combo = QComboBox(); con_combo.addItem("None", "None")
            for el in self.current_project.app_body.findChildren(MovableElement):
                if el.elem_type == "Console": con_combo.addItem(f"Console ({el.elem_id[-4:]})", el.elem_id)
            con_combo.setCurrentIndex(max(0, con_combo.findData(mf.console_linked_id)))
            con_combo.currentIndexChanged.connect(lambda idx, m=mf, cb=con_combo: [self.update_mf_param(m, 'console_linked_id', cb.itemData(idx)), self.node_scene.update()])
            layout3.addWidget(con_combo); self.property_container_layout.addLayout(layout3)

            btn_del = QPushButton("🗑️ Delete Function Panel"); btn_del.setStyleSheet("background-color: #dc3545; color: white;")
            btn_del.clicked.connect(lambda _, m=mf: self.delete_main_func(m))
            self.property_container_layout.addWidget(btn_del)
            self.property_container_layout.addStretch()
            return

        # --- UI ELEMENT PROPERTIES ---
        if len(self.selected_elements) == 1:
            element = self.selected_elements[0]
            self.property_container_layout.addWidget(QLabel(f"Type: {element.elem_type}"))
            
            if element.elem_type == "Button":
                action_layout = QHBoxLayout()
                action_layout.addWidget(QLabel("Action:"))
                action_combo = QComboBox()
                custom_funcs = [m.func_name for m in self.main_function_nodes] + [mp.func_name for mp in self.master_pipeline_nodes]
                action_combo.addItems(["None", "Select File", "Select Directory"] + custom_funcs)
                action_combo.setCurrentText(element.button_action)
                def btn_act_chg(val, el=element):
                    self.change_button_action(el, val)
                    self.node_scene.update()
                action_combo.currentTextChanged.connect(btn_act_chg)
                action_layout.addWidget(action_combo)
                self.property_container_layout.addLayout(action_layout)

            if element.elem_type == "Input Text Field":
                link_layout = QHBoxLayout()
                link_layout.addWidget(QLabel("Link to Button:"))
                link_combo = QComboBox()
                link_combo.addItem("None", "None")
                for child in self.current_project.app_body.findChildren(MovableElement):
                    if child.elem_type == "Button": link_combo.addItem(f"{child.get_text()} ({child.elem_id[-4:]})", child.elem_id)
                idx = link_combo.findData(element.connected_button_id)
                if idx >= 0: link_combo.setCurrentIndex(idx)
                def btn_lnk_chg(idx, el=element, cb=link_combo):
                    self.change_connected_button(el, cb.itemData(idx))
                    self.node_scene.update()
                link_combo.currentIndexChanged.connect(btn_lnk_chg)
                link_layout.addWidget(link_combo)
                self.property_container_layout.addLayout(link_layout)
                
            if element.elem_type == "Dropdown":
                options_layout = QHBoxLayout()
                options_layout.addWidget(QLabel("Options (comma separated):"))
                opt_input = QLineEdit(element.dropdown_options)
                def opt_chg(val, el=element):
                    el.dropdown_options = val
                    el.inner_widget.clear()
                    el.inner_widget.addItems([o.strip() for o in val.split(',') if o.strip()])
                    self.node_scene.update()
                opt_input.textChanged.connect(opt_chg)
                opt_input.editingFinished.connect(self.record_state)
                options_layout.addWidget(opt_input)
                self.property_container_layout.addLayout(options_layout)
            
            if element.elem_type == "Image":
                shape_layout = QHBoxLayout(); shape_layout.addWidget(QLabel("Shape:"))
                shape_combo = QComboBox(); shape_combo.addItems(["Rectangle", "Square", "Circle"])
                shape_combo.setCurrentText(element.shape)
                shape_combo.currentTextChanged.connect(lambda val, el=element: self.change_shape(el, val))
                shape_layout.addWidget(shape_combo); self.property_container_layout.addLayout(shape_layout)

                img_btn = QPushButton("📂 Browse Image")
                img_btn.clicked.connect(lambda _, el=element: self.browse_element_image(el))
                self.property_container_layout.addWidget(img_btn)
                if element.image_path:
                    path_label = QLabel(os.path.basename(element.image_path))
                    path_label.setStyleSheet("color: #aaa; font-size: 10px;")
                    self.property_container_layout.addWidget(path_label)
            elif element.elem_type not in ["Console", "Dropdown"]:
                text_input = QLineEdit()
                text_input.setText(element.get_text())
                def txt_chg(val, el=element):
                    el.set_text(val)
                    for en in self.element_nodes:
                        if en.element_ref == el:
                            t_val = val[:10] if val else el.elem_type
                            icon_str = "🔳" if el.elem_type == "Button" else "📝" if el.elem_type == "Input Text Field" else "💻"
                            en.text_item.setPlainText(f"{icon_str} UI: {t_val}\n({el.elem_id[-4:]})")
                    self.node_scene.update()
                text_input.textChanged.connect(txt_chg)
                text_input.editingFinished.connect(self.record_state)
                self.property_container_layout.addWidget(QLabel("Text / Value:"))
                self.property_container_layout.addWidget(text_input)

            if element.elem_type not in ["Image", "Console", "Dropdown"]:
                font_layout = QHBoxLayout(); font_layout.addWidget(QLabel("Font Size (px):"))
                font_input = QLineEdit(str(element.font_size))
                font_input.textChanged.connect(lambda val, el=element: self.change_font_size(el, val))
                font_input.editingFinished.connect(self.record_state)
                font_layout.addWidget(font_input); self.property_container_layout.addLayout(font_layout)

                align_layout = QHBoxLayout(); align_layout.addWidget(QLabel("Text Alignment:"))
                align_combo = QComboBox(); align_combo.addItems(["Left", "Center", "Right"])
                align_combo.setCurrentText(element.alignment)
                align_combo.currentTextChanged.connect(lambda val, el=element: self.change_alignment(el, val))
                align_layout.addWidget(align_combo); self.property_container_layout.addLayout(align_layout)

            chk_fill = QCheckBox("Enable Fill Background")
            chk_fill.setChecked(element.has_fill)
            chk_fill.stateChanged.connect(lambda state, el=element: self.toggle_fill(el, state))
            self.property_container_layout.addWidget(chk_fill)

            btn_bg_color = QPushButton("🎨 Change Fill Color")
            btn_bg_color.clicked.connect(lambda _, el=element: self.change_bg_color(el))
            self.property_container_layout.addWidget(btn_bg_color)

            if element.elem_type not in ["Image", "Console"]:
                btn_text_color = QPushButton("🎨 Change Text Color")
                btn_text_color.clicked.connect(lambda _, el=element: self.change_text_color(el))
                self.property_container_layout.addWidget(btn_text_color)

            btn_border_color = QPushButton("🎨 Change Border Color")
            btn_border_color.clicked.connect(lambda _, el=element: self.change_border_color(el))
            self.property_container_layout.addWidget(btn_border_color)

            border_width_layout = QHBoxLayout()
            border_width_layout.addWidget(QLabel("Border Width (px):"))
            border_width_input = QLineEdit(str(element.border_width))
            border_width_input.textChanged.connect(lambda val, el=element: self.change_border_width(el, val))
            border_width_input.editingFinished.connect(self.record_state)
            border_width_layout.addWidget(border_width_input)
            self.property_container_layout.addLayout(border_width_layout)

            radius_layout = QHBoxLayout()
            radius_layout.addWidget(QLabel("Corner Radius:"))
            radius_input = QLineEdit(str(element.radius))
            if element.shape == "Circle": radius_input.setEnabled(False)
            radius_input.textChanged.connect(lambda val, el=element: self.change_radius(el, val))
            radius_input.editingFinished.connect(self.record_state)
            radius_layout.addWidget(radius_input)
            self.property_container_layout.addLayout(radius_layout)

            btn_delete = QPushButton("🗑️ Delete Element")
            btn_delete.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
            btn_delete.clicked.connect(lambda _, el=element: self.delete_element(el))
            self.property_container_layout.addWidget(btn_delete)
            self.property_container_layout.addStretch()

        elif len(self.selected_elements) > 1:
            self.property_container_layout.addWidget(QLabel(f"<b>{len(self.selected_elements)} Elements Selected</b>"))
            self.property_container_layout.addWidget(QLabel("Multi-selection active. Drag together or delete."))
            btn_delete_all = QPushButton("🗑️ Delete Selected Elements")
            btn_delete_all.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
            btn_delete_all.clicked.connect(self.delete_selected_elements)
            self.property_container_layout.addWidget(btn_delete_all)
            self.property_container_layout.addStretch()
        else:
            self.property_container_layout.addWidget(QLabel("Select an element/node to edit."))
            self.property_container_layout.addStretch()

    def delete_tree_item(self, item):
        self.record_state()
        
        node_data = item.data(0, Qt.UserRole)
        c_id = node_data.get("params", {}).get("code_node_id")
        if c_id:
            for cn in self.code_nodes:
                if cn.elem_id == c_id:
                    self.node_scene.removeItem(cn)
                    self.code_nodes.remove(cn)
                    if self.selected_code_node == cn: self.selected_code_node = None
                    break
                    
        parent = item.parent()
        if parent: parent.removeChild(item)
        else: item.treeWidget().takeTopLevelItem(item.treeWidget().indexOfTopLevelItem(item))
        self.selected_tree_item = None
        self.update_property_panel()
        self.node_scene.update()

    def update_mf_param(self, mf_node, param, val):
        setattr(mf_node, param, val)
        if hasattr(mf_node, 'update_title'):
            mf_node.update_title()
        self.record_state()

    def delete_main_func(self, node):
        self.record_state()
        
        tree_state = node.extract_tree_state()
        def del_linked_codes(nodes_list):
            for n in nodes_list:
                c_id = n.get("node_data", {}).get("params", {}).get("code_node_id")
                if c_id:
                    for cn in self.code_nodes:
                        if cn.elem_id == c_id:
                            self.node_scene.removeItem(cn)
                            self.code_nodes.remove(cn)
                            if self.selected_code_node == cn: self.selected_code_node = None
                            break
                if n.get("children"):
                    del_linked_codes(n["children"])
        del_linked_codes(tree_state)
        
        for child in self.current_project.app_body.findChildren(MovableElement):
            if child.elem_type == "Button" and child.button_action == node.func_name:
                child.button_action = "None"
                
        if hasattr(node, 'get_sequence'):
            for mf in self.main_function_nodes:
                if mf.input_linked_id == node.elem_id:
                    mf.input_linked_id = "None"

        self.node_scene.removeItem(node)
        if node in self.main_function_nodes: 
            self.main_function_nodes.remove(node)
            self.update_master_combos()
        if node in self.master_pipeline_nodes:
            self.master_pipeline_nodes.remove(node)
            
        if self.selected_main_func == node: self.selected_main_func = None
        if self.selected_master_pipe == node: self.selected_master_pipe = None
        self.update_property_panel()
        self.node_scene.update()

    def change_button_action(self, element, val):
        element.button_action = val
        self.record_state()

    def change_connected_button(self, element, val):
        element.connected_button_id = val
        self.record_state()

    def change_font_size(self, element, val):
        try:
            element.font_size = int(val)
            element.apply_style()
        except ValueError: pass

    def change_alignment(self, element, val):
        element.alignment = val
        element.apply_alignment()
        element.apply_style()
        self.record_state()

    def browse_element_image(self, element):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            element.image_path = file_path
            element.apply_style()
            self.record_state()
            self.update_property_panel()

    def change_shape(self, element, val):
        element.shape = val
        if val in ["Square", "Circle"]:
            size = max(element.inner_widget.width(), element.inner_widget.height())
            if val == "Circle": element.radius = size // 2
            element.resize(size + (element.padding * 2), size + (element.padding * 2))
            element.inner_widget.resize(size, size)
        element.apply_style()
        self.record_state()
        self.update_property_panel()

    def handle_canvas_click_deselect(self):
        for el in self.selected_elements: el.set_selected(False)
        self.selected_elements.clear()
        if self.selected_main_func:
            self.selected_main_func.set_selected(False)
            self.selected_main_func = None
        if self.selected_master_pipe:
            self.selected_master_pipe.set_selected(False)
            self.selected_master_pipe = None
        if self.selected_code_node:
            self.selected_code_node.set_selected(False)
            self.selected_code_node = None
            
        if getattr(self, 'selected_canvas_node', None):
            self.selected_canvas_node.set_selected(False)
            self.selected_canvas_node = None
            
        self.selected_tree_item = None
        self.update_property_panel()

    def handle_canvas_node_selection(self, node):
        self.handle_canvas_click_deselect() # Clear other selections
        self.selected_canvas_node = node
        node.set_selected(True)

    def toggle_fill(self, element, state):
        element.has_fill = (state == Qt.Checked)
        element.apply_style(); self.record_state()

    def change_bg_color(self, element):
        color = QColorDialog.getColor()
        if color.isValid():
            element.bg_color = color.name()
            element.apply_style(); self.record_state()

    def change_text_color(self, element):
        color = QColorDialog.getColor()
        if color.isValid():
            element.text_color = color.name()
            element.apply_style(); self.record_state()

    def change_border_color(self, element):
        color = QColorDialog.getColor()
        if color.isValid():
            element.border_color = color.name()
            element.apply_style(); self.record_state()

    def change_border_width(self, element, val):
        try:
            element.border_width = int(val); element.apply_style()
        except ValueError: pass

    def change_radius(self, element, val):
        try:
            element.radius = int(val); element.apply_style()
        except ValueError: pass

    def delete_element(self, element):
        self.record_state()
        if element.elem_type == "Button":
            for child in self.current_project.app_body.findChildren(MovableElement):
                if child.elem_type == "Input Text Field" and child.connected_button_id == element.elem_id:
                    child.connected_button_id = "None"
        elif element.elem_type == "Console":
            for mf in self.main_function_nodes + self.master_pipeline_nodes:
                if mf.console_linked_id == element.elem_id:
                    mf.console_linked_id = "None"
        elif element.elem_type in ["Input Text Field", "Dropdown"]:
            for mf in self.main_function_nodes + self.master_pipeline_nodes:
                if mf.input_linked_id == element.elem_id:
                    mf.input_linked_id = "None"

        element.deleteLater()
        if element in self.selected_elements: self.selected_elements.remove(element)
        for en in self.element_nodes:
            if en.element_ref == element:
                self.node_scene.removeItem(en)
                self.element_nodes.remove(en)
                break
        self.handle_canvas_click_deselect()
        self.node_scene.update()

    def delete_selected_elements(self):
        if not self.selected_elements: return
        self.record_state()
        for el in list(self.selected_elements):
            if el.elem_type == "Button":
                for child in self.current_project.app_body.findChildren(MovableElement):
                    if child.elem_type == "Input Text Field" and child.connected_button_id == el.elem_id:
                        child.connected_button_id = "None"
            elif el.elem_type == "Console":
                for mf in self.main_function_nodes + self.master_pipeline_nodes:
                    if mf.console_linked_id == el.elem_id:
                        mf.console_linked_id = "None"
            elif el.elem_type in ["Input Text Field", "Dropdown"]:
                for mf in self.main_function_nodes + self.master_pipeline_nodes:
                    if mf.input_linked_id == el.elem_id:
                        mf.input_linked_id = "None"

            el.deleteLater()
            for en in self.element_nodes:
                if en.element_ref == el:
                    self.node_scene.removeItem(en)
                    self.element_nodes.remove(en)
                    break
        self.handle_canvas_click_deselect()
        self.node_scene.update()

    def start_build_app(self):
        dialog = NewAppDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            app_data = dialog.get_data()
            self.create_new_project_tab(app_data.get("app_name", "App"), "app_builder", app_data)

    def start_node_editor(self):
        name, ok = QInputDialog.getText(self, "New Image Edit Project", "Enter Project Name:")
        if ok and name.strip():
            self.create_new_project_tab(name.strip(), "node_editor")

    def save_current_tab_state(self):
        if getattr(self, 'current_tab_id', -1) != -1 and self.current_tab_id in getattr(self, 'projects_data', {}):
            self.projects_data[self.current_tab_id].update({
                "scene": self.node_scene,
                "current_project": self.current_project,
                "element_nodes": self.element_nodes.copy(),
                "main_function_nodes": self.main_function_nodes.copy(),
                "master_pipeline_nodes": self.master_pipeline_nodes.copy(),
                "code_nodes": self.code_nodes.copy(),
                "canvas_nodes": getattr(self, 'canvas_nodes', []).copy(),
                "canvas_connections": getattr(self, 'canvas_connections', []).copy(),
                "current_mode": getattr(self, 'current_mode', 'app_builder'),
                "undo_stack": self.undo_stack.copy(),
                "is_modified": getattr(self, 'is_modified', False) # Modification save karna
            })

    def switch_project_tab(self, index):
        if index == -1: return
        tab_id = self.tab_bar.tabData(index) 
        if not tab_id or tab_id not in self.projects_data: return
        
        if getattr(self, 'current_tab_id', -1) != tab_id:
            self.save_current_tab_state()
            
        tab_data = self.projects_data[tab_id]
        self.current_tab_id = tab_id
        
        self.node_scene = tab_data["scene"]
        self.node_view.setScene(self.node_scene)
        self.current_project = tab_data["current_project"]
        self.element_nodes = tab_data["element_nodes"]
        self.main_function_nodes = tab_data["main_function_nodes"]
        self.master_pipeline_nodes = tab_data["master_pipeline_nodes"]
        self.code_nodes = tab_data["code_nodes"]
        self.canvas_nodes = tab_data["canvas_nodes"]
        self.canvas_connections = tab_data["canvas_connections"]
        self.current_mode = tab_data["current_mode"]
        self.undo_stack = tab_data["undo_stack"]
        self.is_modified = tab_data.get("is_modified", False)
        
        if self.current_mode == "app_builder":
            self.app_mode_widget.setVisible(True)
            self.node_mode_widget.setVisible(False)
            self.btn_publish_app.setEnabled(True)
            self.btn_preview_app.setEnabled(True)
            # Add these 3 lines:
            self.btn_ide.setVisible(True)
            self.btn_main.setVisible(True)
            self.btn_master.setVisible(True)
        else:
            self.app_mode_widget.setVisible(False)
            self.node_mode_widget.setVisible(True)
            self.btn_publish_app.setEnabled(False)
            self.btn_preview_app.setEnabled(False)
            # Add these 3 lines:
            self.btn_ide.setVisible(False)
            self.btn_main.setVisible(False)
            self.btn_master.setVisible(False)
            
        self.left_dock.show()
        self.right_dock.show()
        self.handle_canvas_click_deselect()

    def close_project_workspace(self):
        self.btn_save_project.setEnabled(False)
        if hasattr(self, 'btn_save_as'): self.btn_save_as.setEnabled(False)  # <-- Ye line add karein

        if getattr(self, 'current_tab_id', -1) != -1:
            for i in range(self.tab_bar.count()):
                if self.tab_bar.tabData(i) == self.current_tab_id:
                    self.close_project_tab(i)
                    break

    def close_project_tab(self, index):
        tab_id = self.tab_bar.tabData(index)
        if not tab_id or tab_id not in getattr(self, 'projects_data', {}): return

        # ⚠️ UNSAVED CHANGES CHECK
        tab_data = self.projects_data[tab_id]
        is_mod = self.is_modified if self.current_tab_id == tab_id else tab_data.get("is_modified", False)
        
        if is_mod:
            if self.current_tab_id != tab_id:
                self.tab_bar.setCurrentIndex(index) # Tab ko aage layein dialog ke liye
                
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "Project me unsaved changes hain.\nKya aap close karne se pehle save karna chahte hain?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Save:
                if not self.save_project():
                    return # User ne cancel kiya toh band nahi hoga
            elif reply == QMessageBox.Cancel:
                return

        # ⚠️ FIX CRASH: Selections clear karna zaroori hai nahi toh QT C++ error aayega
        if self.current_tab_id == tab_id:
            self.selected_elements.clear()
            self.selected_main_func = None
            self.selected_master_pipe = None
            self.selected_code_node = None
            if hasattr(self, 'selected_canvas_node'): self.selected_canvas_node = None
            self.selected_tree_item = None
            
            # Clear properties panel securely
            while self.property_container_layout.count():
                child = self.property_container_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
        
        # Free memory cleanly
        scene_to_delete = tab_data.get("scene")
        if scene_to_delete:
            scene_to_delete.clear()
            scene_to_delete.deleteLater()
            
        del self.projects_data[tab_id]
        
        self.tab_bar.blockSignals(True)
        self.tab_bar.removeTab(index)
        self.tab_bar.blockSignals(False)

        if self.tab_bar.count() == 0:
            self.current_tab_id = -1
            self.node_scene = NodeScene(self)
            self.node_view.setScene(self.node_scene)
            self.current_project = None
            self.element_nodes.clear()
            self.main_function_nodes.clear()
            self.master_pipeline_nodes.clear()
            self.code_nodes.clear()
            if hasattr(self, 'canvas_nodes'): self.canvas_nodes.clear()
            if hasattr(self, 'canvas_connections'): self.canvas_connections.clear()
            self.left_dock.hide()
            self.right_dock.hide()
            self.btn_save_project.setEnabled(False)
            if hasattr(self, 'btn_close_project'): self.btn_close_project.setEnabled(False)
            self.is_modified = False
        else:
            self.switch_project_tab(self.tab_bar.currentIndex())

    def create_new_project_tab(self, name, mode, app_data=None, geometry=None, elements=None):
        self.save_current_tab_state()
        
        tab_id = uuid.uuid4().hex  # ⚠️ UNIQUE MEMORY ID
        new_scene = NodeScene(self)
        
        # Watermark Add Karna
        mode_text = "App Builder Workspace" if mode == 'app_builder' else "Node Image Editor Workspace"
        from PyQt5.QtWidgets import QGraphicsTextItem
        from PyQt5.QtGui import QColor, QFont
        bg_text = QGraphicsTextItem(f"{name}\n({mode_text})")
        bg_text.setDefaultTextColor(QColor(255, 255, 255, 25)) 
        bg_text.setFont(QFont("Arial", 40, QFont.Bold))
        bg_text.setZValue(-1000) 
        bg_text.setPos(-200, -100)
        new_scene.addItem(bg_text)

       # Pehle Data Store karega, fir Tab banayega
        self.projects_data[tab_id] = {
            "scene": new_scene, "current_project": None, "element_nodes": [],
            "main_function_nodes": [], "master_pipeline_nodes": [], "code_nodes": [],
            "canvas_nodes": [], "canvas_connections": [], "current_mode": mode, "undo_stack": [],
            "file_path": None, "is_modified": False  # ⚠️ NAYA MEMORY SYSTEM
        }
        
        self.tab_bar.blockSignals(True) # Signals block taaki automatic mix na ho
        tab_name = f"{name} [{'App' if mode == 'app_builder' else 'Node'}]"
        tab_idx = self.tab_bar.addTab(tab_name)
        self.tab_bar.setTabData(tab_idx, tab_id) # ID inject kar di
        self.tab_bar.setCurrentIndex(tab_idx)
        self.tab_bar.blockSignals(False)
        
        # Manually Fresh Scene ko screen par layega
        self.switch_project_tab(tab_idx)
        
        if mode == "app_builder" and app_data:
            self.current_project = TargetAppProxy(
                app_data, close_callback=self.close_project_workspace,
                deselect_prop_callback=self.handle_canvas_click_deselect,
                multi_select_box_callback=self.handle_box_selection
            )
            self.node_scene.addItem(self.current_project)
            
            if geometry:
                self.current_project.setPos(geometry["x"], geometry["y"])
                self.current_project.window_widget.resize(geometry["width"], geometry["height"])
            else:
                center_pos = self.node_view.mapToScene(self.node_view.viewport().rect().center())
                self.current_project.setPos(center_pos.x() - 325, center_pos.y() - 250)
                
            if elements:
                for el in elements:
                    self.spawn_element_in_app(
                        elem_type=el["type"], text=el["text"], x=el["x"], y=el["y"], w=el["width"], h=el["height"],
                        bg_color=el.get("bg_color", "#007acc"), has_fill=el.get("has_fill", True),
                        text_color=el.get("text_color", "#ffffff"), radius=el.get("radius", 4),
                        border_width=el.get("border_width", 1), border_color=el.get("border_color", "#555555"),
                        image_path=el.get("image_path", ""), shape=el.get("shape", "Rectangle"),
                        font_size=el.get("font_size", 12), alignment=el.get("alignment", "Center"),
                        elem_id=el.get("elem_id"), button_action=el.get("button_action", "None"), connected_button_id=el.get("connected_button_id", "None"), dropdown_options=el.get("dropdown_options", "Option 1, Option 2"),
                        record=False, force_single=False, node_x=el.get("node_x"), node_y=el.get("node_y")
                    )
            
        self.btn_save_project.setEnabled(True)
        if hasattr(self, 'btn_close_project'): self.btn_close_project.setEnabled(True)
        
    def spawn_workspace(self, app_data, geometry=None, elements=None):
        # Purani load system ko naye tabs ke sath jod diya gaya hai
        mode = app_data.get("project_mode", "app_builder")
        self.create_new_project_tab(app_data.get("app_name", "Loaded App"), mode, app_data, geometry, elements)
        self.btn_save_project.setEnabled(True)
        if hasattr(self, 'btn_save_as'): self.btn_save_as.setEnabled(True)  # <-- Ye line add karein
        if hasattr(self, 'btn_close_project'): self.btn_close_project.setEnabled(True)

    def save_project(self):
        is_node_mode = getattr(self, 'current_mode', 'app_builder') == "node_editor"
        if not self.current_project and not is_node_mode: return False
        
        tab_id = getattr(self, 'current_tab_id', -1)
        file_path = None
        if tab_id != -1 and tab_id in getattr(self, 'projects_data', {}):
            file_path = self.projects_data[tab_id].get("file_path")

        if not file_path:
            if self.current_project:
                default_name = self.current_project.app_data.get('app_name', 'Untitled_App')
            else:
                idx = self.tab_bar.currentIndex()
                default_name = self.tab_bar.tabText(idx).split(" [")[0].replace("*", "") if idx >= 0 else "Node_Project"
                
            path, _ = QFileDialog.getSaveFileName(self, "Save Project", f"{default_name}.json", "JSON Files (*.json)")
            if not path: return False
            file_path = path
            
            if tab_id != -1:
                self.projects_data[tab_id]["file_path"] = file_path

        # 🚀 MOUSE CURSOR OVERRIDE (Processing/Wait Cursor start)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents() # UI ko turant refresh karega taaki cursor change feel ho

        try:
            state = {}
            if self.current_project:
                state = self.current_project.get_project_state()
                for el_state in state.get("elements", []):
                    for en in self.element_nodes:
                        if en.element_ref.elem_id == el_state["elem_id"]:
                            el_state["node_x"] = en.pos().x()
                            el_state["node_y"] = en.pos().y()
            else:
                state = {"app_name": os.path.basename(file_path).split('.')[0], "project_mode": "node_editor", "elements": []}

            state["main_functions"] = [{"func_name": mf.func_name, "input_linked_id": mf.input_linked_id, "console_linked_id": mf.console_linked_id, "x": mf.pos().x(), "y": mf.pos().y(), "width": mf.widget.width(), "height": mf.widget.height(), "tree_state": mf.extract_tree_state()} for mf in self.main_function_nodes]
            state["master_pipelines"] = [{"func_name": mp.func_name, "input_linked_id": mp.input_linked_id, "console_linked_id": mp.console_linked_id, "x": mp.pos().x(), "y": mp.pos().y(), "width": mp.widget.width(), "height": mp.widget.height(), "sequence": mp.get_sequence()} for mp in self.master_pipeline_nodes]
            
            state["code_nodes"] = [
                {"type": "global_ide" if isinstance(cn, GlobalIDEProxy) else "code_node", "elem_id": cn.elem_id, "x": cn.pos().x(), "y": cn.pos().y(), "width": cn.widget.width(), "height": cn.widget.height(), "code_text": cn.editor.toPlainText()} 
                for cn in self.code_nodes
            ]
            
            canvas_state = []
            for cnode in getattr(self, 'canvas_nodes', []):
                c_data = {
                    "elem_id": cnode.elem_id, "x": cnode.pos().x(), "y": cnode.pos().y(),
                    "width": cnode.widget.width(), "height": cnode.widget.height()
                }
                if isinstance(cnode, CanvasListNodeProxy):
                    c_data.update({"type": "List", "path": cnode.path_input.text(), "ext": cnode.ext_combo.currentText()})
                elif isinstance(cnode, CanvasImageNodeProxy):
                    c_data.update({"type": "Image", "file_path": cnode.file_path})
                elif isinstance(cnode, CanvasConstructorNodeProxy):
                    c_data.update({"type": "Constructor"})
                elif isinstance(cnode, CanvasOutputNodeProxy):
                    c_data.update({"type": "Output Window"})
                elif isinstance(cnode, CanvasFloatingFuncProxy):
                    c_data.update({"type": "FloatingFunc", "func_data": cnode.func_data, "ntype": cnode.ntype, "params": {k: v.text() for k, v in cnode.param_inputs.items()}})
                canvas_state.append(c_data)
            state["canvas_nodes"] = canvas_state
            
            conns = []
            for p1, p2 in getattr(self, 'canvas_connections', []):
                conns.append({"out_node": p1.parent_node.elem_id, "out_role": p1.role, "in_node": p2.parent_node.elem_id, "in_role": p2.role})
            state["canvas_connections"] = conns
            
            with open(file_path, "w") as f:
                json.dump(state, f, indent=4)
                
            self.statusBar().showMessage(f"💾 Project saved successfully to: {os.path.basename(file_path)}", 4000)
            
            # ⚠️ TAB SE '*' HATANA (Saved indicator)
            idx = self.tab_bar.currentIndex()
            if idx >= 0:
                file_name = os.path.basename(file_path).replace('.json', '')
                self.tab_bar.setTabText(idx, f"{file_name} [{'App' if not is_node_mode else 'Node'}]")
            
            self.is_modified = False
            if tab_id != -1:
                self.projects_data[tab_id]["is_modified"] = False
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{str(e)}")
            return False
        finally:
            # 🚀 CURSOR WAPAS NORMAL KARNA (Guaranteed execution via finally block)
            QApplication.restoreOverrideCursor()

    def save_project_as(self):
        is_node_mode = getattr(self, 'current_mode', 'app_builder') == "node_editor"
        if not self.current_project and not is_node_mode: return False

        if self.current_project:
            default_name = self.current_project.app_data.get('app_name', 'Untitled_App')
        else:
            idx = self.tab_bar.currentIndex()
            default_name = self.tab_bar.tabText(idx).split(" [")[0].replace("*", "") if idx >= 0 else "Node_Project"
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Project As", f"{default_name}.json", "JSON Files (*.json)")
        if path:
            tab_id = getattr(self, 'current_tab_id', -1)
            if tab_id != -1:
                self.projects_data[tab_id]["file_path"] = path
            return self._execute_save_to_path(path)
        return False

    def _execute_save_to_path(self, file_path):
        # 🚀 MOUSE CURSOR OVERRIDE (Busy / Wait Cursor start)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents() # UI ko turant refresh karega taaki cursor change feel ho
        try:
            is_node_mode = getattr(self, 'current_mode', 'app_builder') == "node_editor"
            state = {}
            if self.current_project:
                state = self.current_project.get_project_state()
                for el_state in state.get("elements", []):
                    for en in self.element_nodes:
                        if en.element_ref.elem_id == el_state["elem_id"]:
                            el_state["node_x"] = en.pos().x()
                            el_state["node_y"] = en.pos().y()
            else:
                state = {"app_name": os.path.basename(file_path).split('.')[0], "project_mode": "node_editor", "elements": []}

            state["main_functions"] = [{"func_name": mf.func_name, "input_linked_id": mf.input_linked_id, "console_linked_id": mf.console_linked_id, "x": mf.pos().x(), "y": mf.pos().y(), "width": mf.widget.width(), "height": mf.widget.height(), "tree_state": mf.extract_tree_state()} for mf in self.main_function_nodes]
            state["master_pipelines"] = [{"func_name": mp.func_name, "input_linked_id": mp.input_linked_id, "console_linked_id": mp.console_linked_id, "x": mp.pos().x(), "y": mp.pos().y(), "width": mp.widget.width(), "height": mp.widget.height(), "sequence": mp.get_sequence()} for mp in self.master_pipeline_nodes]
            state["code_nodes"] = [
                {"type": "global_ide" if isinstance(cn, GlobalIDEProxy) else "code_node", "elem_id": cn.elem_id, "x": cn.pos().x(), "y": cn.pos().y(), "width": cn.widget.width(), "height": cn.widget.height(), "code_text": cn.editor.toPlainText()} 
                for cn in self.code_nodes
            ]
            
            canvas_state = []
            for cnode in getattr(self, 'canvas_nodes', []):
                c_data = {
                    "elem_id": cnode.elem_id, "x": cnode.pos().x(), "y": cnode.pos().y(),
                    "width": cnode.widget.width(), "height": cnode.widget.height()
                }
                if isinstance(cnode, CanvasListNodeProxy):
                    c_data.update({"type": "List", "path": cnode.path_input.text(), "ext": cnode.ext_combo.currentText()})
                elif isinstance(cnode, CanvasImageNodeProxy):
                    c_data.update({"type": "Image", "file_path": cnode.file_path})
                elif isinstance(cnode, CanvasConstructorNodeProxy):
                    c_data.update({"type": "Constructor"})
                elif isinstance(cnode, CanvasOutputNodeProxy):
                    c_data.update({"type": "Output Window"})
                elif isinstance(cnode, CanvasFloatingFuncProxy):
                    c_data.update({"type": "FloatingFunc", "func_data": cnode.func_data, "ntype": cnode.ntype, "params": {k: v.text() for k, v in cnode.param_inputs.items()}})
                canvas_state.append(c_data)
            state["canvas_nodes"] = canvas_state
            
            conns = []
            for p1, p2 in getattr(self, 'canvas_connections', []):
                conns.append({"out_node": p1.parent_node.elem_id, "out_role": p1.role, "in_node": p2.parent_node.elem_id, "in_role": p2.role})
            state["canvas_connections"] = conns
            
            with open(file_path, "w") as f:
                json.dump(state, f, indent=4)
                
            self.statusBar().showMessage(f"💾 Project saved successfully to: {os.path.basename(file_path)}", 4000)
            
            idx = self.tab_bar.currentIndex()
            if idx >= 0:
                file_name = os.path.basename(file_path).replace('.json', '')
                self.tab_bar.setTabText(idx, f"{file_name} [{'App' if not is_node_mode else 'Node'}]")
            
            self.is_modified = False
            tab_id = getattr(self, 'current_tab_id', -1)
            if tab_id != -1:
                self.projects_data[tab_id]["is_modified"] = False
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{str(e)}")
            return False
        finally:
            # 🚀 CURSOR WAPAS NORMAL KARNA (Guaranteed execution via finally block)
            QApplication.restoreOverrideCursor()

    def closeEvent(self, event):
        any_unsaved = False
        # Saare tabs check karega ki koi unsaved toh nahi
        for tab_id, tdata in getattr(self, 'projects_data', {}).items():
            is_mod = self.is_modified if self.current_tab_id == tab_id else tdata.get("is_modified", False)
            if is_mod:
                any_unsaved = True
                break
                
        if any_unsaved:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "Aapke kuch projects mein unsaved changes hain.\nKya aap exit karne se pehle save karna chahte hain?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Save:
                # Jo bhi tab unsaved hai usko samne laakar save karega
                for i in range(self.tab_bar.count()):
                    tab_id = self.tab_bar.tabData(i)
                    if not tab_id: continue
                    is_mod = self.is_modified if self.current_tab_id == tab_id else self.projects_data[tab_id].get("is_modified", False)
                    if is_mod:
                        self.tab_bar.setCurrentIndex(i)
                        if not self.save_project():
                            event.ignore()
                            return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()
    
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "r") as f:
                    project_state = json.load(f)
                
                # Naye canvas data ko JSON se nikalna
                geometry = project_state.pop("geometry", None)
                elements = project_state.pop("elements", [])
                main_functions = project_state.pop("main_functions", [])
                master_pipelines = project_state.pop("master_pipelines", [])
                code_nodes_data = project_state.pop("code_nodes", [])
                canvas_nodes_data = project_state.pop("canvas_nodes", [])
                canvas_connections_data = project_state.pop("canvas_connections", [])
                
                self.spawn_workspace(project_state, geometry=geometry, elements=elements)
                
                # ⚠️ NAYA: File Path memory mein store karna taaki Ctrl+S silent rahe
                if getattr(self, 'current_tab_id', -1) != -1:
                    self.projects_data[self.current_tab_id]["file_path"] = file_path
                    self.projects_data[self.current_tab_id]["is_modified"] = False
                    self.is_modified = False
                
                for cn_data in code_nodes_data:
                    # ⚠️ FIX: Orange aur Green ko alag-alag pehchanna
                    if cn_data.get("type") == "global_ide":
                        cn = self.spawn_global_ide(cn_data["elem_id"], cn_data["x"], cn_data["y"], cn_data.get("code_text"), record=False)
                    else:
                        cn = self.spawn_code_node(cn_data["elem_id"], cn_data["x"], cn_data["y"], cn_data.get("code_text"), record=False)
                    
                    if cn: cn.widget.resize(cn_data.get("width", 480), cn_data.get("height", 380))
                
                for mf in main_functions:
                    self.spawn_main_function_node(
                        x=mf["x"], y=mf["y"], w=mf["width"], h=mf["height"],
                        func_name=mf["func_name"], input_linked_id=mf["input_linked_id"],
                        console_linked_id=mf["console_linked_id"], tree_state=mf["tree_state"], record=False
                    )
                for mp in master_pipelines:
                    self.spawn_master_pipeline_node(
                        x=mp["x"], y=mp["y"], w=mp["width"], h=mp["height"],
                        func_name=mp["func_name"], input_linked_id=mp["input_linked_id"],
                        console_linked_id=mp["console_linked_id"], sequence=mp.get("sequence", []), record=False
                    )

                # ⚠️ NAYA: Spawning Canvas Nodes (List, Image, etc.)
                if not hasattr(self, 'canvas_nodes'): self.canvas_nodes = []
                for cdata in canvas_nodes_data:
                    ctype = cdata.get("type")
                    node = None
                    if ctype == "List":
                        node = CanvasListNodeProxy(self, cdata["x"], cdata["y"])
                        node.path_input.setText(cdata.get("path", ""))
                        node.ext_combo.setCurrentText(cdata.get("ext", ".*"))
                        if cdata.get("path"): node.load_directory()
                    elif ctype == "Image":
                        node = CanvasImageNodeProxy(self, cdata["x"], cdata["y"])
                        node.file_path = cdata.get("file_path", "")
                        if node.file_path: node.load_image()
                    elif ctype == "Constructor":
                        node = CanvasConstructorNodeProxy(self, cdata["x"], cdata["y"])
                    elif ctype == "Output Window":
                        node = CanvasOutputNodeProxy(self, cdata["x"], cdata["y"])
                    elif ctype == "FloatingFunc":
                        node = CanvasFloatingFuncProxy(self, cdata.get("func_data", {}), cdata.get("ntype", "Func"), cdata["x"], cdata["y"])
                        for k, v in cdata.get("params", {}).items():
                            if k in node.param_inputs: node.param_inputs[k].setText(v)
                            
                    if node:
                        node.elem_id = cdata.get("elem_id", node.elem_id)
                        node.widget.resize(cdata.get("width", node.widget.width()), cdata.get("height", node.widget.height()))
                        self.node_scene.addItem(node)
                        self.canvas_nodes.append(node)
                
                # ⚠️ NAYA: Wires/Connections Restore logic
                if not hasattr(self, 'canvas_connections'): self.canvas_connections = []
                for conn in canvas_connections_data:
                    out_n = next((n for n in self.canvas_nodes if n.elem_id == conn["out_node"]), None)
                    in_n = next((n for n in self.canvas_nodes if n.elem_id == conn["in_node"]), None)
                    if out_n and in_n:
                        def get_port(n, role, is_out):
                            for attr in dir(n):
                                val = getattr(n, attr)
                                if isinstance(val, PortItem) and val.role == role and val.is_out == is_out: return val
                            return None
                        p1 = get_port(out_n, conn["out_role"], True)
                        p2 = get_port(in_n, conn["in_role"], False)
                        if p1 and p2: self.canvas_connections.append((p1, p2))

                self.node_scene.update()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project:\n{str(e)}")

    def preview_app(self):
        if not self.current_project: return
        state = self.current_project.get_project_state()
        state["main_functions"] = [{"func_name": mf.func_name, "input_linked_id": mf.input_linked_id, "console_linked_id": mf.console_linked_id, "tree_state": mf.extract_tree_state()} for mf in self.main_function_nodes]
        state["master_pipelines"] = [{"func_name": mp.func_name, "input_linked_id": mp.input_linked_id, "console_linked_id": mp.console_linked_id, "sequence": mp.get_sequence()} for mp in self.master_pipeline_nodes]
        state["code_nodes"] = [{"elem_id": cn.elem_id, "code_text": cn.editor.toPlainText()} for cn in self.code_nodes]
        
        def get_all_loop_names(nodes):
            names = []
            for n in nodes:
                ntype = n["node_data"].get("type", "")
                if ntype in ["Directory Loop", "File Loop", "Smart Filter Loop"]:
                    nm = n["node_data"].get("params", {}).get("loop_name")
                    if nm: names.append(nm.replace(" ", "_"))
                if n.get("children"):
                    names.extend(get_all_loop_names(n["children"]))
            return names

        for mf in state.get("main_functions", []):
            mf["all_loops"] = get_all_loop_names(mf.get("tree_state", []))

        code = self.generate_app_code(state)
        temp_dir = tempfile.gettempdir()
        
        functions_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "functions.py")
        if os.path.exists(functions_src):
            shutil.copy(functions_src, os.path.join(temp_dir, "functions.py"))
            
        ai_functions_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_functions.py")
        if os.path.exists(ai_functions_src):
            shutil.copy(ai_functions_src, os.path.join(temp_dir, "ai_functions.py"))

        custom_code_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customCode.py")
        if os.path.exists(custom_code_src):
            shutil.copy(custom_code_src, os.path.join(temp_dir, "customCode.py"))
            
        preview_script = os.path.join(temp_dir, "app_builder_quick_preview.py")
        with open(preview_script, "w", encoding="utf-8") as f:
            f.write(code)
        subprocess.Popen([sys.executable, preview_script])

    def publish_app(self):
        if not self.current_project: return
        temp_dir = tempfile.gettempdir()
        project_dir = os.path.dirname(os.path.abspath(__file__))

        state = self.current_project.get_project_state()
        state["main_functions"] = [{"func_name": mf.func_name, "input_linked_id": mf.input_linked_id, "console_linked_id": mf.console_linked_id, "tree_state": mf.extract_tree_state()} for mf in self.main_function_nodes]
        state["master_pipelines"] = [{"func_name": mp.func_name, "input_linked_id": mp.input_linked_id, "console_linked_id": mp.console_linked_id, "sequence": mp.get_sequence()} for mp in self.master_pipeline_nodes]
        state["code_nodes"] = [{"elem_id": cn.elem_id, "code_text": cn.editor.toPlainText()} for cn in self.code_nodes]
        
        def get_all_loop_names(nodes):
            names = []
            for n in nodes:
                ntype = n["node_data"].get("type", "")
                if ntype in ["Directory Loop", "File Loop", "Smart Filter Loop"]:
                    nm = n["node_data"].get("params", {}).get("loop_name")
                    if nm: names.append(nm.replace(" ", "_"))
                if n.get("children"):
                    names.extend(get_all_loop_names(n["children"]))
            return names

        for mf in state.get("main_functions", []):
            mf["all_loops"] = get_all_loop_names(mf.get("tree_state", []))

        app_name = state.get("app_name", "PublishedApp").replace(" ", "_")
        script_path = os.path.join(temp_dir, f"{app_name}_main.py")
        
        # --- COPY BACKEND FILES TO TEMP DIR FOR EXE COMPILATION ---
        for fname in ["functions.py", "ai_functions.py", "customCode.py"]:
            src_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
            if os.path.exists(src_file):
                shutil.copy(src_file, os.path.join(temp_dir, fname))
        # ----------------------------------------------------------
        
        code = self.generate_app_code(state)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        icon_path = state.get("icon_path", "")
        compile_icon_path = icon_path
        
        if icon_path and os.path.exists(icon_path):
            if icon_path.lower().endswith(".png"):
                compile_icon_path = os.path.join(temp_dir, "temp_app_icon.ico")
                img = QImage(icon_path)
                img.save(compile_icon_path, "ICO")
        
        self.progress_dialog = QProgressDialog("Publishing App to Project Directory...\nThis may take 1-2 minutes. Please wait.", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Building Application")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()

        self.compile_thread = CompileThread(script_path, compile_icon_path, temp_dir, project_dir)
        self.compile_thread.finished.connect(self.on_compile_finished)
        self.compile_thread.start()

    def delete_code_node(self, cn):
        self.record_state()
        for mf in self.main_function_nodes:
            tree_root = mf.tree.invisibleRootItem()
            def search_tree(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    node_d = child.data(0, Qt.UserRole)
                    if node_d.get("params", {}).get("code_node_id") == cn.elem_id:
                        return child
                    found = search_tree(child)
                    if found: return found
                return None
            
            found_item = search_tree(tree_root)
            if found_item:
                p = found_item.parent()
                if p: p.removeChild(found_item)
                else: mf.tree.takeTopLevelItem(mf.tree.indexOfTopLevelItem(found_item))
        
        self.node_scene.removeItem(cn)
        if cn in self.code_nodes: self.code_nodes.remove(cn)
        if self.selected_code_node == cn: self.selected_code_node = None
        self.update_property_panel()
        self.node_scene.update()

    def universal_delete(self):
        deleted_something = False
        
        # 1. Agar Logic Tree ke andar ka loop ya function selected hai
        if self.selected_tree_item:
            self.delete_tree_item(self.selected_tree_item)
            deleted_something = True
            
        # 2. Agar koi Button, Input, Image aadi selected hai
        elif self.selected_elements:
            self.delete_selected_elements()
            deleted_something = True
            
        # 3. Agar Main Function Panel (Blue wala) selected hai
        elif self.selected_main_func:
            self.delete_main_func(self.selected_main_func)
            deleted_something = True
            
        # 4. Agar Master Pipeline (Orange wala) selected hai
        elif self.selected_master_pipe:
            self.delete_main_func(self.selected_master_pipe)
            deleted_something = True
            
        # 5. Agar Code Node (Green wala) selected hai
        elif self.selected_code_node:
            self.delete_code_node(self.selected_code_node)
            deleted_something = True
            
        # 6. Agar Canvas Node (ComfyUI List/Viewer aadi) selected hai
        elif getattr(self, 'selected_canvas_node', None):
            node = self.selected_canvas_node
            self.node_scene.removeItem(node)
            if node in getattr(self, 'canvas_nodes', []): 
                self.canvas_nodes.remove(node)
            self.selected_canvas_node = None
            deleted_something = True

        if deleted_something:
            self.handle_canvas_click_deselect()
            self.node_scene.update()

    def switch_workspace_mode(self, mode):
        # Agar mode change ho raha hai, toh canvas clear karne ki warning deni zaroori hai
        if self.current_mode != mode and len(self.node_scene.items()) > 0:
            reply = QMessageBox.question(self, "Clear Canvas?", "Switching modes will clear your current canvas. Continue?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return
            
            # Clean Canvas
            self.node_scene.clear()
            if hasattr(self, 'canvas_nodes'): self.canvas_nodes.clear()
            if hasattr(self, 'canvas_connections'): self.canvas_connections.clear()
            self.element_nodes.clear()
            self.main_function_nodes.clear()
            self.code_nodes.clear()
            self.update_property_panel()
            
        self.current_mode = mode
        self.current_mode = mode
        if mode == "app_builder":
            self.app_mode_widget.setVisible(True)
            self.node_mode_widget.setVisible(False)
            # Add these 3 lines:
            self.btn_ide.setVisible(True)
            self.btn_main.setVisible(True)
            self.btn_master.setVisible(True)
            QMessageBox.information(self, "Mode Changed", "Switched to 📱 App Builder Mode")
        else:
            self.app_mode_widget.setVisible(False)
            self.node_mode_widget.setVisible(True)
            # Add these 3 lines:
            self.btn_ide.setVisible(False)
            self.btn_main.setVisible(False)
            self.btn_master.setVisible(False)
            QMessageBox.information(self, "Mode Changed", "Switched to 🎨 Node Image Editor Mode")

    def spawn_canvas_node(self, elem_type):
        self.record_state()
        center = self.node_view.mapToScene(self.node_view.viewport().rect().center())
        
        if elem_type == "List":
            node = CanvasListNodeProxy(self, center.x() - 300, center.y() - 250)
        elif elem_type == "Image":
            node = CanvasImageNodeProxy(self, center.x() - 300, center.y() - 100)
        elif elem_type == "Constructor":
            node = CanvasConstructorNodeProxy(self, center.x(), center.y() - 150)
        elif elem_type == "Output Window":
            node = CanvasOutputNodeProxy(self, center.x() + 300, center.y() - 200)
        else:
            QMessageBox.information(self, "Upcoming Feature", f"'{elem_type}' Node UI is under development.")
            return

        self.node_scene.addItem(node)
        
        # ⚠️ YEH LINE MISSING THI (Isi se memory me register hoke save hota hai)
        if not hasattr(self, 'canvas_nodes'): self.canvas_nodes = []
        self.canvas_nodes.append(node) 
        
        self.handle_canvas_node_selection(node)
        self.node_scene.update()

    def spawn_floating_logic_node(self, func_data, ntype, x=None, y=None):
        self.record_state()
        if x is None:
            center = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            x, y = center.x() + 50, center.y() - 300
            
        node = CanvasFloatingFuncProxy(self, func_data, ntype, x, y)
        self.node_scene.addItem(node)
        
        # ⚠️ YEH LINE BHI MISSING THI
        if not hasattr(self, 'canvas_nodes'): self.canvas_nodes = []
        self.canvas_nodes.append(node) 
        
        self.handle_canvas_node_selection(node)
        self.node_scene.update()

    def generate_app_code(self, state):
        app_name = state.get("app_name", "My App")
        version = state.get("version", "1.0.0")
        icon_path = state.get("icon_path", "")
        geom = state.get("geometry", {"width": 650, "height": 500})
        width, height = geom["width"], geom["height"]

        icon_setup = f'self.setWindowIcon(QIcon(r"{icon_path}"))' if icon_path and os.path.exists(icon_path) else ""
        has_image = any(el["type"] == "Image" for el in state.get("elements", []))

        rounded_image_class = """
class StreamRedirector(QObject):
    text_written = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.mute = False
    def write(self, text):
        if not self.mute:
            if text.strip() or text == '\\n':
                self.text_written.emit(str(text))
    def flush(self): pass
    def isatty(self): return True
    def fileno(self): return 1

def get_alpha_count(n):
    if n <= 0: return ''
    res = ''
    while n > 0:
        n, rem = divmod(n - 1, 26)
        res = chr(97 + rem) + res
    return res

class RoundedImage(QLabel):
    def __init__(self, parent=None, radius=0, border_width=0):
        super().__init__(parent)
        self.radius = radius; self.border_width = border_width; self.pixmap_path = ""
    def setPixmapPath(self, path):
        self.pixmap_path = path; self.update()
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap_path:
            from PyQt5.QtGui import QPainter, QPainterPath, QPixmap
            from PyQt5.QtCore import Qt
            painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath(); bw = self.border_width
            path.addRoundedRect(bw, bw, self.width() - 2*bw, self.height() - 2*bw, max(0, self.radius - bw), max(0, self.radius - bw))
            painter.setClipPath(path); pixmap = QPixmap(self.pixmap_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
""" if has_image else """
class StreamRedirector(QObject):
    text_written = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.mute = False
    def write(self, text):
        if not self.mute:
            if text.strip() or text == '\\n':
                self.text_written.emit(str(text))
    def flush(self): pass
    def isatty(self): return True
    def fileno(self): return 1

def get_alpha_count(n):
    if n <= 0: return ''
    res = ''
    while n > 0:
        n, rem = divmod(n - 1, 26)
        res = chr(97 + rem) + res
    return res
"""

        ui_elements_code = ""
        connections_code = ""
        logic_code = ""

        inputs_by_button = {}
        for el in state.get("elements", []):
            if el["type"] in ["Input Text Field"] and el.get("connected_button_id") not in ["None", "", None]:
                btn_id = el["connected_button_id"]
                if btn_id not in inputs_by_button: inputs_by_button[btn_id] = []
                inputs_by_button[btn_id].append(el["elem_id"])

        for el in state.get("elements", []):
            e_type = el["type"]; text = el.get("text", "").replace("'", "\\'")
            x, y, w, h = el["x"], el["y"], el["width"], el["height"]
            bg_style = el.get("bg_color", "#007acc") if el.get("has_fill", True) else "transparent"
            text_color = el.get("text_color", "#ffffff")
            radius = el.get("radius", 4); b_width = el.get("border_width", 1); b_color = el.get("border_color", "#555555")
            font_size = el.get("font_size", 12); alignment = el.get("alignment", "Center")
            var_name = el["elem_id"]
            
            align_css = f"text-align: {alignment.lower()};" if e_type == "Button" else ""
            font_family = "Arial"
            style = f"background-color: {bg_style}; color: {text_color}; border-radius: {radius}px; border: {b_width}px solid {b_color}; font-size: {font_size}px; font-weight: bold; font-family: {font_family}; {align_css}"
            
            if e_type == "Button":
                ui_elements_code += f"        self.{var_name} = QPushButton('{text}', self)\n"
                action = str(el.get("button_action", "None")).strip()
                if action != "None":
                    connections_code += f"        self.{var_name}.clicked.connect(self.action_{var_name})\n"
                    if action in ["Select File", "Select Directory"]:
                        logic_code += f"    def action_{var_name}(self):\n"
                        if action == "Select File":
                            logic_code += f"        path, _ = QFileDialog.getOpenFileName(self, 'Select File')\n"
                            logic_code += f"        if path:\n"
                            if var_name in inputs_by_button:
                                for inp_id in inputs_by_button[var_name]: 
                                    logic_code += f"            self.{inp_id}.setText(path)\n"
                            else: logic_code += f"            pass\n"
                        elif action == "Select Directory":
                            logic_code += f"        path = QFileDialog.getExistingDirectory(self, 'Select Directory')\n"
                            logic_code += f"        if path:\n"
                            if var_name in inputs_by_button:
                                for inp_id in inputs_by_button[var_name]: 
                                    logic_code += f"            self.{inp_id}.setText(path)\n"
                            else: logic_code += f"            pass\n"
                        logic_code += "\n"
                    else:
                        clean_action = action.replace(" ", "_")
                        logic_code += f"    def action_{var_name}(self):\n"
                        logic_code += f"        self.{clean_action}()\n\n"

            elif e_type == "Label": ui_elements_code += f"        self.{var_name} = QLabel('{text}', self)\n"
            elif e_type == "Static Text": ui_elements_code += f"        self.{var_name} = QLabel('{text}', self)\n"
            elif e_type == "Input Text Field":
                ui_elements_code += f"        self.{var_name} = QLineEdit(self)\n        self.{var_name}.setPlaceholderText('{text}')\n"
            elif e_type == "Dropdown":
                opts_list = [repr(o.strip()) for o in el.get("dropdown_options", "").split(",") if o.strip()]
                ui_elements_code += f"        self.{var_name} = QComboBox(self)\n"
                ui_elements_code += f"        self.{var_name}.addItems([{', '.join(opts_list)}])\n"
            elif e_type == "Console":
                ui_elements_code += f"        self.{var_name} = QTextEdit(self)\n        self.{var_name}.setReadOnly(True)\n        self.{var_name}.setText('> System Ready...\\n')\n"
                ui_elements_code += f"        self._consoles.append(self.{var_name})\n"
            elif e_type == "Plain Text Edit":
                ui_elements_code += f"        self.{var_name} = QTextEdit(self)\n        self.{var_name}.setPlainText('{text}')\n"
            elif e_type == "Image":
                ui_elements_code += f"        self.{var_name} = RoundedImage(self, radius={radius}, border_width={b_width})\n"
                img_path = el.get("image_path", "").replace("\\", "/")
                if img_path: ui_elements_code += f"        self.{var_name}.setPixmapPath('{img_path}')\n"
            
            ui_elements_code += f"        self.{var_name}.setGeometry({x}, {y}, {w}, {h})\n        self.{var_name}.setStyleSheet('{style}')\n"
            
            if e_type in ["Label", "Static Text", "Input Text Field", "Console", "Dropdown"]:
                if alignment == "Left": align_flag = "Qt.AlignLeft | Qt.AlignVCenter" if e_type not in ["Console"] else "Qt.AlignLeft"
                elif alignment == "Right": align_flag = "Qt.AlignRight | Qt.AlignVCenter" if e_type not in ["Console"] else "Qt.AlignRight"
                else: align_flag = "Qt.AlignHCenter | Qt.AlignVCenter" if e_type not in ["Console"] else "Qt.AlignHCenter"
                if e_type != "Dropdown":
                    ui_elements_code += f"        self.{var_name}.setAlignment({align_flag})\n"
            ui_elements_code += "\n"

        def recurse_tree(nodes, indent_lvl, con_id, active_loop_names, current_count_var="0"):
            code = ""
            ind = "    " * indent_lvl
            
            for idx, node in enumerate(nodes):
                ntype = node["node_data"].get("type", "")
                params = node["node_data"].get("params", {})
                do_log = params.get("log_console", True)
                            
                if ntype == "Smart Filter Loop":
                    loop_name = params.get("loop_name", f"smart_{indent_lvl}_{idx}").replace(" ", "_")
                    target_val = params.get("target_dir", "current_dir").strip()
                    target_type = params.get("target_type", "Files")
                    ext_filter = params.get("ext_filter", "").strip()
                    name_exact = params.get("name_exact", "").strip()
                    name_contains = params.get("name_contains", "").strip()
                    exclude_str = params.get("exclude_contains", "").strip()

                    if target_val == "current_dir": eval_target = "current_dir"
                    elif target_val == "dir_root": eval_target = "dir_root"
                    elif target_val.startswith("self."): 
                        clean_tgt = target_val if ".text()" in target_val or ".currentText()" in target_val else f"{target_val}.text().strip()"
                        eval_target = clean_tgt
                    elif target_val in active_loop_names: eval_target = target_val
                    else: eval_target = f"r'{target_val}'"

                    c_var = f"{loop_name}_count"
                    code += f"{ind}{c_var} = 0\n"
                    
                    if do_log:
                        code += f"{ind}print(f'\\n🔍 [SMART SCAN] Path: {{{eval_target}}} | Type: {target_type}')\n"
                        
                    code += f"{ind}if {eval_target} and os.path.exists({eval_target}):\n"
                    code += f"{ind}    try:\n"
                    code += f"{ind}        for root_{loop_name}, dirs_{loop_name}, files_{loop_name} in os.walk({eval_target}):\n"
                    code += f"{ind}            items_{loop_name} = []\n"
                    if target_type in ["Directories", "Both"]:
                        code += f"{ind}            items_{loop_name}.extend([(d, True) for d in dirs_{loop_name}])\n"
                    if target_type in ["Files", "Both"]:
                        code += f"{ind}            items_{loop_name}.extend([(f, False) for f in files_{loop_name}])\n"
                        
                    code += f"{ind}            for name_{loop_name}, is_dir_{loop_name} in items_{loop_name}:\n"
                    inner_ind = ind + "                "
                    
                    if exclude_str:
                        safe_exc = exclude_str.replace("'", "\\'")
                        code += f"{inner_ind}if '{safe_exc}'.lower() in name_{loop_name}.lower():\n"
                        if do_log:
                            code += f"{inner_ind}    print(f'   ⏭️ [SKIPPED] {{name_{loop_name}}} (Matches Exclude)')\n"
                        code += f"{inner_ind}    continue\n"
                    
                    if name_exact:
                        code += f"{inner_ind}if name_{loop_name}.lower() != r'{name_exact}'.lower(): continue\n"
                    if name_contains:
                        code += f"{inner_ind}if r'{name_contains}'.lower() not in name_{loop_name}.lower(): continue\n"
                    if ext_filter and target_type in ["Files", "Both"]:
                        ext_list = [e.replace("*", "").replace(".", "").strip().lower() for e in ext_filter.split(",") if e.replace("*", "").replace(".", "").strip()]
                        if ext_list:
                            ext_tuple_str = f"({', '.join(repr('.' + e) for e in ext_list)})"
                            if len(ext_list) == 1:
                                ext_tuple_str = f"({repr('.' + ext_list[0])},)"
                            code += f"{inner_ind}if not is_dir_{loop_name} and not name_{loop_name}.lower().endswith({ext_tuple_str}): continue\n"

                    code += f"{inner_ind}{c_var} += 1\n"
                    code += f"{inner_ind}{loop_name} = os.path.join(root_{loop_name}, name_{loop_name})\n"
                    code += f"{inner_ind}_prev_dir_{loop_name} = current_dir\n"
                    code += f"{inner_ind}if is_dir_{loop_name}:\n"
                    code += f"{inner_ind}    current_dir = {loop_name}\n"
                    code += f"{inner_ind}else:\n"
                    code += f"{inner_ind}    current_dir = root_{loop_name}\n"
                    code += f"{inner_ind}    file_path = {loop_name}\n"
                    
                    if do_log:
                        code += f"{inner_ind}print(f'   ┣━ 🎯 [SMART MATCH] {{{loop_name}}}')\n"
                    code += f"{inner_ind}QApplication.processEvents()\n"
                    
                    if node.get("children"):
                        code += recurse_tree(node["children"], len(inner_ind)//4, con_id, active_loop_names, c_var)
                        
                    code += f"{inner_ind}current_dir = _prev_dir_{loop_name}\n"
                    
                    code += f"{ind}    except Exception as e:\n"
                    if do_log:
                        code += f"{ind}        print(f'   ❌ [ERROR SCANNING] {{str(e)}}')\n"
                    else:
                        code += f"{ind}        pass\n"
                    code += f"{ind}else:\n"
                    if do_log:
                        code += f"{ind}    print(f'   ❌ [ERROR] Target path is invalid or empty: {{{eval_target}}}')\n"
                    else:
                        code += f"{ind}    pass\n"
                            
                elif ntype == "Directory Loop":
                    loop_name = params.get("loop_name", f"dir_{indent_lvl}_{idx}").replace(" ", "_")
                    target_val = params.get("target_dir", "current_dir").strip()
                    exclude_str = params.get("exclude_contains", "").strip()
                    
                    if target_val == "current_dir": eval_target = "current_dir"
                    elif target_val == "dir_root": eval_target = "dir_root"
                    elif target_val.startswith("self."): 
                        clean_tgt = target_val if ".text()" in target_val or ".currentText()" in target_val else f"{target_val}.text().strip()"
                        eval_target = clean_tgt
                    elif target_val in active_loop_names: eval_target = target_val
                    else: eval_target = f"r'{target_val}'"

                    c_var = f"{loop_name}_count"
                    code += f"{ind}{c_var} = 0\n"
                    
                    if do_log:
                        code += f"{ind}print(f'\\n📂 [DIR LOOP] Initializing: {loop_name}')\n"
                        code += f"{ind}print(f'   ↳ Validating Target: {{{eval_target}}}')\n"
                        
                    code += f"{ind}if {eval_target} and os.path.exists({eval_target}) and os.path.isdir({eval_target}):\n"
                    if do_log:
                        code += f"{ind}    print(f'   ↳ Status: Found Directory! Scanning...')\n"
                        
                    code += f"{ind}    try:\n"
                    code += f"{ind}        for entry_{loop_name} in os.scandir({eval_target}):\n"
                    code += f"{ind}            if entry_{loop_name}.is_dir():\n"
                    inner_ind = ind + "                "
                    
                    if exclude_str:
                        safe_exc = exclude_str.replace("'", "\\'")
                        code += f"{inner_ind}if '{safe_exc}'.lower() in entry_{loop_name}.name.lower():\n"
                        if do_log:
                            code += f"{inner_ind}    print(f'   ⏭️ [SKIPPED DIR] {{entry_{loop_name}.name}} (Matches Exclude)')\n"
                        code += f"{inner_ind}    continue\n"
                        
                    code += f"{inner_ind}{c_var} += 1\n"
                    code += f"{inner_ind}{loop_name} = entry_{loop_name}.path\n"
                    code += f"{inner_ind}_prev_dir_{loop_name} = current_dir\n"
                    code += f"{inner_ind}current_dir = {loop_name}\n"
                    if do_log:
                        code += f"{inner_ind}print(f'   ┣━ 📁 [FOUND SUB-DIR] {{{loop_name}}}')\n"
                    code += f"{inner_ind}QApplication.processEvents()\n"
                    if node.get("children"):
                        code += recurse_tree(node["children"], indent_lvl + 4, con_id, active_loop_names, c_var)
                    code += f"{inner_ind}current_dir = _prev_dir_{loop_name}\n"
                    code += f"{ind}    except PermissionError:\n"
                    if do_log:
                        code += f"{ind}        print(f'   ❌ [PERMISSION DENIED] Skipping: {{{eval_target}}}')\n"
                    else:
                        code += f"{ind}        pass\n"
                    code += f"{ind}else:\n"
                    if do_log:
                        code += f"{ind}    print(f'   ❌ [ERROR] Target path is invalid or empty: {{{eval_target}}}')\n"
                    else:
                        code += f"{ind}    pass\n"

                elif ntype == "File Loop":
                    loop_name = params.get("loop_name", f"file_{indent_lvl}_{idx}").replace(" ", "_")
                    target_val = params.get("target_dir", "current_dir").strip()
                    exclude_str = params.get("exclude_contains", "").strip()
                    
                    if target_val == "current_dir": eval_target = "current_dir"
                    elif target_val == "dir_root": eval_target = "dir_root"
                    elif target_val.startswith("self."): 
                        clean_tgt = target_val if ".text()" in target_val or ".currentText()" in target_val else f"{target_val}.text().strip()"
                        eval_target = clean_tgt
                    elif target_val in active_loop_names: eval_target = target_val
                    else: eval_target = f"r'{target_val}'"

                    ext = params.get("ext", "*.*")
                    if ext == "*.*" or ext.strip() == "*" or ext.strip() == "":
                        safe_ext = ""
                    else:
                        safe_ext = ext.replace("*", "").strip()
                    
                    c_var = f"{loop_name}_count"
                    code += f"{ind}{c_var} = 0\n"
                    
                    if do_log:
                        code += f"{ind}print(f'\\n📄 [FILE LOOP] Initializing: {loop_name}')\n"
                        code += f"{ind}print(f'   ↳ Validating Target: {{{eval_target}}} | Ext Filter: {ext if ext else 'ALL'}')\n"
                        
                    code += f"{ind}if {eval_target} and os.path.exists({eval_target}) and os.path.isdir({eval_target}):\n"
                    if do_log:
                        code += f"{ind}    print(f'   ↳ Status: Found Directory! Scanning for files...')\n"
                        
                    code += f"{ind}    try:\n"
                    code += f"{ind}        for entry_{loop_name} in os.scandir({eval_target}):\n"
                    code += f"{ind}            if entry_{loop_name}.is_file():\n"
                    inner_ind = ind + "                "
                    
                    if exclude_str:
                        safe_exc = exclude_str.replace("'", "\\'")
                        code += f"{inner_ind}if '{safe_exc}'.lower() in entry_{loop_name}.name.lower():\n"
                        if do_log:
                            code += f"{inner_ind}    print(f'   ⏭️ [SKIPPED FILE] {{entry_{loop_name}.name}} (Matches Exclude)')\n"
                        code += f"{inner_ind}    continue\n"
                    
                    if not safe_ext:
                        code += f"{inner_ind}{c_var} += 1\n"
                        code += f"{inner_ind}{loop_name} = entry_{loop_name}.path\n"
                        code += f"{inner_ind}file_path = {loop_name}\n"
                        if do_log:
                            code += f"{inner_ind}print(f'   ┣━ 📝 [FOUND FILE] {{{loop_name}}}')\n"
                        code += f"{inner_ind}QApplication.processEvents()\n"
                        if node.get("children"):
                            code += recurse_tree(node["children"], len(inner_ind)//4, con_id, active_loop_names, c_var)
                    else:
                        ext_list = [e.replace(".", "").strip().lower() for e in safe_ext.split(",")]
                        ext_tuple_str = f"({', '.join(repr('.' + e) for e in ext_list)})"
                        if len(ext_list) == 1:
                            ext_tuple_str = f"({repr('.' + ext_list[0])},)"
                            
                        code += f"{inner_ind}if entry_{loop_name}.name.lower().endswith({ext_tuple_str}):\n"
                        inner_ind += "    "
                        code += f"{inner_ind}{c_var} += 1\n"
                        code += f"{inner_ind}{loop_name} = entry_{loop_name}.path\n"
                        code += f"{inner_ind}file_path = {loop_name}\n"
                        if do_log:
                            code += f"{inner_ind}print(f'   ┣━ 📝 [MATCHED FILE] {{{loop_name}}}')\n"
                        code += f"{inner_ind}QApplication.processEvents()\n"
                        if node.get("children"):
                            code += recurse_tree(node["children"], len(inner_ind)//4, con_id, active_loop_names, c_var)
                            
                    code += f"{ind}    except PermissionError:\n"
                    if do_log:
                        code += f"{ind}        print(f'   ❌ [PERMISSION DENIED] Skipping: {{{eval_target}}}')\n"
                    else:
                        code += f"{ind}        pass\n"
                    code += f"{ind}else:\n"
                    if do_log:
                        code += f"{ind}    print(f'   ❌ [ERROR] Target path is invalid or empty: {{{eval_target}}}')\n"
                    else:
                        code += f"{ind}    pass\n"

                elif ntype.startswith("Func:") or ntype.startswith("AI:") or ntype.startswith("Custom:"):
                    is_ai = ntype.startswith("AI:")
                    is_custom = ntype.startswith("Custom:")
                    func_n = ntype.split(": ")[1]
                    module_name = "ai_functions" if is_ai else ("customCode" if is_custom else "functions")
                    formatted_args = []
                    
                    for k, v in params.items():
                        if k == "log_console": continue
                        
                        if k == "code_text" and func_n == "run_custom_user_code":
                            continue
                        
                        if k == "code_node_id" and func_n == "run_custom_user_code":
                            code_txt = ""
                            for cn in state.get("code_nodes", []):
                                if cn["elem_id"] == v:
                                    code_txt = cn["code_text"]
                                    break
                            safe_code = code_txt.replace('"""', '\\"\\"\\"')
                            formatted_args.append(f"code_text=\"\"\"{safe_code}\"\"\"")
                            continue
                            
                        v_str = str(v).strip()
                        is_fstring = False
                        
                        if "{num_count}" in v_str:
                            v_str = v_str.replace("{num_count}", f"{{{current_count_var}}}")
                            is_fstring = True
                        if "{alpha_count}" in v_str:
                            v_str = v_str.replace("{alpha_count}", f"{{get_alpha_count({current_count_var})}}")
                            is_fstring = True
                        if re.search(r'\{rand_num_(\d+)\}', v_str):
                            v_str = re.sub(r'\{rand_num_(\d+)\}', r"{''.join(random.choices(string.digits, k=\1))}", v_str)
                            is_fstring = True
                        if re.search(r'\{rand_alpha_(\d+)\}', v_str):
                            v_str = re.sub(r'\{rand_alpha_(\d+)\}', r"{''.join(random.choices(string.ascii_lowercase, k=\1))}", v_str)
                            is_fstring = True
                        if "{current_name}" in v_str:
                            v_str = v_str.replace("{current_name}", "{os.path.splitext(os.path.basename(file_path if 'file_path' in locals() else current_dir))[0]}")
                            is_fstring = True
                        if "{original_ext}" in v_str:
                            v_str = v_str.replace("{original_ext}", "{os.path.splitext(file_path if 'file_path' in locals() else current_dir)[1]}")
                            is_fstring = True
                        if "{current_dir_name}" in v_str:
                            v_str = v_str.replace("{current_dir_name}", "{os.path.basename(current_dir.rstrip(os.path.sep))}")
                            is_fstring = True
                        if "{current_dir}" in v_str: is_fstring = True
                        if "{dir_root}" in v_str: is_fstring = True
                        if "{preserve_structure}" in v_str:
                            v_str = v_str.replace("{preserve_structure}", "{os.path.relpath(current_dir, dir_root) if dir_root and os.path.abspath(current_dir).startswith(os.path.abspath(dir_root)) and os.path.relpath(current_dir, dir_root) != '.' else ''}")
                            is_fstring = True
                            
                        for l_name in active_loop_names:
                            macro = f"{{{l_name}_name}}"
                            if macro in v_str:
                                v_str = v_str.replace(macro, f"{{os.path.basename({l_name}.rstrip(os.path.sep))}}")
                                is_fstring = True
                        
                        if is_fstring:
                            formatted_args.append(f"{k}=f'{v_str}'")
                        elif v_str.startswith("self."):
                            clean_v = v_str if ".text()" in v_str or ".currentText()" in v_str or ".toPlainText()" in v_str else f"{v_str}.text().strip()"
                            formatted_args.append(f"{k}={clean_v}")
                        elif v_str in ["file_path", "current_dir", "dir_root"]:
                            formatted_args.append(f"{k}={v_str}")
                        elif v_str in active_loop_names:
                            formatted_args.append(f"{k}={v_str}")
                        elif v_str in ["None", "True", "False"] or v_str == "1":
                            formatted_args.append(f"{k}={v_str}")
                        else:
                            try:
                                float(v_str)
                                formatted_args.append(f"{k}={v_str}")
                            except ValueError:
                                safe_v = v_str.replace("'", "\\'")
                                formatted_args.append(f"{k}='{safe_v}'")
                    
                    args_str = ", ".join(formatted_args)
                    code += f"{ind}import {module_name}\n"
                    code += f"{ind}try:\n"
                    if not do_log:
                        code += f"{ind}    self.redirector.mute = True\n"
                    
                    if func_n == "run_custom_user_code":
                        code += f"{ind}    return_val_{idx} = {module_name}.{func_n}({args_str}, **locals())\n"
                    else:
                        code += f"{ind}    return_val_{idx} = {module_name}.{func_n}({args_str})\n"
                    
                    if not do_log:
                        code += f"{ind}    self.redirector.mute = False\n"
                    if do_log:
                        code += f"{ind}    print(f'   🟢 [SUCCESS] Executed {func_n} successfully.')\n"
                    code += f"{ind}except Exception as e:\n"
                    if not do_log:
                        code += f"{ind}    self.redirector.mute = False\n"
                    if do_log:
                        code += f"{ind}    print(f'   🛑 [ERROR] {func_n} failed: {{str(e)}}')\n"
                    else:
                        code += f"{ind}    pass\n"
                        
            return code

        for mp in state.get("master_pipelines", []):
            fname = mp["func_name"].replace(" ", "_")
            in_id = mp["input_linked_id"]
            con_id = mp["console_linked_id"]
            seq = mp["sequence"]
            
            logic_code += f"    def {fname}(self, override_dir=None):\n"
            if con_id != "None":
                logic_code += f"        print(f'\\n{'='*50}')\n"
                logic_code += f"        print(f'👑 [MASTER PIPELINE START] Executing: {fname}')\n"
                
            logic_code += f"        dir_root = ''\n"
            logic_code += f"        if override_dir:\n"
            logic_code += f"            dir_root = override_dir\n"
            if in_id != "None":
                logic_code += f"        elif hasattr(self, '{in_id}'):\n"
                logic_code += f"            dir_root = getattr(self.{in_id}, 'text', getattr(self.{in_id}, 'currentText', lambda: ''))().strip()\n"
            
            logic_code += f"        if not dir_root or not os.path.exists(dir_root):\n"
            logic_code += f"            return\n"
            logic_code += f"        dir_root = os.path.abspath(dir_root)\n\n"
            
            for s_func in seq:
                clean_sf = s_func.replace(" ", "_")
                if con_id != "None":
                    logic_code += f"        print(f'\\n▶️ [CALLING SUB-FUNCTION] -> {clean_sf}')\n"
                logic_code += f"        self.{clean_sf}(override_dir=dir_root)\n"
            logic_code += "\n"

        for mf in state.get("main_functions", []):
            fname = mf["func_name"].replace(" ", "_")
            in_id = mf["input_linked_id"]
            con_id = mf["console_linked_id"]
            active_loops = mf.get("all_loops", [])
            
            logic_code += f"    def {fname}(self, override_dir=None):\n"
            
            if con_id != "None":
                logic_code += f"        print(f'\\n{'='*50}')\n"
                logic_code += f"        print(f'🚀 [START] Executing Function: {fname}')\n"
            
            logic_code += f"        dir_root = ''\n"
            logic_code += f"        if override_dir is not None:\n"
            logic_code += f"            dir_root = override_dir\n"
            if in_id != "None":
                logic_code += f"        elif hasattr(self, '{in_id}'):\n"
                logic_code += f"            dir_root = getattr(self.{in_id}, 'text', getattr(self.{in_id}, 'currentText', lambda: ''))().strip()\n"
                if con_id != "None":
                    logic_code += f"            print(f'📥 [INPUT] Received path from UI: {{dir_root}}')\n"
            else:
                if con_id != "None":
                    logic_code += f"        elif not override_dir:\n"
                    logic_code += f"            print(f'⚠️ [WARNING] No Directory Input linked.')\n"
                
            logic_code += f"        if not dir_root or not os.path.exists(dir_root):\n"
            logic_code += f"            return\n"
            if con_id != "None":
                logic_code += f"        else:\n"
                logic_code += f"            dir_root = os.path.abspath(dir_root)\n"
                logic_code += f"            print(f'✅ [VALID] Root directory set to: {{dir_root}}')\n"
                
            logic_code += f"        current_dir = dir_root\n"
            logic_code += f"        QApplication.processEvents()\n"
            
            tree = mf.get("tree_state", [])
            if tree:
                logic_code += recurse_tree(tree, 2, con_id, active_loops)
            else:
                logic_code += f"        pass\n"
            logic_code += "\n"

        template = f"""import sys
import os
import random
import string
import traceback
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QMessageBox, QComboBox
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QIcon, QTextCursor, QPixmap, QPainter, QPainterPath

{rounded_image_class}

class PublishedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(r"{app_name} v{version}")
        self.resize({width}, {height})
        self.setStyleSheet("background-color: #1e1e1e;")
        {icon_setup}

        self._consoles = []
        self.redirector = StreamRedirector()
        self.redirector.text_written.connect(self._append_log)
        sys.stdout = self.redirector
        sys.stderr = self.redirector

        self.setup_ui()

    def _append_log(self, text):
        for console in self._consoles:
            console.moveCursor(QTextCursor.End)
            console.insertPlainText(text)
            console.ensureCursorVisible()
        QApplication.processEvents()

    def setup_ui(self):
{ui_elements_code if ui_elements_code.strip() else '        pass'}
{connections_code}

{logic_code if logic_code.strip() else ''}


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = PublishedApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        if not QApplication.instance():
            app = QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Fatal Crash Report")
        msg.setText("The application crashed due to an internal error!")
        msg.setDetailedText(traceback.format_exc())
        msg.exec_()
"""
        return template

    def spawn_canvas_node(self, elem_type):
        self.record_state()
        center = self.node_view.mapToScene(self.node_view.viewport().rect().center())
        
        if elem_type == "List":
            node = CanvasListNodeProxy(self, center.x() - 300, center.y() - 250)
        elif elem_type == "Image":
            node = CanvasImageNodeProxy(self, center.x() - 300, center.y() - 100)
        elif elem_type == "Constructor":
            node = CanvasConstructorNodeProxy(self, center.x(), center.y() - 150)
        elif elem_type == "Output Window":
            node = CanvasOutputNodeProxy(self, center.x() + 300, center.y() - 200)
        elif elem_type == "Plain Text Edit":
            node = CanvasTextNodeProxy(self, center.x(), center.y())
        else:
            QMessageBox.information(self, "Upcoming Feature", f"'{elem_type}' Node UI is under development.")
            return

        self.node_scene.addItem(node)
        
        # ⚠️ YEH DO LINES IMPORTANT HAIN
        if not hasattr(self, 'canvas_nodes'): self.canvas_nodes = []
        self.canvas_nodes.append(node) 
        
        # ⚠️ TAB MODIFIED STATUS ON KARNA
        self.is_modified = True
        if getattr(self, 'current_tab_id', -1) != -1 and self.current_tab_id in getattr(self, 'projects_data', {}):
            self.projects_data[self.current_tab_id]["is_modified"] = True
            
        self.handle_canvas_node_selection(node)
        self.node_scene.update()

    def spawn_floating_logic_node(self, func_data, ntype, x=None, y=None):
        self.record_state()
        if x is None:
            center = self.node_view.mapToScene(self.node_view.viewport().rect().center())
            x, y = center.x() + 50, center.y() - 300
            
        node = CanvasFloatingFuncProxy(self, func_data, ntype, x, y)
        self.node_scene.addItem(node)
        
        # ⚠️ YEH DO LINES IMPORTANT HAIN
        if not hasattr(self, 'canvas_nodes'): self.canvas_nodes = []
        self.canvas_nodes.append(node) 
        
        # ⚠️ TAB MODIFIED STATUS ON KARNA
        self.is_modified = True
        if getattr(self, 'current_tab_id', -1) != -1 and self.current_tab_id in getattr(self, 'projects_data', {}):
            self.projects_data[self.current_tab_id]["is_modified"] = True
            
        self.handle_canvas_node_selection(node)
        self.node_scene.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.Window, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.WindowText, Qt.white)
    dark_palette.setColor(dark_palette.Base, QColor(30, 30, 30))
    dark_palette.setColor(dark_palette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ToolTipBase, Qt.white)
    dark_palette.setColor(dark_palette.ToolTipText, Qt.white)
    dark_palette.setColor(dark_palette.Text, Qt.white)
    dark_palette.setColor(dark_palette.Button, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ButtonText, Qt.white)
    app.setPalette(dark_palette)

    window = AppBuilderWindow()
    window.show()
    sys.exit(app.exec_())