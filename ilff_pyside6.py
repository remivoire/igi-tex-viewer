import sys
import struct
from PIL import Image
from PIL.ImageQt import ImageQt
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QListWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QCheckBox, QFrame, QSizePolicy, QStatusBar,
    QTextEdit, QDockWidget
)
from PySide6.QtGui import (
    QPixmap, QPalette, QColor, QFont, QFontDatabase, QAction
)
from PySide6.QtCore import Qt, QObject, Signal


class EmittingStream(QObject):
    text_written = Signal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass


class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # main window reference

    def wheelEvent(self, event):
        self.parent.zoom(event)

    def mouseDoubleClickEvent(self, event):
        self.parent.double_click_image(event)


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        # instance vars
        self.zoom_level = 1.0
        self.current_image = None  # pil img
        self.current_image_name = None
        self.current_image_size = 0  # size in bytes
        self.images = []  # list of tuples (pil image, name, size_in_bytes)
        self.auto_fit = True
        self.console_visible = False  # Console vis flag

        self.init_ui()

        # redirt stdout and stderr to onsole
        self.sys_stdout = sys.stdout
        self.sys_stderr = sys.stderr
        self.console = None  # will hold console widget

    def init_ui(self):
        # main window setup
        self.setWindowTitle('IGI - TEX Viewer')
        self.setGeometry(100, 100, 800, 600)

        # central widget creation
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # layout creation
        self.main_layout = QHBoxLayout(self.central_widget)

        # list widget creation
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(200)
        self.list_widget.itemSelectionChanged.connect(self.on_select)
        self.list_widget.itemDoubleClicked.connect(self.double_click)
        self.main_layout.addWidget(self.list_widget)

        # img display area creation
        self.image_frame = QFrame()
        self.image_frame.setFrameShape(QFrame.StyledPanel)
        self.image_frame_layout = QVBoxLayout(self.image_frame)
        self.main_layout.addWidget(self.image_frame)

        # img label creation
        self.image_label = ImageLabel(self)
        self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_label.setScaledContents(True)
        self.image_frame_layout.addWidget(self.image_label)

        # img info label creation
        self.image_info_label = QLabel(self.image_label)
        self.image_info_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 128);")
        self.image_info_label.move(5, 5)
        self.image_info_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.image_info_label.setVisible(False)

        # status bar with autofit checkbox creation
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.auto_fit_checkbox = QCheckBox('Auto fit image to window')
        self.auto_fit_checkbox.setChecked(True)
        self.auto_fit_checkbox.stateChanged.connect(self.toggle_auto_fit)
        self.status_bar.addPermanentWidget(self.auto_fit_checkbox)

        # menu bar creation
        menubar = self.menuBar()

        # file menu
        file_menu = menubar.addMenu('File')
        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Esc')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # debug menu
        debug_menu = menubar.addMenu('Debug')
        toggle_console_action = QAction('Toggle Console', self)
        toggle_console_action.setShortcut('Ctrl+D')
        toggle_console_action.triggered.connect(self.toggle_console)
        debug_menu.addAction(toggle_console_action)

    def open_file(self):
        # file open dialog and load images implementation
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Resource Files (*.res)")
        if file_path:
            self.load_images(file_path)

    def load_images(self, file_path):
        # image loading implementation
        self.images = self.read_chunks(file_path)
        self.list_widget.clear()
        for i, (img, name, size_in_bytes) in enumerate(self.images):
            # extraction of filename from the name
            if name:
                filename = os.path.basename(name)
            else:
                filename = f'Image {i+1}'
            self.list_widget.addItem(filename)
        if self.images:
            self.list_widget.setCurrentRow(0)
            self.update_image(0)

    def read_chunks(self, file_path):
        images = []
        try:
            with open(file_path, 'rb') as file:
                if file.readable() and file.seekable():
                    try:
                        magic, filesize, _, _, res_type = struct.unpack('IIIII', file.read(20))
                        if magic != 0x46464C49:  # 'ILFF'
                            print("Not a valid ILFF file.")
                            return images  # not a valid file
                    except struct.error:
                        print("Failed to read the initial header, file may be corrupted or incomplete.")
                        return images

                    current_name = None  # to store the name associated with the next image
                    while file.tell() < filesize + 4:
                        try:
                            start_address = file.tell()
                            header = file.read(16)
                            if len(header) < 16:
                                print("Error reading chunk: Not enough data for header.")
                                break
                            chunk_type, buffer_size, _, chunk_size = struct.unpack('IIII', header)
                            buffer = file.read(buffer_size)
                            if len(buffer) < buffer_size:
                                print("Error reading chunk: Not enough data for buffer.")
                                break

                            # process NAME chunk
                            if chunk_type == 0x454D414E:  # 'NAME'
                                # read the name string
                                name = buffer.decode('utf-8', errors='ignore').strip('\x00')
                                current_name = name
                            elif chunk_type == 0x59444F42:  # 'BODY'
                                image_data = self.parse_body_chunk(buffer, start_address, current_name)
                                if image_data:
                                    size_in_bytes = len(buffer)
                                    images.append((image_data, current_name, size_in_bytes))
                                current_name = None  # reset the name after associating it
                            else:
                                # might want to look into handling other chunk types here if needed..
                                pass

                            # align to next chunk properly
                            file.seek((file.tell() + 3) & ~3)
                        except struct.error as e:
                            print(f"Error reading chunk: {e}. Possibly end of file reached unexpectedly.")
                            break
                else:
                    print("File is not readable or seekable.")
        except FileNotFoundError:
            print(f"File '{file_path}' not found.")
        return images

    def parse_body_chunk(self, buffer, start_address, name):
        try:
            extension = os.path.splitext(name)[-1].lower()  # get file extension in lowercase
            if extension == '.tex':
                # usual process for .tex files
                header_format = 'IIIIIHHHHHH'
                header_size = struct.calcsize(header_format)
                header = struct.unpack(header_format, buffer[:header_size])
                image_data = buffer[header_size:]
                width, height = header[6], header[7]  # width_1, height_1 are likely the actual image dimensions

                # print header values and start address for debugging
                print(f"Start Address: {start_address}, Image Header Values: {header}")

                if width > 8000 or height > 8000:
                    print(f"Unusually large image dimensions: {width}x{height}. Skipping.")
                    return None
                if len(image_data) < width * height * 4:
                    print(f"Not enough data for an image {width}x{height}.")
                    return None

                # handle BGR img data
                image = Image.frombytes('RGBA', (width, height), image_data, 'raw', 'BGRA')
                return image
            elif extension == '.tga':
                # read TGA img data directly
                return self.read_tga_image(buffer)
            else:
                print(f"Unsupported image format: {extension}. Skipping.")
                return None
        except Exception as e:
            print(f"Error parsing image chunk: {e}")
            return None

    def read_tga_image(self, buffer):
        """Reads TGA image data from a raw buffer."""
        # tga header
        header_size = 18  # tga header size
        if len(buffer) < header_size:
            print("Buffer too small to contain TGA header.")
            return None

        header = buffer[:header_size]
        width = header[12] + (header[13] << 8)  # width in pixels
        height = header[14] + (header[15] << 8)  # height in pixels
        pixel_depth = header[16]  # bits per pixel
        image_data_offset = header_size  # image data starts right after the header!

        if pixel_depth == 32:
            # create a new img from the tga data with 32bpp
            image_data = buffer[image_data_offset:]
            if len(image_data) < width * height * 4:
                print(f"Not enough data for image dimensions: {width}x{height}.")
                return None
            image = Image.frombuffer('RGBA', (width, height), image_data, 'raw', 'BGRA', 0, 1)
            return image
        elif pixel_depth == 24:
            # create a new img from the tga data with 24bpp
            image_data = buffer[image_data_offset:]
            if len(image_data) < width * height * 3:
                print(f"Not enough data for image dimensions: {width}x{height}.")
                return None
            # Convert to RGBA
            rgba_data = bytearray()
            for i in range(0, len(image_data), 3):
                rgba_data.extend(image_data[i:i+3])  # add RGB
                rgba_data.extend(b'\xFF')  # add alpha (consider argb)

            # convert bytearray to bytes for pil
            image = Image.frombuffer('RGBA', (width, height), bytes(rgba_data), 'raw', 'BGRA', 0, 1)
            return image
        else:
            print(f"Unsupported pixel depth: {pixel_depth}. Only 24bpp and 32bpp TGA are supported.")
            return None

    def on_select(self):
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            index = self.list_widget.row(selected_items[0])
            self.update_image(index)

    def update_image(self, selected_index):
        if 0 <= selected_index < len(self.images):
            self.current_image = self.images[selected_index][0]  # pil img
            self.current_image_name = self.images[selected_index][1]
            self.current_image_size = self.images[selected_index][2]
            self.zoom_level = 1.0  # rset zoom level
            self.display_image_at_zoom(self.current_image)

    def display_image_at_zoom(self, image):
        if image is None:
            return

        # getting current frame dimensions
        frame_width = self.image_frame.width()
        frame_height = self.image_frame.height()

        # resize according to zoom level or fit to window
        if self.auto_fit:
            # fit img to window while maintaining aspect ratio
            aspect_ratio = image.width / image.height
            new_width = frame_width
            new_height = int(frame_width / aspect_ratio)

            if new_height > frame_height:  # if height is too large adjust to fit height
                new_height = frame_height
                new_width = int(frame_height * aspect_ratio)
        else:
            # resize based on zoom level
            new_width = int(image.width * self.zoom_level)
            new_height = int(image.height * self.zoom_level)

        # resize the pil img
        resized_image = image.resize((new_width, new_height), Image.LANCZOS)

        # convert pil img to QPixmap
        qim = ImageQt(resized_image)
        pixmap = QPixmap.fromImage(qim)

        self.image_label.setPixmap(pixmap)
        self.image_label.resize(new_width, new_height)

        # update image info label
        self.update_image_info()

    def update_image_info(self):
        if self.current_image is not None:
            width, height = self.current_image.width, self.current_image.height
            size_in_bytes = self.current_image_size
            size_in_kb = size_in_bytes / 1024
            info_text = f"{width} x {height} px\n{size_in_kb:.2f} KB"
            self.image_info_label.setText(info_text)
            self.image_info_label.adjustSize()
            self.image_info_label.setVisible(True)
        else:
            self.image_info_label.setVisible(False)

    def zoom(self, event):
        if self.auto_fit:
            return

        delta = event.angleDelta().y()

        if delta > 0:  # Zoom in
            self.zoom_level *= 1.05
        else:
            self.zoom_level /= 1.05

        # ensuring the zoom level remains within reasonable bounds
        self.zoom_level = max(0.1, min(10.0, self.zoom_level))

        # update the img display
        self.display_image_at_zoom(self.current_image)

    def toggle_auto_fit(self):
        self.auto_fit = self.auto_fit_checkbox.isChecked()
        self.display_image_at_zoom(self.current_image)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.auto_fit:
            self.display_image_at_zoom(self.current_image)

    def double_click(self, item):
        index = self.list_widget.row(item)
        image = self.images[index][0]
        self.save_image_as_tga(image)

    def double_click_image(self, event):
        if self.current_image is not None:
            self.save_image_as_tga(self.current_image)

    def save_image_as_tga(self, image):
        if image is not None:
            # extract the base filename and replace extension with .tga
            default_name = 'image.tga'  # default name
            if self.current_image_name:
                default_name = os.path.splitext(os.path.basename(self.current_image_name))[0] + '.tga'

            options = QFileDialog.Options()
            tga_filename, _ = QFileDialog.getSaveFileName(
                self, "Save Image As", default_name, "TGA Files (*.tga)", options=options
            )
            if tga_filename:
                image.save(tga_filename, format='TGA')
                QMessageBox.information(self, "Image Saved", f"Image saved as: {tga_filename}")

    def toggle_console(self):
        if self.console_visible:
            self.close_console()
        else:
            self.open_console()

    def open_console(self):
        if not self.console:
            # create the console widget
            self.console = QDockWidget("Debug Console", self)
            self.console.setAllowedAreas(Qt.BottomDockWidgetArea)
            self.console_widget = QTextEdit()
            self.console_widget.setReadOnly(True)

            # setting monospace font for the console widget
            font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
            font.setPointSize(10)  # font size, adjustable
            self.console_widget.setFont(font)

            self.console.setWidget(self.console_widget)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.console)

            # redir stdout and stderr
            self.stdout_stream = EmittingStream()
            self.stdout_stream.text_written.connect(self.write_console)
            self.stderr_stream = EmittingStream()
            self.stderr_stream.text_written.connect(self.write_console)
            sys.stdout = self.stdout_stream
            sys.stderr = self.stderr_stream

        self.console.show()
        self.console_visible = True

    def close_console(self):
        if self.console:
            self.console.hide()
            self.console_visible = False

            # restore original stdout and stderr
            sys.stdout = self.sys_stdout
            sys.stderr = self.sys_stderr

    def write_console(self, text):
        self.console_widget.insertPlainText(text)
        self.console_widget.ensureCursorVisible()

    def closeEvent(self, event):
        # restore stdout and stderr
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # theming
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(37, 37, 38))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(37, 37, 38))
    palette.setColor(QPalette.ToolTipBase, QColor(220, 220, 220))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(45, 45, 48))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(0, 122, 204))
    palette.setColor(QPalette.Highlight, QColor(0, 122, 204))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    viewer = ImageViewer()

    # fallback thing, check if fixed file exists otherwise prompt for a file to open
    fixed_file_path = 'G:\\tmp\\rando_mef_files\\New folder\\textures.res'
    if os.path.exists(fixed_file_path):
        viewer.load_images(fixed_file_path)
    else:
        viewer.open_file()

    viewer.show()
    sys.exit(app.exec())
