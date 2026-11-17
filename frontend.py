from datetime import datetime
import requests
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

STYLESHEET = """
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #1e293b;
}
QWidget#Sidebar {
    background-color: #f4f7fa;
    border-right: 1px solid #e2e8f0;
}
QWidget#HeaderBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}
QWidget#MainArea {
    background-color: #f8fafc;
}
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QPushButton#NavBtn {
    text-align: left;
    padding: 10px 14px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: #475569;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#NavBtn:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}
QPushButton#NavBtn:checked {
    background-color: #e0e7ff;
    color: #4338ca;
    font-weight: 600;
}
QPushButton#PrimaryBtn {
    background-color: #10b981;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #059669;
}
QPushButton#SecondaryBtn {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 500;
    font-size: 13px;
}
QPushButton#SecondaryBtn:hover {
    background-color: #f1f5f9;
}
QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus {
    border: 1px solid #6366f1;
}
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    gridline-color: #f1f5f9;
    font-size: 13px;
}
QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-weight: 600;
    font-size: 12px;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}
QTableWidget::item {
    padding: 8px;
}
"""


class ApiWorker(QThread):
    finished = pyqtSignal(object, str)

    def __init__(self, method, url, payload=None):
        super().__init__()
        self.method = method
        self.url = url
        self.payload = payload

    def run(self):
        try:
            r = requests.request(self.method, self.url, json=self.payload, timeout=3.5)
            data = r.json() if r.content else {}
            if r.status_code >= 400:
                self.finished.emit(None, data.get("error") or data.get("message") or f"HTTP {r.status_code}")
            else:
                self.finished.emit(data, "")
        except requests.exceptions.ConnectionError:
            self.finished.emit(None, "Backend is offline.")
        except Exception as e:
            self.finished.emit(None, str(e))


def make_pill(text, bg, fg):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background-color: {bg}; color: {fg}; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 700;"
    )
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.addWidget(lbl)
    lay.addStretch()
    return wrap


class MemberDialog(QDialog):
    def __init__(self, parent=None, member=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Member" if member else "Register Member")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_in = QLineEdit(member["full_name"] if member else "")
        self.code_in = QLineEdit(member["member_code"] if member else "")
        self.uid_in = QLineEdit((member.get("rfid_uid") or "") if member else "")
        self.phone_in = QLineEdit((member.get("phone") or "") if member else "")
        self.status_in = QComboBox()
        self.status_in.addItems(["ACTIVE", "INACTIVE"])
        if member:
            self.status_in.setCurrentText(member["status"])

        self.name_in.setPlaceholderText("Juan Dela Cruz")
        self.code_in.setPlaceholderText("GYM-0001")
        self.uid_in.setPlaceholderText("04 B9 60 A7")

        form.addRow("Full Name *", self.name_in)
        form.addRow("Member Code *", self.code_in)
        form.addRow("RFID UID", self.uid_in)
        form.addRow("Phone", self.phone_in)
        form.addRow("Status", self.status_in)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def payload(self):
        return {
            "full_name": self.name_in.text().strip(),
            "member_code": self.code_in.text().strip().upper(),
            "rfid_uid": self.uid_in.text().strip().upper() or None,
            "phone": self.phone_in.text().strip() or None,
            "status": self.status_in.currentText(),
        }


class GymWindow(QMainWindow):
    def __init__(self, api_url="http://127.0.0.1:8000"):
        super().__init__()
        self.api_url = api_url
        self.workers = []
        self.members_data = []

        self.setWindowTitle("GymLane — Gym Management & Attendance")
        self.resize(1120, 700)
        self.setStyleSheet(STYLESHEET)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(16, 20, 16, 20)
        side_lay.setSpacing(6)

        logo = QLabel("❖  GymLane")
        logo.setStyleSheet("font-size: 18px; font-weight: 800; color: #4338ca; margin-bottom: 16px;")
        side_lay.addWidget(logo)

        main_sec = QLabel("MAIN")
        main_sec.setStyleSheet("font-size: 10px; font-weight: 700; color: #94a3b8; margin-top: 6px;")
        side_lay.addWidget(main_sec)

        self.nav_btns = []
        nav_specs = [
            ("Dashboard", 0),
            ("Attendance History", 1),
            ("Members", 2),
            ("RFID Simulator", 3),
            ("Hardware & Settings", 4),
        ]
        for label, idx in nav_specs:
            if idx == 2:
                team_sec = QLabel("MANAGEMENT")
                team_sec.setStyleSheet("font-size: 10px; font-weight: 700; color: #94a3b8; margin-top: 14px;")
                side_lay.addWidget(team_sec)
            btn = QPushButton(label)
            btn.setObjectName("NavBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, i=idx: self.go_page(i))
            side_lay.addWidget(btn)
            self.nav_btns.append(btn)

        side_lay.addStretch()

        self.conn_pill = QLabel("●  Checking API...")
        self.conn_pill.setStyleSheet(
            "background-color: #e2e8f0; color: #475569; border-radius: 8px; padding: 8px 10px; font-size: 12px; font-weight: 600;"
        )
        side_lay.addWidget(self.conn_pill)
        outer.addWidget(sidebar)

        # Right Column (Header + Content)
        right_col = QWidget()
        right_col.setObjectName("MainArea")
        right_lay = QVBoxLayout(right_col)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # Top Header Bar
        header = QWidget()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(68)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 10, 24, 10)

        greet_box = QVBoxLayout()
        greet_box.setSpacing(2)
        welcome_lbl = QLabel("Welcome, Admin")
        welcome_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a;")
        date_str = datetime.now().strftime("Today is %A, %d %B %Y • %I:%M %p")
        self.date_lbl = QLabel(date_str)
        self.date_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        greet_box.addWidget(welcome_lbl)
        greet_box.addWidget(self.date_lbl)
        h_lay.addLayout(greet_box)

        h_lay.addStretch()

        self.quick_search = QLineEdit()
        self.quick_search.setPlaceholderText("Quick search member or UID...")
        self.quick_search.setFixedWidth(260)
        self.quick_search.returnPressed.connect(self.on_quick_search)
        h_lay.addWidget(self.quick_search)

        quick_scan_btn = QPushButton("→ Simulate Scan")
        quick_scan_btn.setObjectName("PrimaryBtn")
        quick_scan_btn.clicked.connect(lambda: self.go_page(3))
        h_lay.addWidget(quick_scan_btn)

        right_lay.addWidget(header)

        # Pages Stack
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_dashboard_page())
        self.stack.addWidget(self.build_attendance_page())
        self.stack.addWidget(self.build_members_page())
        self.stack.addWidget(self.build_simulator_page())
        self.stack.addWidget(self.build_settings_page())
        right_lay.addWidget(self.stack)

        outer.addWidget(right_col)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_health)
        self.timer.start(4000)

        self.go_page(0)
        self.check_health()

    def call_api(self, method, path, payload=None, cb=None):
        w = ApiWorker(method, f"{self.api_url}{path}", payload)
        if cb:
            w.finished.connect(cb)
        self.workers.append(w)
        w.start()

    def go_page(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.setChecked(i == idx)
        if idx == 0:
            self.load_dashboard()
        elif idx == 1:
            self.load_attendance()
        elif idx == 2:
            self.load_members()
        elif idx == 4:
            self.check_health()

    def on_quick_search(self):
        text = self.quick_search.text().strip()
        self.member_search.setText(text)
        self.go_page(2)

    def check_health(self):
        self.date_lbl.setText(datetime.now().strftime("Today is %A, %d %B %Y • %I:%M %p"))

        def done(data, err):
            if data and data.get("status") == "ok":
                self.conn_pill.setText("●  Backend Online")
                self.conn_pill.setStyleSheet(
                    "background-color: #dcfce7; color: #15803d; border-radius: 8px; padding: 8px 10px; font-size: 12px; font-weight: 600;"
                )
                self.settings_status.setText("ONLINE (Ready for Desktop & ESP32)")
                self.settings_status.setStyleSheet("color: #15803d; font-weight: 700;")
            else:
                self.conn_pill.setText("●  Backend Offline")
                self.conn_pill.setStyleSheet(
                    "background-color: #fee2e2; color: #b91c1c; border-radius: 8px; padding: 8px 10px; font-size: 12px; font-weight: 600;"
                )
                self.settings_status.setText(f"OFFLINE ({err})")
                self.settings_status.setStyleSheet("color: #b91c1c; font-weight: 700;")

        self.call_api("GET", "/api/health", cb=done)

    # --- PAGE 0: DASHBOARD ---
    def build_dashboard_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        sub = QLabel("Overview of active gym memberships and today's check-in activity.")
        sub.setStyleSheet("font-size: 13px; color: #64748b;")
        lay.addWidget(title)
        lay.addWidget(sub)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.stat_active = self.make_stat_card("Active Members", "0", "#10b981")
        self.stat_today = self.make_stat_card("Check-ins Today", "0", "#6366f1")
        self.stat_total = self.make_stat_card("Total Registered", "0", "#0ea5e9")
        cards.addWidget(self.stat_active)
        cards.addWidget(self.stat_today)
        cards.addWidget(self.stat_total)
        lay.addLayout(cards)

        card = QFrame()
        card.setObjectName("Card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(16, 16, 16, 16)
        c_lay.addWidget(QLabel("Recent Check-ins"))

        self.dash_table = QTableWidget(0, 5)
        self.dash_table.setHorizontalHeaderLabels(["Member Name", "Member Code", "RFID UID", "Check-in Time", "Status"])
        self.dash_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dash_table.verticalHeader().setVisible(False)
        self.dash_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        c_lay.addWidget(self.dash_table)
        lay.addWidget(card)
        return page

    def make_stat_card(self, label, val, accent):
        box = QFrame()
        box.setObjectName("Card")
        l = QVBoxLayout(box)
        l.setContentsMargins(18, 16, 18, 16)
        t = QLabel(label)
        t.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748b;")
        v = QLabel(val)
        v.setObjectName("Val")
        v.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {accent};")
        l.addWidget(t)
        l.addWidget(v)
        return box

    def load_dashboard(self):
        def done(data, err):
            if not data:
                return
            self.stat_active.findChild(QLabel, "Val").setText(str(data["active_members"]))
            self.stat_today.findChild(QLabel, "Val").setText(str(data["today_attendance"]))
            self.stat_total.findChild(QLabel, "Val").setText(str(data["total_members"]))
            recs = data["recent"]
            self.dash_table.setRowCount(len(recs))
            for i, r in enumerate(recs):
                dt = datetime.fromisoformat(r["scan_time"]).astimezone().strftime("%d/%m/%Y • %I:%M %p")
                self.dash_table.setItem(i, 0, QTableWidgetItem(r["full_name"]))
                self.dash_table.setItem(i, 1, QTableWidgetItem(r["member_code"]))
                self.dash_table.setItem(i, 2, QTableWidgetItem(r["scanned_uid"]))
                self.dash_table.setItem(i, 3, QTableWidgetItem(dt))
                self.dash_table.setCellWidget(i, 4, make_pill("Present", "#dcfce7", "#15803d"))

        self.call_api("GET", "/api/stats", cb=done)

    # --- PAGE 1: ATTENDANCE HISTORY ---
    def build_attendance_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel("History")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        sub = QLabel("View member check-in logs and RFID verification records.")
        sub.setStyleSheet("font-size: 13px; color: #64748b;")
        lay.addWidget(title)
        lay.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(16, 16, 16, 16)
        c_lay.setSpacing(12)

        top = QHBoxLayout()
        self.att_search = QLineEdit()
        self.att_search.setPlaceholderText("Search by name, code, or RFID UID...")
        self.att_search.setFixedWidth(300)
        self.att_search.returnPressed.connect(self.load_attendance)
        ref_btn = QPushButton("Refresh")
        ref_btn.setObjectName("SecondaryBtn")
        ref_btn.clicked.connect(self.load_attendance)
        top.addWidget(self.att_search)
        top.addStretch()
        top.addWidget(ref_btn)
        c_lay.addLayout(top)

        self.att_table = QTableWidget(0, 6)
        self.att_table.setHorizontalHeaderLabels(["Date", "Punch-In", "Member Name", "Member Code", "RFID UID", "Status"])
        self.att_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.att_table.verticalHeader().setVisible(False)
        self.att_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        c_lay.addWidget(self.att_table)

        lay.addWidget(card)
        return page

    def load_attendance(self):
        q = self.att_search.text().strip()
        path = f"/api/attendance?search={q}" if q else "/api/attendance"

        def done(data, err):
            if not data:
                return
            recs = data["records"]
            self.att_table.setRowCount(len(recs))
            for i, r in enumerate(recs):
                dt = datetime.fromisoformat(r["scan_time"]).astimezone()
                self.att_table.setItem(i, 0, QTableWidgetItem(dt.strftime("%d/%m/%Y")))
                self.att_table.setItem(i, 1, QTableWidgetItem(dt.strftime("%I:%M %p")))
                self.att_table.setItem(i, 2, QTableWidgetItem(r["full_name"]))
                self.att_table.setItem(i, 3, QTableWidgetItem(r["member_code"]))
                self.att_table.setItem(i, 4, QTableWidgetItem(r["scanned_uid"]))
                self.att_table.setCellWidget(i, 5, make_pill("Present", "#dcfce7", "#15803d"))

        self.call_api("GET", path, cb=done)

    # --- PAGE 2: MEMBERS ---
    def build_members_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        header = QHBoxLayout()
        t_box = QVBoxLayout()
        title = QLabel("Members")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        sub = QLabel("Register members, assign RFID cards, and manage active status.")
        sub.setStyleSheet("font-size: 13px; color: #64748b;")
        t_box.addWidget(title)
        t_box.addWidget(sub)
        header.addLayout(t_box)
        header.addStretch()

        add_btn = QPushButton("+ Add Member")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self.add_member_dialog)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("SecondaryBtn")
        edit_btn.clicked.connect(self.edit_member_dialog)

        deact_btn = QPushButton("Deactivate")
        deact_btn.setObjectName("SecondaryBtn")
        deact_btn.clicked.connect(self.deactivate_selected)

        header.addWidget(add_btn)
        header.addWidget(edit_btn)
        header.addWidget(deact_btn)
        lay.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(16, 16, 16, 16)

        self.member_search = QLineEdit()
        self.member_search.setPlaceholderText("Search member name, code, or RFID UID...")
        self.member_search.setFixedWidth(300)
        self.member_search.returnPressed.connect(self.load_members)
        c_lay.addWidget(self.member_search)

        self.mem_table = QTableWidget(0, 5)
        self.mem_table.setHorizontalHeaderLabels(["Member Code", "Full Name", "RFID UID", "Phone", "Status"])
        self.mem_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mem_table.verticalHeader().setVisible(False)
        self.mem_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mem_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.mem_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        c_lay.addWidget(self.mem_table)

        lay.addWidget(card)
        return page

    def load_members(self):
        q = self.member_search.text().strip()
        path = f"/api/members?search={q}" if q else "/api/members"

        def done(data, err):
            if not data:
                return
            self.members_data = data["members"]
            self.mem_table.setRowCount(len(self.members_data))
            for i, m in enumerate(self.members_data):
                self.mem_table.setItem(i, 0, QTableWidgetItem(m["member_code"]))
                self.mem_table.setItem(i, 1, QTableWidgetItem(m["full_name"]))
                self.mem_table.setItem(i, 2, QTableWidgetItem(m["rfid_uid"] or "Unassigned"))
                self.mem_table.setItem(i, 3, QTableWidgetItem(m["phone"] or "—"))
                if m["status"] == "ACTIVE":
                    self.mem_table.setCellWidget(i, 4, make_pill("ACTIVE", "#dcfce7", "#15803d"))
                else:
                    self.mem_table.setCellWidget(i, 4, make_pill("INACTIVE", "#fee2e2", "#b91c1c"))

        self.call_api("GET", path, cb=done)

    def add_member_dialog(self):
        dlg = MemberDialog(self)
        if dlg.exec():
            def done(data, err):
                if err:
                    QMessageBox.warning(self, "Error", err)
                else:
                    self.load_members()
            self.call_api("POST", "/api/members", dlg.payload(), cb=done)

    def edit_member_dialog(self):
        row = self.mem_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Row", "Select a member first.")
            return
        m = self.members_data[row]
        dlg = MemberDialog(self, m)
        if dlg.exec():
            def done(data, err):
                if err:
                    QMessageBox.warning(self, "Error", err)
                else:
                    self.load_members()
            self.call_api("PUT", f"/api/members/{m['id']}", dlg.payload(), cb=done)

    def deactivate_selected(self):
        row = self.mem_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Row", "Select a member first.")
            return
        m = self.members_data[row]
        self.call_api("PATCH", f"/api/members/{m['id']}/deactivate", cb=lambda d, e: self.load_members())

    # --- PAGE 3: RFID SIMULATOR ---
    def build_simulator_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel("RFID Simulator")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        sub = QLabel("Test card scans against POST /api/attendance without the ESP32 connected.")
        sub.setStyleSheet("font-size: 13px; color: #64748b;")
        lay.addWidget(title)
        lay.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(24, 24, 24, 24)
        c_lay.setSpacing(14)

        row = QHBoxLayout()
        self.sim_uid = QLineEdit()
        self.sim_uid.setPlaceholderText("Enter RFID UID (e.g. 04 B9 60 A7)")
        self.sim_uid.returnPressed.connect(self.run_simulation)

        scan_btn = QPushButton("Simulate Tap")
        scan_btn.setObjectName("PrimaryBtn")
        scan_btn.clicked.connect(self.run_simulation)

        row.addWidget(self.sim_uid)
        row.addWidget(scan_btn)
        c_lay.addLayout(row)

        samples = QHBoxLayout()
        samples.addWidget(QLabel("Quick test UIDs:"))
        for uid in ("04 B9 60 A7", "C3 96 AA E4"):
            b = QPushButton(uid)
            b.setObjectName("SecondaryBtn")
            b.clicked.connect(lambda _, u=uid: self.sim_uid.setText(u))
            samples.addWidget(b)
        samples.addStretch()
        c_lay.addLayout(samples)

        self.sim_banner = QFrame()
        self.sim_banner.setStyleSheet("background-color: #f1f5f9; border-radius: 10px; padding: 24px;")
        b_lay = QVBoxLayout(self.sim_banner)
        self.sim_status = QLabel("WAITING FOR SCAN")
        self.sim_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sim_status.setStyleSheet("font-size: 22px; font-weight: 800; color: #475569;")
        self.sim_msg = QLabel("Submit a UID to verify backend authorization.")
        self.sim_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sim_msg.setStyleSheet("font-size: 13px; color: #64748b;")
        b_lay.addWidget(self.sim_status)
        b_lay.addWidget(self.sim_msg)
        c_lay.addWidget(self.sim_banner)

        lay.addWidget(card)
        lay.addStretch()
        return page

    def run_simulation(self):
        uid = self.sim_uid.text().strip()

        def done(data, err):
            if err or not data:
                self.sim_banner.setStyleSheet("background-color: #fee2e2; border-radius: 10px; padding: 24px;")
                self.sim_status.setText("CONNECTION / INPUT ERROR")
                self.sim_status.setStyleSheet("font-size: 20px; font-weight: 800; color: #b91c1c;")
                self.sim_msg.setText(err or "Failed")
                return
            if data.get("status") == "granted":
                self.sim_banner.setStyleSheet("background-color: #dcfce7; border-radius: 10px; padding: 24px;")
                self.sim_status.setText("ACCESS GRANTED")
                self.sim_status.setStyleSheet("font-size: 24px; font-weight: 800; color: #15803d;")
                self.sim_msg.setText(data.get("message", ""))
            else:
                self.sim_banner.setStyleSheet("background-color: #fee2e2; border-radius: 10px; padding: 24px;")
                self.sim_status.setText("ACCESS DENIED")
                self.sim_status.setStyleSheet("font-size: 24px; font-weight: 800; color: #b91c1c;")
                self.sim_msg.setText(data.get("message", ""))

        self.call_api("POST", "/api/attendance", {"uid": uid}, cb=done)

    # --- PAGE 4: HARDWARE & SETTINGS ---
    def build_settings_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel("Hardware & Settings")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("Card")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(20, 20, 20, 20)
        c_lay.setSpacing(12)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit(self.api_url)
        save_btn = QPushButton("Update URL")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self.update_url)
        url_row.addWidget(QLabel("API Base URL:"))
        url_row.addWidget(self.url_input)
        url_row.addWidget(save_btn)
        c_lay.addLayout(url_row)

        self.settings_status = QLabel("Checking...")
        c_lay.addWidget(self.settings_status)

        guide = QLabel(
            "<b>ESP32 + RC522 Plug-and-Play Readiness:</b><br>"
            "• Your ESP32 sketch only needs to POST JSON <code>{\"uid\": \"04 B9 60 A7\"}</code> to <code>http://&lt;LAPTOP-IP&gt;:8000/attendance</code>.<br>"
            "• Set <code>HOST = \"0.0.0.0\"</code> in <code>main.py</code> when connecting the ESP32 over Wi-Fi."
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("background-color: #f8fafc; padding: 12px; border-radius: 8px; color: #334155;")
        c_lay.addWidget(guide)

        lay.addWidget(card)
        lay.addStretch()
        return page

    def update_url(self):
        val = self.url_input.text().strip().rstrip("/")
        if val:
            self.api_url = val
            self.check_health()