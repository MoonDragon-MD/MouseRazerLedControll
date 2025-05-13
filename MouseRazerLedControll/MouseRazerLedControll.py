# Razer Basilisk V3 X HyperSpeed LED Control
# V1.0 by MoonDragon (https://github.com/MoonDragon-MD/MouseRazerLedControll)
# dependencies
# pip install pyqt5 hidapi Cython
# pip install --upgrade hid
# Based on work of https://github.com/geezmolycos/razerqdhid
# If you have problems copy hidapi.dll, hidapi.lib and hidapi.pdb where python.exe resides
import sys
import hid
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QLineEdit, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt
from qdrazer.device import Device
import qdrazer.protocol as pt
from time import sleep

class Mouse(Device):
    vid = 0x1532
    pid = 0x00B9
    ifn = 0

    def connect(self, nth=1, path=None):
        self.path = path
        if self.path is None:
            devices = hid.enumerate()
            if not devices:
                raise RuntimeError("No HID devices detected by hidapi.")
            ith = 0
            for it in devices:
                if self.vid == it['vendor_id'] and self.pid == it['product_id'] and it.get('interface_number') == self.ifn:
                    ith += 1
                    if nth == ith:
                        self.path = it['path']
                        break
            if self.path is None:
                raise RuntimeError('No matching device')
        try:
            self.hid_device = hid.Device(path=self.path)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to device: {e}")

    def close(self):
        if hasattr(self, 'hid_device'):
            self.hid_device.close()

    def send(self, report):
        report.calculate_crc()
        send_data = b'\x00' + bytes(report)
        try:
            self.hid_device.send_feature_report(send_data)
        except Exception as e:
            raise RuntimeError(f"Failed to send report: {e}")

    def recv(self):
        try:
            data = self.hid_device.get_feature_report(0, 91)
            data = data[1:]  # Remove report ID
            return pt.Report.from_buffer(bytearray(data))
        except Exception as e:
            raise RuntimeError(f"Failed to receive report: {e}")

    def send_recv(self, report, *, wait_power=0):
        self.send(report)
        rr = report
        if wait_power is None:
            return rr
        for i in range(15 * (wait_power + 1)):
            sleep(0.01 * (i + 1))
            rr = self.recv()
            if not (rr.command_class == report.command_class and bytes(rr.command_id) == bytes(report.command_id)):
                raise pt.RazerException('Command does not match', rr)
            if rr.status == pt.Status.OK:
                return rr
            elif rr.status == pt.Status.BUSY:
                continue
            else:
                raise pt.RazerException(f'Report execution failed {rr.status}', rr)
        raise pt.RazerException('Report timeout', rr)

class LEDControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Razer Basilisk V3 X HyperSpeed LED Control")
        self.setGeometry(100, 100, 400, 500)
        self.device = None
        self.init_device()
        self.init_ui()

    def init_device(self):
        try:
            self.device = Mouse()
            self.device.connect()
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", str(e))
            sys.exit(1)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Predefined Colors
        color_group = QGroupBox("Predefined Colors")
        color_layout = QHBoxLayout()
        colors = [
            ("Red", (255, 0, 0)), ("Green", (0, 255, 0)), ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)), ("Purple", (128, 0, 128)), ("Cyan", (0, 255, 255)),
            ("White", (255, 255, 255)), ("Dark Red", (139, 0, 0))
        ]
        self.color_buttons = {}
        for name, rgb in colors:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, r=rgb: self.set_color(r))
            self.color_buttons[name] = btn
            color_layout.addWidget(btn)
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        # Manual RGB Input
        rgb_group = QGroupBox("Manual RGB Input")
        rgb_layout = QHBoxLayout()
        self.rgb_inputs = {}
        for label in ["R", "G", "B"]:
            rgb_layout.addWidget(QLabel(f"{label}:"))
            input_field = QLineEdit("0")
            input_field.setFixedWidth(50)
            self.rgb_inputs[label] = input_field
            rgb_layout.addWidget(input_field)
        rgb_group.setLayout(rgb_layout)
        layout.addWidget(rgb_group)

        # Brightness Slider
        brightness_group = QGroupBox("Brightness")
        brightness_layout = QVBoxLayout()
        self.brightness_label = QLabel("Brightness:")
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 100)
        self.brightness_slider.setValue(30)
        self.brightness_slider.valueChanged.connect(self.update_brightness_label)
        brightness_layout.addWidget(self.brightness_label)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # Apply and Save Buttons
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_settings)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)

    def update_brightness_label(self):
        self.brightness_label.setText(f"Brightness: {self.brightness_slider.value()}")

    def set_color(self, rgb):
        for label, value in zip(["R", "G", "B"], rgb):
            self.rgb_inputs[label].setText(str(value))

    def apply_settings(self):
        try:
            r = int(self.rgb_inputs["R"].text())
            g = int(self.rgb_inputs["G"].text())
            b = int(self.rgb_inputs["B"].text())
            if not all(0 <= x <= 255 for x in [r, g, b]):
                raise ValueError("RGB values must be 0-255")
            brightness = self.brightness_slider.value()
            self.device.set_led_effect(pt.LedRegion.WHEEL, pt.LedEffect.STATIC, colors=[(r, g, b)])
            self.device.set_led_brightness(pt.LedRegion.WHEEL, brightness)
            QMessageBox.information(self, "Success", "LED settings applied")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply settings: {e}")

    def save_settings(self):
        try:
            self.apply_settings()
            QMessageBox.information(self, "Success", "LED settings saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def closeEvent(self, event):
        if self.device:
            self.device.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LEDControlWindow()
    window.show()
    sys.exit(app.exec_())
