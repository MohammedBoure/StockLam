from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QPushButton, 
                               QMessageBox, QCheckBox)
from PySide6.QtGui import QIcon
import qtawesome as qta
import json
import os
from branding import get_login_window_title, get_logo_path

class SessionManager:
    SESSION_FILE = "user_session.json"

    @staticmethod
    def save_session(username, password):
        """حفظ بيانات الدخول محلياً"""
        data = {"username": username, "password": password}
        try:
            with open(SessionManager.SESSION_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Erreur sauvegarde session: {e}")

    @staticmethod
    def load_session():
        """قراءة بيانات الدخول المحفوظة"""
        if not os.path.exists(SessionManager.SESSION_FILE):
            return None
        try:
            with open(SessionManager.SESSION_FILE, 'r') as f:
                return json.load(f)
        except:
            return None

    @staticmethod
    def clear_session():
        if os.path.exists(SessionManager.SESSION_FILE):
            os.remove(SessionManager.SESSION_FILE)
class LoginDialog(QDialog):
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_data = None
        self.setWindowTitle(get_login_window_title())
        self.setFixedSize(380, 250)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 40, 40, 40)

        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        else:
            self.setWindowIcon(qta.icon('fa5s.heartbeat', color='#007572'))

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nom d'utilisateur")
        self.username_input.setFixedHeight(40)
        layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Mot de passe")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)
        layout.addWidget(self.password_input)

        self.remember_me = QCheckBox("Rester connecté")
        self.remember_me.setChecked(True)
        layout.addWidget(self.remember_me)

        self.btn_login = QPushButton("SE CONNECTER")
        self.btn_login.setFixedHeight(45)
        self.btn_login.setStyleSheet("""
            QPushButton { background-color: #007572; color: white; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #005f5c; }
        """)
        self.btn_login.clicked.connect(self.handle_login)
        layout.addWidget(self.btn_login)

        # --- التعديلات المطلوبة ---

        self.username_input.returnPressed.connect(self.password_input.setFocus)
        
        # 2. عند الضغط على Enter في كلمة المرور -> يحاول تسجيل الدخول (سيتم التحقق من الخانات داخل الدالة)
        self.password_input.returnPressed.connect(self.handle_login)
        
        # 3. وضع المؤشر في الخانة الأولى عند البدء
        self.username_input.setFocus()

    def handle_login(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text().strip()
        
        # --- التحقق من الخانات قبل المحاولة ---
        
        # إذا كان اسم المستخدم فارغاً، نضع المؤشر عليه ولا نفعل شيئاً
        if not user:
            self.username_input.setFocus()
            return

        if not pwd:
            self.password_input.setFocus()
            return

        result = self.data_manager.users.authenticate(user, pwd)
        
        if result:
            self.user_data = result
            
            if self.remember_me.isChecked():
                SessionManager.save_session(user, pwd)
            else:
                SessionManager.clear_session()
                
            self.accept()
        else:
            QMessageBox.warning(self, "Échec", "Nom d'utilisateur ou mot de passe incorrect.")
            self.password_input.clear()
            self.password_input.setFocus()
