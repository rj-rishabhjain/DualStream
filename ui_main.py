import ctypes
import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QSlider, QPushButton, 
                             QFrame, QMessageBox, QSystemTrayIcon, QMenu)
from PyQt6.QtGui import QIcon, QAction, QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

try:
    ctypes.windll.ole32.CoInitialize(None)
except Exception:
    pass

CONFIG_FILE = "dualstream_history.json"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Background Worker Thread for Zero-Lag Startup ---
class AudioLoader(QThread):
    devices_loaded = pyqtSignal(list)
    
    def run(self):
        try:
            import soundcard as sc
            speakers = sc.all_speakers()
            self.devices_loaded.emit(speakers)
        except Exception:
            self.devices_loaded.emit([])

# --- Custom Widget for Instant Background Rendering ---
class BackgroundWidget(QWidget):
    def __init__(self, image_path):
        super().__init__()
        self.pixmap = None
        if os.path.exists(image_path):
            self.pixmap = QPixmap(image_path)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.pixmap and not self.pixmap.isNull():
            painter.drawPixmap(self.rect(), self.pixmap.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            painter.fillRect(self.rect(), QColor(15, 23, 42))

# --- Custom ComboBox to Show Popup clearly ---
class LockingComboBox(QComboBox):
    def __init__(self, is_primary, dashboard):
        super().__init__()
        self.is_primary = is_primary
        self.dashboard = dashboard

    def showPopup(self):
        if not self.is_primary and not self.dashboard.has_primary_selected():
            msg = QMessageBox(self.window())
            msg.setWindowTitle("Action Required")
            msg.setText("Please select the PRIMARY MASTER device first to unlock the secondary slots.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            return
        super().showPopup()

class DeviceSlot(QFrame):
    def __init__(self, title_text, dashboard, is_primary=False):
        super().__init__()
        self.is_primary = is_primary
        self.dashboard = dashboard
        self.setObjectName("PrimarySlot" if is_primary else "SecondarySlot")
        self.layout = QVBoxLayout()
        
        self.title = QLabel(title_text)
        self.title.setObjectName("SlotTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        self.device_dropdown = LockingComboBox(is_primary, dashboard)
        self.device_dropdown.addItem("-- Loading Devices... --")
        self.device_dropdown.setEnabled(False) 
        self.layout.addWidget(self.device_dropdown)

        self.layout.addWidget(QLabel("Volume Level:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.layout.addWidget(self.volume_slider)

        self.layout.addWidget(QLabel("Latency Fine-Tune (ms):"))
        self.delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_slider.setRange(0, 500)
        self.delay_slider.setValue(0)
        self.layout.addWidget(self.delay_slider)

        self.setLayout(self.layout)

    def populate_devices(self, speakers, saved_name=""):
        self.device_dropdown.clear()
        self.device_dropdown.addItem("-- Select Device --")
        for sp in speakers:
            self.device_dropdown.addItem(sp.name)
        
        self.device_dropdown.setEnabled(True)
        if saved_name:
            self.device_dropdown.setCurrentText(saved_name)

    def get_settings(self):
        device_name = self.device_dropdown.currentText()
        if device_name in ["-- Select Device --", "-- Loading Devices... --", ""]:
            return None
        return {
            'name': device_name,
            'role': 1 if self.is_primary else 0,
            'volume': self.volume_slider.value() / 100.0,
            'delay_ms': self.delay_slider.value()
        }

class DualStreamDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.router = None # Will be loaded lazily to prevent lag
        self.setWindowTitle("DUAL STREAM - Advanced Audio Router")
        self.setFixedSize(900, 600) 
        
        self.history_data = {}
        self.load_history_file()
        
        self.init_ui()
        self.init_system_tray()
        
        # Instantly show the UI, then load the heavy audio engines after 100ms
        self.show()
        QTimer.singleShot(100, self.lazy_load_backend)

    def lazy_load_backend(self):
        from core_engine import DualStreamRouter
        self.router = DualStreamRouter()
        self.audio_thread = AudioLoader()
        self.audio_thread.devices_loaded.connect(self.on_devices_loaded)
        self.audio_thread.start()

    def load_history_file(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.history_data = json.load(f)
            except Exception:
                pass

    def on_devices_loaded(self, speakers):
        self.primary_slot.populate_devices(speakers, self.history_data.get('primary', ''))
        
        saved_secondaries = self.history_data.get('secondary', [])
        for i, slot in enumerate(self.secondary_slots):
            saved_name = saved_secondaries[i] if i < len(saved_secondaries) else ""
            slot.populate_devices(speakers, saved_name)
            
        self.enforce_primary_rule()

    def has_primary_selected(self):
        if not hasattr(self, 'primary_slot'):
            return False
        current_text = self.primary_slot.device_dropdown.currentText()
        return current_text not in ["-- Select Device --", "-- Loading Devices... --", ""]

    def init_ui(self):
        central_widget = BackgroundWidget(resource_path("background.jpg"))
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # DUAL STREAM Header
        header = QLabel("DUAL STREAM")
        header.setObjectName("Header")
        main_layout.addWidget(header, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        main_layout.addStretch(1)

        # PRIMARY MASTER SECTION (Shortened width using setMaximumWidth)
        self.primary_slot = DeviceSlot("PRIMARY MASTER (Mic + Speaker Default)", self, is_primary=True)
        self.primary_slot.setMaximumWidth(450) # Makes the primary box compact and centered
        self.primary_slot.device_dropdown.currentIndexChanged.connect(self.enforce_primary_rule)
        
        primary_container = QHBoxLayout()
        primary_container.addStretch(1)
        primary_container.addWidget(self.primary_slot)
        primary_container.addStretch(1)
        main_layout.addLayout(primary_container)

        main_layout.addStretch(1)

        # SECONDARY MASTER SECTION (With transparent Teal Background Box)
        secondary_label = QLabel("SECONDARY MASTER (Speakers Only)")
        secondary_label.setObjectName("SecondaryLabel")
        secondary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(secondary_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        slots_layout = QHBoxLayout()
        self.secondary_slots = []
        for i in range(1, 5):
            slot = DeviceSlot(f"Output Slot {i}", self)
            self.secondary_slots.append(slot)
            slots_layout.addWidget(slot)
        
        main_layout.addLayout(slots_layout)
        main_layout.addSpacing(25)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("INITIALIZE ROUTING")
        self.btn_start.setObjectName("StartBtn")
        self.btn_start.clicked.connect(self.start_routing)
        
        self.btn_stop = QPushButton("TERMINATE STREAM")
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.clicked.connect(self.stop_routing)
        self.btn_stop.setEnabled(False)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        main_layout.addLayout(btn_layout)

        style_sheet = """
            QLabel {
                color: #f8fafc;
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
            }
            QLabel#Header {
                color: #0f172a; 
                font-size: 34px;
                letter-spacing: 8px;
                background: rgba(255, 255, 255, 0.7);
                padding: 5px 20px;
                border-radius: 8px;
                margin-top: 15px;
            }
            QLabel#SecondaryLabel {
                color: #f8fafc;
                font-size: 14px;
                letter-spacing: 2px;
                background-color: rgba(13, 148, 136, 0.4); /* Teal transparent background */
                border: 1px solid #0d9488;
                padding: 6px 20px;
                border-radius: 6px;
                margin-bottom: 5px;
            }
            QFrame#PrimarySlot {
                background-color: rgba(13, 148, 136, 0.25);
                border: 2px solid #0d9488;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#SecondarySlot {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px;
            }
            QComboBox {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #334155;
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox[locked="true"] {
                background-color: #0f172a;
                color: #64748b;
                border: 1px solid #0f172a;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #ffffff;
                selection-background-color: #0d9488;
            }
            QPushButton {
                font-weight: bold;
                color: white;
                border-radius: 6px;
                padding: 12px;
                font-size: 14px;
            }
            QPushButton#StartBtn { background-color: #0d9488; }
            QPushButton#StartBtn:hover { background-color: #0f766e; }
            QPushButton#StartBtn:disabled { background-color: #334155; color: #94a3b8; }
            QPushButton#StopBtn { background-color: #be123c; }
            QPushButton#StopBtn:hover { background-color: #9f1239; }
            QSlider::groove:horizontal {
                border: 1px solid #334155; height: 6px; background: #1e293b; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #38bdf8; width: 14px; margin: -4px 0; border-radius: 7px;
            }
            QMessageBox {
                background-color: #f1f5f9;
            }
            QMessageBox QLabel {
                color: #0f172a; /* Forces popup text to be dark and readable */
                font-weight: normal;
            }
            QMessageBox QPushButton {
                background-color: #0d9488;
                color: white;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 60px;
            }
        """
        self.setStyleSheet(style_sheet)

    def enforce_primary_rule(self):
        has_primary = self.has_primary_selected()
        self.btn_start.setEnabled(has_primary)
        
        for slot in self.secondary_slots:
            slot.volume_slider.setEnabled(has_primary)
            slot.delay_slider.setEnabled(has_primary)
            slot.device_dropdown.setProperty("locked", not has_primary)
            slot.device_dropdown.style().unpolish(slot.device_dropdown)
            slot.device_dropdown.style().polish(slot.device_dropdown)

    def save_history(self):
        history = {
            'primary': self.primary_slot.device_dropdown.currentText(),
            'secondary': [s.device_dropdown.currentText() for s in self.secondary_slots]
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(history, f)
        except Exception:
            pass

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = resource_path("background.jpg")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon))
        tray_menu = QMenu()
        restore_action = QAction("Open Dashboard", self)
        restore_action.triggered.connect(self.showNormal)
        tray_menu.addAction(restore_action)
        quit_action = QAction("Exit Completely", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self.tray_icon.showMessage("Dual Stream Active", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 2000)
            event.ignore()
        else:
            super().changeEvent(event)

    def start_routing(self):
        self.save_history()
        device_settings = {}
        
        p_set = self.primary_slot.get_settings()
        if p_set: device_settings[p_set['name']] = p_set
            
        for slot in self.secondary_slots:
            s_set = slot.get_settings()
            if s_set and s_set['name'] not in device_settings:
                device_settings[s_set['name']] = s_set

        if len(device_settings) < 2:
            QMessageBox.warning(self, "Configuration Error", "Please select your Primary device and at least ONE Secondary device.")
            return
        
        if not self.router: return

        success = self.router.start_routing(device_settings)
        if success:
            self.btn_start.setEnabled(False)
            self.primary_slot.setEnabled(False)
            for s in self.secondary_slots: s.setEnabled(False)
            self.btn_stop.setEnabled(True)
        else:
            QMessageBox.critical(self, "System Error", "Failed to tap into system audio.")

    def stop_routing(self):
        if self.router: self.router.stop_routing()
        self.btn_start.setEnabled(True)
        self.primary_slot.setEnabled(True)
        for s in self.secondary_slots: s.setEnabled(True)
        self.btn_stop.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    dashboard = DualStreamDashboard()
    # No more self.show() here, it's called instantly in __init__ for zero lag
    sys.exit(app.exec())