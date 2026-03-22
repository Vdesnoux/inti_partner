# -*- coding: utf-8 -*-
"""
SpectroSolHub submission wizard for INTI Partner.
3-step wizard: Authentication → Image Selection → Session Metadata

Ported from JSol'Ex Java implementation.
"""

import os
import json
import platform
import re
import webbrowser

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QProgressBar, QCheckBox, QScrollArea,
    QWidget, QMessageBox, QFrame, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage

from spectrosolhub_client import (
    SpectroSolHubClient, SpectroSolHubException, DEFAULT_BASE_URL
)

try:
    from Inti_functions import angle_P_B0
except ImportError:
    angle_P_B0 = None

def _get_date_from_log(log_file):
    """Extract UTC date from a _log.txt file.
    Log files contain a line like: SER date UTC :"2024-04-13T13:16:33.8371717"
    Returns ISO date string or None."""
    try:
        with open(log_file, encoding='latin-1') as f:
            lines = f.readlines()
        utc_lines = [l for l in lines if "UTC" in l]
        if not utc_lines:
            return None
        line = utc_lines[0].rstrip()
        date_part = line.split('UTC :')[1].strip().strip('"')
        return date_part
    except Exception:
        return None


def _get_p_angle_from_log(log_file):
    """Extract applied P angle from a _log.txt file produced by INTI.
    Log files contain a line like: 'Angle P : 23.45' or 'P angle : 23.45'
    Returns the float value, or None if not found."""
    try:
        with open(log_file, encoding='latin-1') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            # French: "Angle P : 23.45"  English: "P angle : 23.45"
            if line.startswith("Angle P") or line.startswith("P angle"):
                value_str = line.split(":")[1].strip()
                return float(value_str)
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Spectroheliograph definitions matching JSol'Ex SpectroHeliograph constants.
# Each entry: label -> {totalAngleDegrees, focalLength (camera), collimatorFocalLength,
#                       density (grooves/mm), order, slitWidthMicrons, slitHeightMillimeters}
SPECTROHELIOGRAPHS = {
    "Sol'Ex": {
        "name": "Sol'Ex",
        "gratingDensity": 2400, "gratingOrder": 1,
        "slitWidthMicrons": 10.0, "slitHeightMillimeters": 4.5,
        "cameraFocalLength": 125.0, "collimatorFocalLength": 80.0,
        "totalAngleDegrees": 34.0,
    },
    "Sol'Ex (7μm/6mm slit)": {
        "name": "Sol'Ex (7μm/6mm slit)",
        "gratingDensity": 2400, "gratingOrder": 1,
        "slitWidthMicrons": 7.0, "slitHeightMillimeters": 6.0,
        "cameraFocalLength": 125.0, "collimatorFocalLength": 80.0,
        "totalAngleDegrees": 34.0,
    },
    "Sol'Ex (10μm/6mm slit)": {
        "name": "Sol'Ex (10μm/6mm slit)",
        "gratingDensity": 2400, "gratingOrder": 1,
        "slitWidthMicrons": 10.0, "slitHeightMillimeters": 6.0,
        "cameraFocalLength": 125.0, "collimatorFocalLength": 80.0,
        "totalAngleDegrees": 34.0,
    },
    "Sunscan": {
        "name": "Sunscan",
        "gratingDensity": 2400, "gratingOrder": 1,
        "slitWidthMicrons": 10.0, "slitHeightMillimeters": 6.0,
        "cameraFocalLength": 100.0, "collimatorFocalLength": 75.0,
        "totalAngleDegrees": 34.0,
    },
    "MLAstro SHG 700": {
        "name": "MLAstro SHG 700",
        "gratingDensity": 2400, "gratingOrder": 1,
        "slitWidthMicrons": 7.0, "slitHeightMillimeters": 7.0,
        "cameraFocalLength": 72.0, "collimatorFocalLength": 72.0,
        "totalAngleDegrees": 34.0,
    },
    "MLAstro SHG 400": {
        "name": "MLAstro SHG 400",
        "gratingDensity": 2400, "gratingOrder": 1,
        "slitWidthMicrons": 7.0, "slitHeightMillimeters": 7.0,
        "cameraFocalLength": 100.0, "collimatorFocalLength": 100.0,
        "totalAngleDegrees": 34.0,
    },
}


# Spectral line labels and wavelengths matching JSol'Ex SpectralRay definitions
SPECTRAL_LINES = {
    "H-alpha":              6562.81,
    "Calcium (K)":          3933.66,
    "Calcium (H)":          3968.47,
    "Calcium+Iron+CH (G)":  4307.82,
    "H-beta":               4861.34,
    "Magnesium (b1)":       5183.62,
    "Iron (E2)":            5270.39,
    "Mercury (e)":          5460.73,
    "Helium (D3)":          5875.62,
    "Iron (Fe I)":          5883.8166,
    "Sodium (D2)":          5889.95,
    "Sodium (D1)":          5895.92,
    "Other":                None,
}


def _guess_spectral_line(filename):
    """Guess the spectral line from the filename conventions used by INTI/JSol'Ex."""
    fn = os.path.basename(filename).lower()
    # Map filename patterns to JSol'Ex spectral line labels
    mapping = {
        "_ha": "H-alpha",
        "halpha": "H-alpha",
        "_cak": "Calcium (K)",
        "_cahk": "Calcium (K)",
        "_calcium": "Calcium (K)",
        "_cah_": "Calcium (H)",
        "_nad": "Sodium (D1)",
        "_sodium": "Sodium (D1)",
        "_hed3": "Helium (D3)",
        "_helium": "Helium (D3)",
        "_mgi": "Magnesium (b1)",
        "_magnesium": "Magnesium (b1)",
        "_hbeta": "H-beta",
        "_cont": "Other",
    }
    for key, line in mapping.items():
        if key in fn:
            return line, SPECTRAL_LINES.get(line)
    # default to H-alpha as it is the most common
    return "H-alpha", SPECTRAL_LINES["H-alpha"]


def _image_to_jpeg_bytes(img_path):
    """Read an image file and return JPEG bytes."""
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(f"Cannot read image: {img_path}")
    # Convert 16-bit to 8-bit for JPEG
    if img.dtype == np.uint16:
        img = (img / 256).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise IOError(f"Failed to encode JPEG: {img_path}")
    return buf.tobytes()


def _make_thumbnail(img_path, size=120):
    """Create a QPixmap thumbnail from an image file."""
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.dtype == np.uint16:
        img = (img / 256).astype(np.uint8)
    h, w = img.shape[:2]
    scale = min(size / w, size / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    qimg = QImage(img.data, img.shape[1], img.shape[0],
                  img.shape[1] * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


def _split_brand_model(text):
    """Split 'Brand Model' text into (brand, model) tuple, like JSol'Ex splitBrandModel."""
    parts = text.strip().split(None, 1)
    if len(parts) < 2:
        return parts[0], parts[0]
    return parts[0], parts[1]


def _int_or_none(text):
    try:
        return int(text.strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _carrington_rotation(date_utc):
    """Compute Carrington rotation number from a UTC date string.
    Uses the same formula as JSol'Ex SolarParametersUtils."""
    import astropy.time
    jd = astropy.time.Time(date_utc).jd
    CARRINGTON_ROTATION_1_START = 2398167.2763889
    CARRINGTON_ROTATION_PERIOD = 27.2753
    return int((jd - CARRINGTON_ROTATION_1_START) / CARRINGTON_ROTATION_PERIOD) + 1


def _float_or_none(text):
    try:
        return float(text.strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _image_kind_from_filename(filename):
    """Determine image kind from filename suffix.
    Used only for filtering (e.g. excluding RAW).
    The imageKind sent to the API is always INTI_PARTNER."""
    fn = os.path.basename(filename).lower()
    if "_disk" in fn:
        return "DISK"
    elif "_clahe" in fn:
        return "CLAHE"
    elif "_protus" in fn:
        return "PROTUS"
    elif "_color" in fn:
        return "COLOR"
    elif "_doppler" in fn:
        return "DOPPLER"
    elif "_cont" in fn:
        return "CONTINUUM"
    elif "_free" in fn:
        return "FREE"
    elif "_raw" in fn:
        return "RAW"
    elif "_mix" in fn:
        return "MIXED"
    return "OTHER"


# ---------------------------------------------------------------------------
# Background worker threads
# ---------------------------------------------------------------------------

class LoginWorker(QThread):
    finished = Signal(str)  # token
    error = Signal(str, int)  # message, status_code

    def __init__(self, url, username, password, token_name, totp_code=None):
        super().__init__()
        self.url = url
        self.username = username
        self.password = password
        self.token_name = token_name
        self.totp_code = totp_code

    def run(self):
        try:
            token = SpectroSolHubClient.login(
                self.url, self.username, self.password,
                self.token_name, self.totp_code
            )
            self.finished.emit(token)
        except SpectroSolHubException as e:
            self.error.emit(str(e), e.status_code or 0)


class VerifyTokenWorker(QThread):
    valid = Signal()
    invalid = Signal()

    def __init__(self, url, token):
        super().__init__()
        self.url = url
        self.token = token

    def run(self):
        try:
            client = SpectroSolHubClient(self.url, self.token)
            client.fetch_quota()
            self.valid.emit()
        except SpectroSolHubException:
            self.invalid.emit()


class UploadWorker(QThread):
    progress = Signal(int, int, int, int)  # image_idx, total_images, part, total_parts
    finished = Signal(int)  # session_id
    error = Signal(str)

    def __init__(self, url, token, session_request, image_files, publish,
                 build_metadata_func):
        super().__init__()
        self.url = url
        self.token = token
        self.session_request = session_request
        self.image_files = image_files
        self.publish = publish
        self.build_metadata_func = build_metadata_func

    def run(self):
        try:
            client = SpectroSolHubClient(self.url, self.token)
            session = client.create_session(self.session_request)
            session_id = session["id"]
            total = len(self.image_files)

            for i, file_path in enumerate(self.image_files):
                jpeg_bytes = _image_to_jpeg_bytes(file_path)
                title = os.path.splitext(os.path.basename(file_path))[0]
                image_kind = "INTI_PARTNER"
                metadata = self.build_metadata_func(file_path)
                metadata_json = json.dumps(metadata) if metadata else None

                def on_part_progress(part, total_parts, idx=i):
                    self.progress.emit(idx, total, part, total_parts)

                client.upload_image(
                    session_id, title, image_kind, metadata_json,
                    jpeg_bytes, on_part_progress
                )

            if self.publish:
                try:
                    client.publish_session(session_id)
                except SpectroSolHubException:
                    pass  # still open in browser

            self.finished.emit(session_id)
        except (SpectroSolHubException, IOError) as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Wizard Widget (embeddable as a tab or in a dialog)
# ---------------------------------------------------------------------------

class SpectroSolHubWidget(QWidget):
    """3-step wizard for submitting images to SpectroSolHub.
    Can be embedded as a tab in the main window."""

    def __init__(self, parent=None, working_dir="", get_geom_func=None,
                 get_log_file_func=None, read_fits_func=None, langue='Fr',
                 version="1.2"):
        super().__init__(parent)
        self.working_dir = working_dir
        self.get_geom_func = get_geom_func
        self.get_log_file_func = get_log_file_func
        self.read_fits_func = read_fits_func
        self.langue = langue
        self.app_version = version

        self.current_step = 1
        self.total_steps = 3
        self.token = None
        self.base_url = os.environ.get("SPECTROSOLHUB_URL", DEFAULT_BASE_URL)
        self.selected_files = []
        self.image_checkboxes = []
        self.image_files_list = []
        self._inti_version = None  # (name, version) from FITS CREATOR header

        # Load persisted token
        self._load_config()

        self._build_ui()
        self._update_step()

    def set_working_dir(self, working_dir):
        """Update the working directory (called when the user changes directory)."""
        self.working_dir = working_dir
        # Reset image gallery so it reloads on next visit to step 2
        if 2 in self._step_widgets:
            del self._step_widgets[2]
            self.image_checkboxes.clear()
            self.image_files_list.clear()

    # ----- Config persistence -----

    def _config_path(self):
        return os.path.join(os.path.expanduser("~"), ".inti_partner_ssh.json")

    def _load_config(self):
        path = self._config_path()
        self._persisted_equipment = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    cfg = json.load(f)
                self.token = cfg.get("token")
                self._persisted_equipment = {
                    "telescope": cfg.get("telescope", ""),
                    "camera": cfg.get("camera", ""),
                    "mount": cfg.get("mount", ""),
                    "shg": cfg.get("shg", "Sol'Ex"),
                    "slit_width": cfg.get("slit_width", ""),
                    "slit_height": cfg.get("slit_height", ""),
                    "focal_length": cfg.get("focal_length", ""),
                    "aperture": cfg.get("aperture", ""),
                    "pixel_size": cfg.get("pixel_size", ""),
                    "binning": cfg.get("binning", ""),
                    "erf": cfg.get("erf", ""),
                }
            except Exception:
                pass

    def _save_config(self):
        path = self._config_path()
        cfg = {
            "token": self.token,
            "telescope": self._persisted_equipment.get("telescope", ""),
            "camera": self._persisted_equipment.get("camera", ""),
            "mount": self._persisted_equipment.get("mount", ""),
            "shg": self._persisted_equipment.get("shg", "Sol'Ex"),
            "slit_width": self._persisted_equipment.get("slit_width", ""),
            "slit_height": self._persisted_equipment.get("slit_height", ""),
            "focal_length": self._persisted_equipment.get("focal_length", ""),
            "aperture": self._persisted_equipment.get("aperture", ""),
            "pixel_size": self._persisted_equipment.get("pixel_size", ""),
            "binning": self._persisted_equipment.get("binning", ""),
            "erf": self._persisted_equipment.get("erf", ""),
        }
        try:
            with open(path, "w") as f:
                json.dump(cfg, f)
        except Exception:
            pass

    def _save_equipment(self):
        """Persist current equipment fields so the user doesn't have to re-enter them."""
        self._persisted_equipment = {
            "telescope": self.telescope_field.text().strip(),
            "camera": self.camera_field.text().strip(),
            "mount": self.mount_field.text().strip(),
            "shg": self.shg_combo.currentText(),
            "slit_width": self.slit_width_field.text().strip(),
            "slit_height": self.slit_height_field.text().strip(),
            "focal_length": self.focal_length_field.text().strip(),
            "aperture": self.aperture_field.text().strip(),
            "pixel_size": self.pixel_size_field.text().strip(),
            "binning": self.binning_field.text().strip(),
            "erf": self.erf_field.text().strip(),
        }
        self._save_config()

    def _clear_token(self):
        self.token = None
        self._save_config()

    # ----- UI construction -----

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_steps)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # Step label
        self.step_label = QLabel()
        self.step_label.setStyleSheet("font-size: 12px; color: gray;")
        main_layout.addWidget(self.step_label)

        # Content area
        self.content_area = QVBoxLayout()
        main_layout.addLayout(self.content_area, 1)

        # Navigation buttons
        btn_layout = QHBoxLayout()
        self.prev_btn = QPushButton(self.tr("Précédent"))
        self.next_btn = QPushButton(self.tr("Suivant"))
        self.prev_btn.clicked.connect(self._on_previous)
        self.next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self.prev_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.next_btn)
        main_layout.addLayout(btn_layout)

        # Step widgets (created lazily)
        self._step_widgets = {}

    def _clear_content(self):
        while self.content_area.count():
            item = self.content_area.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

    def _update_step(self):
        self.progress_bar.setValue(self.current_step)
        self.step_label.setText(
            self.tr("Étape {0} / {1}").replace("{0}", str(self.current_step)).replace("{1}", str(self.total_steps))
        )
        self.prev_btn.setEnabled(self.current_step > 1)
        if self.current_step == self.total_steps:
            self.next_btn.setText(self.tr("Envoyer"))
        else:
            self.next_btn.setText(self.tr("Suivant"))

        self._clear_content()
        step_widget = self._get_step_widget(self.current_step)
        self.content_area.addWidget(step_widget)

        if self.current_step == 1:
            self.next_btn.setEnabled(self.token is not None)
            if self.token:
                self._verify_existing_token()

    def _get_step_widget(self, step):
        if step not in self._step_widgets:
            if step == 1:
                self._step_widgets[step] = self._create_step1()
            elif step == 2:
                self._step_widgets[step] = self._create_step2()
            elif step == 3:
                self._step_widgets[step] = self._create_step3_metadata()
        # Refresh step 2 gallery when entering
        if step == 2:
            self._populate_gallery()
        if step == 3:
            self._prefill_metadata()
        return self._step_widgets[step]

    # ----- Navigation -----

    def _on_previous(self):
        if self.current_step > 1:
            self.current_step -= 1
            self._update_step()

    def _on_next(self):
        if not self._validate_current_step():
            return
        if self.current_step < self.total_steps:
            self.current_step += 1
            self._update_step()
        else:
            self._perform_upload()

    def _validate_current_step(self):
        if self.current_step == 1:
            if not self.token:
                QMessageBox.warning(self, "SpectroSolHub",
                                    self.tr("Veuillez vous connecter d'abord."))
                return False
        elif self.current_step == 2:
            if not self._get_selected_files():
                QMessageBox.warning(self, "SpectroSolHub",
                                    self.tr("Sélectionnez au moins une image."))
                return False
        elif self.current_step == 3:
            if not self.title_field.text().strip():
                QMessageBox.warning(self, "SpectroSolHub",
                                    self.tr("Le titre de la session est requis."))
                return False
            if not self.date_label.text().strip():
                QMessageBox.warning(self, "SpectroSolHub",
                                    self.tr("La date d'observation est requise.\n"
                                            "Aucune date n'a pu être extraite des fichiers."))
                return False
            # Custom spectral line validation
            if self.spectral_line_combo.currentText() == "Other":
                if not self.custom_line_label_field.text().strip():
                    QMessageBox.warning(self, "SpectroSolHub",
                                        self.tr("Le nom de la raie spectrale est requis."))
                    self.custom_line_label_field.setFocus()
                    return False
                if _float_or_none(self.custom_wavelength_field.text()) is None:
                    QMessageBox.warning(self, "SpectroSolHub",
                                        self.tr("La longueur d'onde (en Å) est requise."))
                    self.custom_wavelength_field.setFocus()
                    return False
            # Equipment fields are required in "Brand Model" format
            for field, label in [
                (self.telescope_field, self.tr("Télescope")),
                (self.camera_field, self.tr("Caméra")),
                (self.mount_field, self.tr("Monture")),
            ]:
                text = field.text().strip()
                if not text:
                    QMessageBox.warning(self, "SpectroSolHub",
                                        self.tr("{0} est requis.").replace("{0}", label))
                    field.setFocus()
                    return False
                if len(text.split()) < 2:
                    QMessageBox.warning(self, "SpectroSolHub",
                                        self.tr("{0} doit être au format \"Marque Modèle\" "
                                                "(ex: ZWO ASI174MM).").replace("{0}", label))
                    field.setFocus()
                    return False
            # Persist equipment for next time
            self._save_equipment()
        return True

    # ===================================================================
    # STEP 1: Authentication
    # ===================================================================

    def _create_step1(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel(self.tr("Connexion à SpectroSolHub"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        instructions = QLabel(self.tr(
            "Connectez-vous à votre compte SpectroSolHub pour partager vos images.\n"
            "Si vous n'avez pas de compte, créez-en un sur spectrosolhub.com."
        ))
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)

        # Login form
        self.login_form = QWidget()
        form_layout = QGridLayout(self.login_form)

        form_layout.addWidget(QLabel(self.tr("Utilisateur :")), 0, 0)
        self.username_field = QLineEdit()
        self.username_field.setPlaceholderText(self.tr("Nom d'utilisateur"))
        self.username_field.setMaximumWidth(300)
        form_layout.addWidget(self.username_field, 0, 1)

        form_layout.addWidget(QLabel(self.tr("Mot de passe :")), 1, 0)
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setMaximumWidth(300)
        form_layout.addWidget(self.password_field, 1, 1)

        self.totp_label = QLabel(self.tr("Code TOTP :"))
        self.totp_field = QLineEdit()
        self.totp_field.setPlaceholderText(self.tr("Optionnel"))
        self.totp_field.setMaximumWidth(300)
        self.totp_label.setVisible(False)
        self.totp_field.setVisible(False)
        form_layout.addWidget(self.totp_label, 2, 0)
        form_layout.addWidget(self.totp_field, 2, 1)

        layout.addWidget(self.login_form)

        self.login_btn = QPushButton(self.tr("Se connecter"))
        self.login_btn.setMaximumWidth(200)
        self.login_btn.clicked.connect(self._perform_login)
        layout.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.auth_status_label = QLabel()
        self.auth_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.auth_status_label)

        # Connected info (hidden initially)
        self.connected_widget = QWidget()
        conn_layout = QVBoxLayout(self.connected_widget)
        conn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connected_label = QLabel(self.tr("Connecté à SpectroSolHub"))
        self.connected_label.setStyleSheet("font-size: 14px; color: green;")
        self.connected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        conn_layout.addWidget(self.connected_label)

        disconnect_btn = QPushButton(self.tr("Se déconnecter"))
        disconnect_btn.setMaximumWidth(200)
        disconnect_btn.clicked.connect(self._disconnect)
        conn_layout.addWidget(disconnect_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.connected_widget.setVisible(False)
        layout.addWidget(self.connected_widget)

        register_btn = QPushButton(self.tr("Créer un compte"))
        register_btn.setFlat(True)
        register_btn.setStyleSheet("color: blue; text-decoration: underline;")
        register_btn.clicked.connect(
            lambda: webbrowser.open(self.base_url + "/register"))
        layout.addWidget(register_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return widget

    def _verify_existing_token(self):
        self.auth_status_label.setText(self.tr("Vérification du token..."))
        self.auth_status_label.setStyleSheet("color: gray;")
        self._token_worker = VerifyTokenWorker(self.base_url, self.token)
        self._token_worker.valid.connect(self._on_token_valid)
        self._token_worker.invalid.connect(self._on_token_invalid)
        self._token_worker.start()

    def _on_token_valid(self):
        self.auth_status_label.setText("")
        self.login_form.setVisible(False)
        self.login_btn.setVisible(False)
        self.connected_widget.setVisible(True)
        self.connected_label.setText(self.tr("Connecté à SpectroSolHub"))
        self.connected_label.setStyleSheet("font-size: 14px; color: green;")
        self.next_btn.setEnabled(True)

    def _on_token_invalid(self):
        self.token = None
        self._clear_token()
        self.auth_status_label.setText(self.tr("Token expiré, veuillez vous reconnecter."))
        self.auth_status_label.setStyleSheet("color: orange;")
        self.login_form.setVisible(True)
        self.login_btn.setVisible(True)
        self.connected_widget.setVisible(False)
        self.next_btn.setEnabled(False)

    def _perform_login(self):
        username = self.username_field.text().strip()
        password = self.password_field.text()
        totp = self.totp_field.text().strip() or None

        if not username or not password:
            self.auth_status_label.setText(self.tr("Saisissez vos identifiants."))
            self.auth_status_label.setStyleSheet("color: red;")
            return

        self.auth_status_label.setText(self.tr("Connexion en cours..."))
        self.auth_status_label.setStyleSheet("color: gray;")
        self.login_btn.setEnabled(False)

        token_name = f"INTI_Partner {platform.system()}"
        self._login_worker = LoginWorker(
            self.base_url, username, password, token_name, totp)
        self._login_worker.finished.connect(self._on_login_success)
        self._login_worker.error.connect(self._on_login_error)
        self._login_worker.start()

    def _on_login_success(self, token):
        self.token = token
        self._save_config()
        self.login_btn.setEnabled(True)
        self.login_form.setVisible(False)
        self.login_btn.setVisible(False)
        self.connected_widget.setVisible(True)
        self.auth_status_label.setText("")
        self.next_btn.setEnabled(True)

    def _on_login_error(self, message, status_code):
        self.login_btn.setEnabled(True)
        if status_code == 403:
            self.totp_label.setVisible(True)
            self.totp_field.setVisible(True)
            self.auth_status_label.setText(self.tr("Code TOTP requis."))
            self.auth_status_label.setStyleSheet("color: orange;")
        elif status_code == 401:
            self.auth_status_label.setText(self.tr("Identifiants invalides."))
            self.auth_status_label.setStyleSheet("color: red;")
        else:
            self.auth_status_label.setText(self.tr("Erreur : ") + message)
            self.auth_status_label.setStyleSheet("color: red;")

    def _disconnect(self):
        self.token = None
        self._clear_token()
        self.connected_widget.setVisible(False)
        self.login_form.setVisible(True)
        self.login_btn.setVisible(True)
        self.auth_status_label.setText("")
        self.next_btn.setEnabled(False)

    # ===================================================================
    # STEP 2: Image Selection
    # ===================================================================

    def _create_step2(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel(self.tr("Sélection des images"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        instruction = QLabel(self.tr(
            "Sélectionnez les images à envoyer à SpectroSolHub."
        ))
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        # Select all / Deselect all
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton(self.tr("Tout sélectionner"))
        select_all_btn.clicked.connect(self._select_all_images)
        deselect_all_btn = QPushButton(self.tr("Tout désélectionner"))
        deselect_all_btn.clicked.connect(self._deselect_all_images)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(deselect_all_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Scrollable gallery
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setSpacing(8)
        scroll.setWidget(self.gallery_widget)
        layout.addWidget(scroll, 1)

        return widget

    def _populate_gallery(self):
        # Clear existing
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.image_checkboxes.clear()
        self.image_files_list.clear()

        if not self.working_dir or not os.path.isdir(self.working_dir):
            return

        # Find eligible PNG images in working directory
        excluded_kinds = {"RAW"}
        preselected_kinds = {"DISK", "CLAHE", "MIXED"}

        files = sorted([
            f for f in os.listdir(self.working_dir)
            if f.lower().endswith(".png") and not f.startswith("st")
        ])

        col = 0
        row = 0
        cols_per_row = 4

        for filename in files:
            full_path = os.path.join(self.working_dir, filename)
            kind = _image_kind_from_filename(filename)
            if kind in excluded_kinds:
                continue

            self.image_files_list.append(full_path)

            # Card widget
            card = QFrame()
            card.setFrameShape(QFrame.Shape.Box)
            card.setStyleSheet(
                "QFrame { border: 1px solid lightgray; border-radius: 4px; "
                "background-color: white; padding: 4px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(2)
            card_layout.setContentsMargins(4, 4, 4, 4)

            # Thumbnail
            thumb = _make_thumbnail(full_path, 120)
            thumb_label = QLabel()
            if thumb:
                thumb_label.setPixmap(thumb)
            else:
                thumb_label.setText("?")
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb_label.setFixedSize(130, 130)
            card_layout.addWidget(thumb_label)

            # Checkbox + name
            cb = QCheckBox(filename[:30])
            cb.setToolTip(filename)
            cb.setChecked(kind in preselected_kinds)
            card_layout.addWidget(cb)
            self.image_checkboxes.append(cb)

            self.gallery_layout.addWidget(card, row, col)
            col += 1
            if col >= cols_per_row:
                col = 0
                row += 1

    def _select_all_images(self):
        for cb in self.image_checkboxes:
            cb.setChecked(True)

    def _deselect_all_images(self):
        for cb in self.image_checkboxes:
            cb.setChecked(False)

    def _get_selected_files(self):
        selected = []
        for i, cb in enumerate(self.image_checkboxes):
            if cb.isChecked():
                selected.append(self.image_files_list[i])
        return selected

    # ===================================================================
    # STEP 3: Session Metadata
    # ===================================================================

    def _create_step3_metadata(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel(self.tr("Métadonnées de la session"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        instruction = QLabel(self.tr(
            "Renseignez les informations sur votre observation."
        ))
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        row = 0

        grid.addWidget(QLabel(self.tr("Titre :")), row, 0)
        self.title_field = QLineEdit()
        self.title_field.setMinimumWidth(350)
        grid.addWidget(self.title_field, row, 1)
        row += 1

        grid.addWidget(QLabel(self.tr("Date d'observation :")), row, 0)
        self.date_label = QLabel()
        grid.addWidget(self.date_label, row, 1)
        row += 1

        grid.addWidget(QLabel(self.tr("Raie spectrale :")), row, 0)
        self.spectral_line_combo = QComboBox()
        self.spectral_line_combo.addItems(list(SPECTRAL_LINES.keys()))
        self.spectral_line_combo.currentTextChanged.connect(self._on_spectral_line_changed)
        grid.addWidget(self.spectral_line_combo, row, 1)
        row += 1

        # Custom spectral line fields (visible only when "Other" is selected)
        custom_line_layout = QHBoxLayout()
        custom_line_layout.addWidget(QLabel(self.tr("Nom :")))
        self.custom_line_label_field = QLineEdit()
        self.custom_line_label_field.setPlaceholderText(self.tr("ex: Fe XIV 5303"))
        self.custom_line_label_field.setMaximumWidth(150)
        custom_line_layout.addWidget(self.custom_line_label_field)
        custom_line_layout.addWidget(QLabel(self.tr("Longueur d'onde (Å) :")))
        self.custom_wavelength_field = QLineEdit()
        self.custom_wavelength_field.setMaximumWidth(100)
        self.custom_wavelength_field.setPlaceholderText(self.tr("ex: 5303.0"))
        custom_line_layout.addWidget(self.custom_wavelength_field)
        custom_line_layout.addStretch()
        self.custom_line_widget = QWidget()
        self.custom_line_widget.setLayout(custom_line_layout)
        self.custom_line_widget.setVisible(False)
        grid.addWidget(QLabel(""), row, 0)
        grid.addWidget(self.custom_line_widget, row, 1)
        row += 1

        # Equipment section
        equip_title = QLabel(self.tr("Équipement"))
        equip_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        grid.addWidget(equip_title, row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel(self.tr("Spectro :")), row, 0)
        self.shg_combo = QComboBox()
        self.shg_combo.addItems(list(SPECTROHELIOGRAPHS.keys()))
        self.shg_combo.setCurrentIndex(0)  # default to Sol'Ex
        self.shg_combo.currentTextChanged.connect(self._on_shg_changed)
        grid.addWidget(self.shg_combo, row, 1)
        row += 1

        slit_layout = QHBoxLayout()
        slit_layout.addWidget(QLabel(self.tr("Largeur (μm) :")))
        self.slit_width_field = QLineEdit()
        self.slit_width_field.setMaximumWidth(80)
        slit_layout.addWidget(self.slit_width_field)
        slit_layout.addWidget(QLabel(self.tr("Hauteur (mm) :")))
        self.slit_height_field = QLineEdit()
        self.slit_height_field.setMaximumWidth(80)
        slit_layout.addWidget(self.slit_height_field)
        slit_layout.addStretch()

        grid.addWidget(QLabel(self.tr("Fente :")), row, 0)
        slit_widget = QWidget()
        slit_widget.setLayout(slit_layout)
        grid.addWidget(slit_widget, row, 1)
        row += 1

        grid.addWidget(QLabel(self.tr("Télescope :")), row, 0)
        self.telescope_field = QLineEdit()
        self.telescope_field.setPlaceholderText(self.tr("Marque Modèle (ex: Takahashi FSQ-106ED)"))
        grid.addWidget(self.telescope_field, row, 1)
        row += 1

        tel_details = QHBoxLayout()
        tel_details.addWidget(QLabel(self.tr("Focale (mm) :")))
        self.focal_length_field = QLineEdit()
        self.focal_length_field.setMaximumWidth(80)
        tel_details.addWidget(self.focal_length_field)
        tel_details.addWidget(QLabel(self.tr("Ouverture (mm) :")))
        self.aperture_field = QLineEdit()
        self.aperture_field.setMaximumWidth(80)
        tel_details.addWidget(self.aperture_field)
        tel_details.addStretch()
        tel_details_widget = QWidget()
        tel_details_widget.setLayout(tel_details)
        grid.addWidget(QLabel(""), row, 0)
        grid.addWidget(tel_details_widget, row, 1)
        row += 1

        grid.addWidget(QLabel(self.tr("Caméra :")), row, 0)
        self.camera_field = QLineEdit()
        self.camera_field.setPlaceholderText(self.tr("Marque Modèle (ex: ZWO ASI174MM)"))
        grid.addWidget(self.camera_field, row, 1)
        row += 1

        cam_details = QHBoxLayout()
        cam_details.addWidget(QLabel(self.tr("Pixel (μm) :")))
        self.pixel_size_field = QLineEdit()
        self.pixel_size_field.setMaximumWidth(80)
        cam_details.addWidget(self.pixel_size_field)
        cam_details.addStretch()
        cam_details_widget = QWidget()
        cam_details_widget.setLayout(cam_details)
        grid.addWidget(QLabel(""), row, 0)
        grid.addWidget(cam_details_widget, row, 1)
        row += 1

        grid.addWidget(QLabel(self.tr("Monture :")), row, 0)
        self.mount_field = QLineEdit()
        self.mount_field.setPlaceholderText(self.tr("Marque Modèle (ex: SkyWatcher EQ6-R)"))
        grid.addWidget(self.mount_field, row, 1)
        row += 1

        # Observation parameters
        obs_title = QLabel(self.tr("Observation"))
        obs_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        grid.addWidget(obs_title, row, 0, 1, 2)
        row += 1

        obs_details = QHBoxLayout()
        obs_details.addWidget(QLabel(self.tr("Binning :")))
        self.binning_field = QLineEdit("1")
        self.binning_field.setMaximumWidth(50)
        obs_details.addWidget(self.binning_field)
        obs_details.addWidget(QLabel(self.tr("Filtre ERF :")))
        self.erf_field = QLineEdit()
        self.erf_field.setMaximumWidth(200)
        self.erf_field.setPlaceholderText(self.tr("ex: ND 16"))
        obs_details.addWidget(self.erf_field)
        obs_details.addStretch()
        obs_details_widget = QWidget()
        obs_details_widget.setLayout(obs_details)
        grid.addWidget(obs_details_widget, row, 0, 1, 2)
        row += 1

        grid.addWidget(QLabel(self.tr("Notes :")), row, 0)
        self.notes_field = QTextEdit()
        self.notes_field.setMaximumHeight(80)
        self.notes_field.setPlaceholderText(self.tr(
            "Vous pouvez ajouter des notes sur votre session d'observation ici. "
            "Les notes peuvent contenir des hashtags (ex. #stack, #flare, ...) "
            "que vous pouvez utiliser pour classer vos observations."
        ))
        grid.addWidget(self.notes_field, row, 1)
        row += 1

        self.publish_checkbox = QCheckBox(self.tr("Publier immédiatement"))
        grid.addWidget(self.publish_checkbox, row, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return widget

    def _on_spectral_line_changed(self, line_name):
        """Show/hide custom spectral line fields when 'Other' is selected."""
        self.custom_line_widget.setVisible(line_name == "Other")

    def _on_shg_changed(self, shg_name):
        """Update slit fields when the SHG selection changes."""
        shg = SPECTROHELIOGRAPHS.get(shg_name)
        if shg:
            self.slit_width_field.setText(str(shg["slitWidthMicrons"]))
            self.slit_height_field.setText(str(shg["slitHeightMillimeters"]))

    def _find_companion_fits(self, file_path):
        """Find a companion FITS file for a PNG/JPG image.
        INTI produces _recon.fits and _cont.fits alongside PNG outputs.
        Uses get_baseline to strip suffixes like _disk, _clahe, etc."""
        try:
            from inti_partner import get_baseline
        except ImportError:
            get_baseline = None

        base_no_ext = os.path.splitext(file_path)[0]
        directory = os.path.dirname(file_path)

        # If it's already a FITS file, return it
        if file_path.lower().endswith((".fits", ".fit")):
            return file_path

        # Try stripping image suffixes to find the baseline
        if get_baseline:
            baseline = get_baseline(base_no_ext)
        else:
            baseline = base_no_ext

        # Search for companion FITS files
        for suffix in ("_recon.fits", "_cont.fits", ".fits"):
            candidate = baseline + suffix
            if os.path.exists(candidate):
                return candidate
            # Also try in parent directory (for Clahe/Complements subdirs)
            parent_candidate = os.path.join(
                os.path.dirname(directory), os.path.basename(baseline) + suffix)
            if os.path.exists(parent_candidate):
                return parent_candidate

        return None

    def _find_fits_header(self, file_path):
        """Get FITS header for a file, looking for companion FITS if needed."""
        if not self.read_fits_func:
            return None
        fits_path = self._find_companion_fits(file_path)
        if fits_path is None:
            return None
        try:
            _, header = self.read_fits_func(fits_path)
            return header
        except Exception:
            return None

    def _extract_inti_version(self, selected_files):
        """Try to extract INTI version from FITS CREATOR header (e.g. 'INTI 7.0.3').
        Looks for companion FITS files if needed.
        Returns (software_name, software_version) or None."""
        for f in selected_files:
            header = self._find_fits_header(f)
            if header is not None:
                creator = header.get("CREATOR", "")
                if creator.startswith("INTI "):
                    return "INTI", creator[5:]
        return None

    def _prefill_metadata(self):
        selected = self._get_selected_files()
        if not selected:
            return

        # Try to detect INTI version from FITS headers
        self._inti_version = self._extract_inti_version(selected)

        # Guess spectral line from filenames
        line, wavelength = _guess_spectral_line(selected[0])
        idx = self.spectral_line_combo.findText(line)
        if idx >= 0:
            self.spectral_line_combo.setCurrentIndex(idx)

        # Try to get observation date from first selected file
        date_str = self._extract_date(selected[0])
        if date_str:
            self.date_label.setText(date_str)
            self.title_field.setText(f"{line} - {date_str[:10]}")
        else:
            self.title_field.setText(line)

        # Restore persisted equipment (only if fields are empty)
        for field, key in [
            (self.telescope_field, "telescope"),
            (self.camera_field, "camera"),
            (self.mount_field, "mount"),
            (self.focal_length_field, "focal_length"),
            (self.aperture_field, "aperture"),
            (self.pixel_size_field, "pixel_size"),
            (self.binning_field, "binning"),
            (self.erf_field, "erf"),
        ]:
            if not field.text().strip():
                field.setText(self._persisted_equipment.get(key, ""))

        # Restore SHG selection and slit values
        shg_name = self._persisted_equipment.get("shg", "Sol'Ex")
        idx = self.shg_combo.findText(shg_name)
        if idx >= 0:
            self.shg_combo.setCurrentIndex(idx)
        # Restore persisted slit overrides, or default from SHG
        persisted_sw = self._persisted_equipment.get("slit_width", "")
        persisted_sh = self._persisted_equipment.get("slit_height", "")
        if persisted_sw:
            self.slit_width_field.setText(persisted_sw)
        elif not self.slit_width_field.text().strip():
            self._on_shg_changed(self.shg_combo.currentText())
        if persisted_sh:
            self.slit_height_field.setText(persisted_sh)

    def _extract_date(self, filepath):
        """Try to extract observation date from FITS header, log file, or filename.
        Returns an ISO 8601 UTC date string (e.g. '2024-04-13T13:16:33.00Z')."""
        ext = os.path.splitext(filepath)[1].lower()

        # 1. FITS header (or companion FITS): DATE-OBS is already in ISO format
        header = self._find_fits_header(filepath)
        if header is not None:
            date_obs = header.get("DATE-OBS", "")
            if date_obs:
                return self._ensure_utc(date_obs)

        # 2. Log file: SER date UTC :"2024-04-13T13:16:33.8371717"
        if self.get_log_file_func:
            try:
                log_file = self.get_log_file_func(filepath)
                if log_file and log_file != '':
                    date_str = _get_date_from_log(log_file)
                    if date_str:
                        return self._ensure_utc(date_str)
            except Exception:
                pass

        # 3. Filename pattern: _2024-04-13T13-16-33_
        basename = os.path.basename(filepath)
        m = re.search(r'(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})', basename)
        if m:
            return f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}.00Z"

        return ""

    @staticmethod
    def _ensure_utc(date_str):
        """Ensure a date string ends with Z (UTC indicator)."""
        date_str = date_str.strip()
        if not date_str:
            return ""
        # Already has timezone info
        if date_str.endswith("Z") or "+" in date_str[10:]:
            return date_str
        # Append Z to indicate UTC
        return date_str + "Z"

    # ===================================================================
    # Upload
    # ===================================================================

    def _perform_upload(self):
        self.next_btn.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self.next_btn.setText(self.tr("Envoi en cours..."))
        self.progress_bar.setRange(0, 0)  # indeterminate

        selected_files = self._get_selected_files()
        session_request = self._build_session_request()

        self._upload_worker = UploadWorker(
            self.base_url, self.token, session_request, selected_files,
            self.publish_checkbox.isChecked(), self._build_image_metadata
        )
        self._upload_worker.progress.connect(self._on_upload_progress)
        self._upload_worker.finished.connect(self._on_upload_finished)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.start()

    def _on_upload_progress(self, img_idx, total_images, part, total_parts):
        total = total_images * 100
        current = img_idx * 100 + int(part / total_parts * 100)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.next_btn.setText(
            self.tr("Envoi image {0}/{1}...").replace(
                "{0}", str(img_idx + 1)).replace("{1}", str(total_images))
        )

    def _on_upload_finished(self, session_id):
        self.progress_bar.setRange(0, self.total_steps)
        self.progress_bar.setValue(self.total_steps)
        self.next_btn.setText(self.tr("Envoyé !"))
        self.prev_btn.setEnabled(False)
        url = f"{self.base_url}/observation/{session_id}"
        webbrowser.open(url)
        # Reset wizard to step 1 for next use
        self.current_step = 1
        if 2 in self._step_widgets:
            del self._step_widgets[2]
            self.image_checkboxes.clear()
            self.image_files_list.clear()
        QMessageBox.information(self, "SpectroSolHub",
                                self.tr("Images envoyées avec succès !"))
        self._update_step()

    def _on_upload_error(self, message):
        self.progress_bar.setRange(0, self.total_steps)
        self.progress_bar.setValue(self.current_step)
        self.next_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.next_btn.setText(self.tr("Envoyer"))
        QMessageBox.critical(self, "SpectroSolHub",
                             self.tr("Erreur lors de l'envoi : ") + message)

    def _get_effective_spectral_line(self):
        """Return (label, wavelength) taking custom fields into account."""
        line = self.spectral_line_combo.currentText()
        if line == "Other":
            custom_label = self.custom_line_label_field.text().strip()
            custom_wl = _float_or_none(self.custom_wavelength_field.text())
            return custom_label or "Other", custom_wl
        return line, SPECTRAL_LINES.get(line)

    def _build_session_request(self):
        spectral_line, wavelength = self._get_effective_spectral_line()

        # Split brand/model for telescope, camera, mount
        # Matches JSol'Ex CreateSessionRequest structure
        telescope_info = None
        telescope_text = self.telescope_field.text().strip()
        if telescope_text:
            brand, model = _split_brand_model(telescope_text)
            telescope_info = {
                "brand": brand,
                "model": model,
                "focalLengthMm": _int_or_none(self.focal_length_field.text()),
                "apertureMm": _int_or_none(self.aperture_field.text()),
            }

        camera_info = None
        camera_text = self.camera_field.text().strip()
        if camera_text:
            brand, model = _split_brand_model(camera_text)
            camera_info = {
                "brand": brand,
                "model": model,
                "pixelSizeUm": _float_or_none(self.pixel_size_field.text()),
                "binning": _int_or_none(self.binning_field.text()),
            }

        mount_info = None
        mount_text = self.mount_field.text().strip()
        if mount_text:
            brand, model = _split_brand_model(mount_text)
            mount_info = {
                "brand": brand,
                "model": model,
                "type": "EQUATORIAL",
            }

        erf_text = self.erf_field.text().strip() or None

        # Spectroheliograph from dropdown, with user-editable slit values
        shg_name = self.shg_combo.currentText()
        spectro_info = None
        shg = SPECTROHELIOGRAPHS.get(shg_name)
        if shg:
            spectro_info = dict(shg)  # copy so we don't mutate the constant
            try:
                spectro_info["slitWidthMicrons"] = float(self.slit_width_field.text())
            except (ValueError, TypeError):
                pass
            try:
                spectro_info["slitHeightMillimeters"] = float(self.slit_height_field.text())
            except (ValueError, TypeError):
                pass

        date_str = self.date_label.text() or None

        return {
            "title": self.title_field.text().strip(),
            "observationDate": date_str,
            "spectralLine": spectral_line,
            "customWavelengthAngstroms": wavelength,
            "spectroheliograph": spectro_info,
            "telescope": telescope_info,
            "camera": camera_info,
            "mount": mount_info,
            "energyRejectionFilter": erf_text,
            "latitude": None,
            "longitude": None,
            "notes": self.notes_field.toPlainText().strip() or None,
            "softwareName": self._inti_version[0] if self._inti_version else "INTI Partner",
            "softwareVersion": self._inti_version[1] if self._inti_version else self.app_version,
        }

    def _build_image_metadata(self, file_path):
        """Build image metadata dict for a given file, similar to JSol'Ex ImageMetadata.

        Fields match the JSol'Ex ImageMetadata record:
        solarB0, solarL0, solarP (degrees), carringtonRotation,
        centerX, centerY, solarRadius, wavelengthAngstroms,
        spectralLine, dateObs.
        """
        metadata = {}
        ext = os.path.splitext(file_path)[1].lower()

        # Try to get observation date
        date_obs = self._extract_date(file_path)

        # Solar parameters (P, B0, L0) from date
        if date_obs and angle_P_B0:
            try:
                # angle_P_B0 returns (str, str, str, str)
                p_str, b0_str, l0_str, _ = angle_P_B0(date_obs)
                metadata["solarP"] = float(p_str)
                metadata["solarB0"] = float(b0_str)
                metadata["solarL0"] = float(l0_str)
            except Exception:
                pass
        # Carrington rotation: compute directly (INTI's value is incorrect)
        if date_obs:
            try:
                metadata["carringtonRotation"] = _carrington_rotation(date_obs)
            except Exception:
                pass

        if date_obs:
            metadata["dateObs"] = date_obs

        # Try to get a FITS header: either from the file itself, or from a
        # companion FITS file (INTI produces _recon.fits / _cont.fits alongside PNGs)
        fits_header = self._find_fits_header(file_path)

        # Disk geometry from FITS header or image analysis
        if fits_header is not None:
            if "CENTER_X" in fits_header:
                metadata["centerX"] = int(fits_header["CENTER_X"])
            if "CENTER_Y" in fits_header:
                metadata["centerY"] = int(fits_header["CENTER_Y"])
            if "SOLAR_R" in fits_header:
                metadata["solarRadius"] = int(fits_header["SOLAR_R"])
        elif self.get_geom_func:
            try:
                img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    cx, cy, sr = self.get_geom_func(file_path, img)
                    if sr and int(sr) > 0:
                        metadata["centerX"] = int(cx)
                        metadata["centerY"] = int(cy)
                        metadata["solarRadius"] = int(sr)
            except Exception:
                pass

        # Spectral line info (using JSol'Ex SpectralRay labels)
        line, wavelength = _guess_spectral_line(file_path)
        if wavelength:
            metadata["wavelengthAngstroms"] = wavelength
        metadata["spectralLine"] = line

        # Instrument (SHG) info from selected spectroheliograph, with user slit overrides
        shg_name = self.shg_combo.currentText()
        shg = SPECTROHELIOGRAPHS.get(shg_name)
        if shg:
            metadata["instrument"] = shg["name"]
            metadata["cameraFocalLength"] = shg["cameraFocalLength"]
            metadata["collimatorFocalLength"] = shg["collimatorFocalLength"]
            metadata["grating"] = shg["gratingDensity"]
            metadata["gratingOrder"] = shg["gratingOrder"]
            metadata["shgAngle"] = shg["totalAngleDegrees"]
            # Use user-edited slit values
            try:
                metadata["slitWidth"] = float(self.slit_width_field.text()) / 1000.0  # μm → mm
            except (ValueError, TypeError):
                metadata["slitWidth"] = shg["slitWidthMicrons"] / 1000.0
            try:
                metadata["slitHeight"] = float(self.slit_height_field.text())
            except (ValueError, TypeError):
                metadata["slitHeight"] = shg["slitHeightMillimeters"]

        # Camera info from field (brand model)
        camera_text = self.camera_field.text().strip()
        if camera_text:
            metadata["camera"] = camera_text

        # Telescope: focal length, aperture
        fl = _float_or_none(self.focal_length_field.text())
        if fl is not None:
            metadata["focalLength"] = fl
        ap = _int_or_none(self.aperture_field.text())
        if ap is not None:
            metadata["aperture"] = ap

        # Camera: pixel size, binning
        px = _float_or_none(self.pixel_size_field.text())
        if px is not None:
            metadata["pixelSizeMm"] = px / 1000.0  # μm → mm
        bn = _int_or_none(self.binning_field.text())
        if bn is not None:
            metadata["binning"] = bn

        # Energy rejection filter
        erf = self.erf_field.text().strip()
        if erf:
            metadata["energyRejectionFilter"] = erf

        # P angle correction: detect from FITS header (SOLAR_P) or log file
        p_corrected = False
        if fits_header is not None:
            try:
                solar_p = fits_header.get("SOLAR_P", 0.0)
                p_corrected = float(solar_p) != 0.0
            except Exception:
                pass
        elif self.get_log_file_func:
            try:
                log_file = self.get_log_file_func(file_path)
                if log_file and log_file != '':
                    p_val = _get_p_angle_from_log(log_file)
                    if p_val is not None:
                        p_corrected = p_val != 0.0
            except Exception:
                pass
        metadata["pAngleCorrected"] = p_corrected

        return metadata if metadata else None
