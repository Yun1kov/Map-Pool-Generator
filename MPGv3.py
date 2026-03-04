import sys
import os
import random
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                               QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
                               QGraphicsDropShadowEffect, QStackedWidget)
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QTimer, QEasingCurve
from PySide6.QtGui import (QPalette, QPixmap, QColor, QPainter, QFont,
                           QPainterPath, QIcon, QGuiApplication)


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------
# QuestionMarkWidget (unchanged)
# ------------------------------------------------------------
class QuestionMarkWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._hover = False

    def mouseReleaseEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        font_size = int(min(rect.width(), rect.height()) * 0.6)
        font = QFont("Roboto", font_size)
        font.setWeight(QFont.Light)
        painter.setFont(font)

        painter.setPen(QColor(220, 240, 255))
        painter.drawText(rect, Qt.AlignCenter, "?")


# ------------------------------------------------------------
# RoundDisplay (unchanged)
# ------------------------------------------------------------
class RoundDisplay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("roundFrame")
        self.setFixedSize(200, 180)
        self.setStyleSheet("background: transparent; border: none;")

        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, 200, 180)
        bg_path = resource_path("round_bg.png")
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            scaled = pixmap.scaled(200, 180, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            if scaled.width() > 200 or scaled.height() > 180:
                crop_x = (scaled.width() - 200) // 2
                crop_y = (scaled.height() - 180) // 2
                scaled = scaled.copy(crop_x, crop_y, 200, 180)

            rounded = QPixmap(200, 180)
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            path = QPainterPath()
            path.addRoundedRect(0, 0, 200, 180, 24, 24)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            self.bg_label.setPixmap(rounded)
        else:
            self.bg_label.setStyleSheet("background-color: rgba(35, 65, 130, 0.45); border-radius: 24px;")

        self.overlay = QLabel(self)
        self.overlay.setGeometry(0, 0, 200, 180)
        self.overlay.setStyleSheet("""
            background-color: rgba(35, 65, 130, 0.3);
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.addStretch()

        self.round_label = QLabel("Round: --")
        self.round_label.setAlignment(Qt.AlignCenter)
        self.round_label.setStyleSheet("color: white; font-size: 20px; font-weight: 600;")
        layout.addWidget(self.round_label)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

    def set_round(self, number):
        if number is None:
            self.round_label.setText("Round: --")
        else:
            self.round_label.setText(f"Round: {number}")


# ------------------------------------------------------------
# Main window
# ------------------------------------------------------------
class MapGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setWindowTitle("Map Pool Generator")

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setFixedSize(1220, 720)

        # Load maps
        base = get_base_path()
        maps_folder = os.path.join(base, "maps")
        self.maps = self.load_maps(maps_folder)
        if not self.maps:
            QMessageBox.critical(self, "Error",
                                 "The 'maps' folder is empty or not found!\n"
                                 "Supported formats: .jpg, .webp")
            sys.exit(1)

        self.used_cards = set()
        self.rounds = []
        self.current_round_index = -1

        # Do not show the window yet
        self.hide()

        # Defer UI creation
        QTimer.singleShot(0, self.init_ui)

    def paintEvent(self, event):
        # Fill background with dark color
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 15, 26))
        super().paintEvent(event)

    def init_ui(self):
        """Create the interface (called after the constructor)."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 20, 40, 20)
        main_layout.setSpacing(30)

        # Background
        self.set_background("background.jpg")

        self.toast = ToastNotification(self)

        # Round widget
        self.round_widget = RoundDisplay()
        round_container = QHBoxLayout()
        round_container.addStretch()
        round_container.addWidget(self.round_widget)
        round_container.addStretch()
        main_layout.addLayout(round_container)

        # Center part
        center_layout = QHBoxLayout()
        center_layout.setSpacing(20)

        # Left arrow
        self.left_arrow = QPushButton("◀")
        self.left_arrow.setObjectName("arrowButton")
        self.left_arrow.setFixedSize(70, 160)
        self.left_arrow.clicked.connect(self.prev_round)
        self.left_arrow.setEnabled(False)
        arrow_shadow = QGraphicsDropShadowEffect()
        arrow_shadow.setBlurRadius(20)
        arrow_shadow.setColor(QColor(0, 0, 0, 80))
        arrow_shadow.setOffset(0, 5)
        self.left_arrow.setGraphicsEffect(arrow_shadow)
        center_layout.addWidget(self.left_arrow)

        # Cards
        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setSpacing(32)
        cards_layout.setAlignment(Qt.AlignCenter)

        self.card_frames = []
        self.card_stacks = []
        self.image_labels = []
        self.question_widgets = []
        self.name_labels = []
        self.card_shadows = []

        for i in range(3):
            card = QFrame()
            card.setObjectName("cardFrame")
            card.setFixedSize(250, 300)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(10)
            card_layout.setContentsMargins(15, 15, 15, 15)

            stack = QStackedWidget()
            stack.setFixedSize(210, 210)
            stack.setObjectName("cardStack")

            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            img_label.setObjectName("cardImage")
            img_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            stack.addWidget(img_label)

            question_widget = QuestionMarkWidget()
            question_widget.setFixedSize(210, 210)
            stack.addWidget(question_widget)

            stack.setCurrentIndex(1)

            card_layout.addWidget(stack, alignment=Qt.AlignCenter)

            name_label = QLabel()
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setObjectName("cardName")
            name_label.setWordWrap(True)
            name_label.setMaximumWidth(220)
            name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            card_layout.addWidget(name_label)

            cards_layout.addWidget(card)

            self.card_frames.append(card)
            self.card_stacks.append(stack)
            self.image_labels.append(img_label)
            self.question_widgets.append(question_widget)
            self.name_labels.append(name_label)

            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(30)
            shadow.setColor(QColor(0, 0, 0, 120))
            shadow.setOffset(0, 8)
            card.setGraphicsEffect(shadow)
            self.card_shadows.append(shadow)

            card.installEventFilter(self)

        center_layout.addWidget(cards_container)

        # Right arrow
        self.right_arrow = QPushButton("▶")
        self.right_arrow.setObjectName("arrowButton")
        self.right_arrow.setFixedSize(70, 160)
        self.right_arrow.clicked.connect(self.next_round)
        self.right_arrow.setEnabled(False)
        right_arrow_shadow = QGraphicsDropShadowEffect()
        right_arrow_shadow.setBlurRadius(20)
        right_arrow_shadow.setColor(QColor(0, 0, 0, 80))
        right_arrow_shadow.setOffset(0, 5)
        self.right_arrow.setGraphicsEffect(right_arrow_shadow)
        center_layout.addWidget(self.right_arrow)

        main_layout.addLayout(center_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        self.generate_btn = QPushButton("Generate Round")
        self.generate_btn.setObjectName("generateButton")
        self.generate_btn.setFixedSize(300, 60)
        self.generate_btn.clicked.connect(self.generate_round)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("resetButton")
        self.reset_btn.setFixedSize(150, 60)
        self.reset_btn.clicked.connect(self.reset_rounds)

        for btn in (self.generate_btn, self.reset_btn):
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(30)
            shadow.setColor(QColor(0, 0, 0, 120))
            shadow.setOffset(0, 8)
            btn.setGraphicsEffect(shadow)

        btn_layout.addStretch()
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 5, 0, 5)
        footer_layout.addStretch()
        self.footer_label = QLabel("MPGv1.0 by YUN")
        self.footer_label.setStyleSheet("color: rgba(255, 255, 255, 0.2); font-size: 12px;")
        self.footer_label.setAlignment(Qt.AlignCenter)
        footer_layout.addWidget(self.footer_label)
        footer_layout.addStretch()
        main_layout.addLayout(footer_layout)

        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 1)
        main_layout.setStretch(2, 0)
        main_layout.setStretch(3, 0)

        self.setStyleSheet(self.get_stylesheet())

        self.update_display()

        # Now that everything is ready, show the window
        self.show()

    # ------------------------------------------------------------
    # Remaining methods (set_background, load_maps, get_stylesheet, eventFilter, show_toast, update_display, etc.)
    # They remain unchanged except for comment translation.
    # ------------------------------------------------------------
    def set_background(self, filename):
        central = self.centralWidget()
        if central is None:
            return
        bg_path = resource_path(filename)
        if os.path.exists(bg_path):
            self.bg_label = QLabel(central)
            pixmap = QPixmap(bg_path)
            scaled = pixmap.scaled(1220, 720, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.bg_label.setPixmap(scaled)
            self.bg_label.setGeometry(0, 0, 1220, 720)

            self.dark_overlay = QLabel(central)
            self.dark_overlay.setGeometry(0, 0, 1220, 720)
            self.dark_overlay.setStyleSheet("background-color: rgba(8, 15, 30, 0.6);")
            self.dark_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)

            self.bg_label.lower()
            self.dark_overlay.raise_()
        else:
            print("Background image not found, using dark background.")

    def load_maps(self, folder):
        maps = {}
        if not os.path.exists(folder):
            os.makedirs(folder)
            return maps
        for filename in os.listdir(folder):
            if filename.lower().endswith(('.jpg', '.webp')):
                name = os.path.splitext(filename)[0]
                path = os.path.join(folder, filename)
                maps[name] = path
        return maps

    def get_stylesheet(self):
        return """
            QMainWindow {
                background-color: transparent;
            }
            QLabel, QPushButton {
                font-family: 'Segoe UI', sans-serif;
            }
            #roundFrame {
                background: transparent;
                border: none;
            }
            #cardFrame {
                background-color: rgba(35, 65, 130, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 24px;
            }
            #cardImage {
                border-radius: 16px;
                background-color: #1e1e2f;
            }
            #cardName {
                color: white;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }
            #arrowButton {
                font-size: 28px;
                font-weight: bold;
                background-color: rgba(58, 111, 247, 0.5);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 16px;
            }
            #arrowButton:hover {
                background-color: rgba(58, 111, 247, 0.85);
                border-color: rgba(255, 255, 255, 0.3);
            }
            #arrowButton:disabled {
                background-color: rgba(80, 80, 120, 0.3);
                color: rgba(255, 255, 255, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #generateButton, #resetButton {
                font-size: 22px;
                font-weight: 600;
                color: white;
                background-color: rgba(35, 65, 130, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 24px;
                padding: 12px 24px;
            }
            #generateButton:hover, #resetButton:hover {
                background-color: rgba(58, 111, 247, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            #generateButton:pressed, #resetButton:pressed {
                background-color: rgba(20, 40, 80, 0.7);
            }
        """

    def eventFilter(self, obj, event):
        if obj in self.card_frames:
            idx = self.card_frames.index(obj)
            shadow = self.card_shadows[idx]

            if event.type() == QEvent.Enter:
                shadow.setBlurRadius(45)
                shadow.setColor(QColor(0, 160, 255, 180))
                shadow.setOffset(0, 12)
            elif event.type() == QEvent.Leave:
                shadow.setBlurRadius(30)
                shadow.setColor(QColor(0, 0, 0, 120))
                shadow.setOffset(0, 8)
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    map_name = self.name_labels[idx].text()
                    if map_name:
                        clipboard = QApplication.clipboard()
                        clipboard.setText(f"!map {map_name}")

                        if hasattr(event, "globalPosition"):
                            pos = event.globalPosition().toPoint()
                        else:
                            pos = event.globalPos()

                        self.show_toast(f"Copied: !map {map_name}", pos)
                    return True
        return super().eventFilter(obj, event)

    def show_toast(self, text, pos):
        self.toast.show_toast(text, pos)

    def update_display(self):
        if self.rounds:
            self.left_arrow.setEnabled(self.current_round_index > 0)
            self.right_arrow.setEnabled(self.current_round_index < len(self.rounds) - 1)
            round_num, cards = self.rounds[self.current_round_index]
            self.round_widget.set_round(round_num)
            self.display_cards(cards)
        else:
            self.left_arrow.setEnabled(False)
            self.right_arrow.setEnabled(False)
            self.round_widget.set_round(None)
            self.display_cards([])

    def display_cards(self, cards):
        for i in range(3):
            if i < len(cards):
                card_name = cards[i]
                img_path = self.maps.get(card_name)
                if img_path and os.path.exists(img_path):
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(210, 210, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.image_labels[i].setPixmap(pixmap)
                        self.card_stacks[i].setCurrentIndex(0)
                        self.name_labels[i].setText(card_name)
                    else:
                        self.card_stacks[i].setCurrentIndex(1)
                        self.name_labels[i].setText("")
                else:
                    self.card_stacks[i].setCurrentIndex(1)
                    self.name_labels[i].setText("")
            else:
                self.card_stacks[i].setCurrentIndex(1)
                self.name_labels[i].setText("")

    def generate_round(self):
        available = [name for name in self.maps.keys() if name not in self.used_cards]
        if len(available) < 3:
            QMessageBox.warning(self, "Cannot create a new round",
                                f"Only {len(available)} unused maps remain. Cannot create a new round.")
            return
        chosen = random.sample(available, 3)
        self.used_cards.update(chosen)
        new_round_num = len(self.rounds) + 1
        self.rounds.append((new_round_num, chosen))
        self.current_round_index = len(self.rounds) - 1
        self.update_display()

    def reset_rounds(self):
        self.used_cards.clear()
        self.rounds.clear()
        self.current_round_index = -1
        self.update_display()

    def prev_round(self):
        if self.current_round_index > 0:
            self.current_round_index -= 1
            self.update_display()

    def next_round(self):
        if self.current_round_index < len(self.rounds) - 1:
            self.current_round_index += 1
            self.update_display()


# ------------------------------------------------------------
# ToastNotification (unchanged)
# ------------------------------------------------------------
class ToastNotification(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            #toast {
                background-color: rgba(30, 30, 40, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
            }
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: 600;
                padding: 12px 24px;
                background: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(150)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_anim.finished.connect(self.on_animation_finished)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_animated)

        self._hide_when_finished = False

    def on_animation_finished(self):
        if self._hide_when_finished:
            self.hide()
            self._hide_when_finished = False

    def show_toast(self, text, pos):
        self.opacity_anim.stop()
        self.timer.stop()
        self._hide_when_finished = False

        self.label.setText(text)
        self.adjustSize()

        screen = QGuiApplication.screenAt(pos)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        x = pos.x() + 20
        y = pos.y() - self.height() - 10

        if x + self.width() > screen_geo.right():
            x = pos.x() - self.width() - 20
        if y < screen_geo.top():
            y = pos.y() + 20
        if x < screen_geo.left():
            x = screen_geo.left() + 5

        self.move(x, y)

        self.setWindowOpacity(0.0)
        self.show()
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.start()

        self.timer.start(500)

    def hide_animated(self):
        self.opacity_anim.stop()
        self.opacity_anim.setStartValue(1.0)
        self.opacity_anim.setEndValue(0.0)
        self._hide_when_finished = True
        self.opacity_anim.start()


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set dark palette just in case
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(10, 15, 26))
    app.setPalette(palette)

    window = MapGeneratorApp()
    # Not shown here – will be shown in init_ui
    sys.exit(app.exec())