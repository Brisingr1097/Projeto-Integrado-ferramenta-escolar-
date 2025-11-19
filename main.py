import tkinter as tk
import ctypes
import os
import json
import base64
import secrets
from pathlib import Path
import importlib
# tkinter messagebox
from tkinter import messagebox

# Try to import a TTS engine (pyttsx3) for offline narration; fallback if missing
try:
    import pyttsx3
    _TTS_ENGINE = pyttsx3.init()
    has_tts = True
except Exception:
    _TTS_ENGINE = None
    has_tts = False

# image cache to keep PhotoImage references
_IMAGE_CACHE = {}

# Accessibility / theme state
ACCESSIBILITY = {
    'tts': False,          # narration on/off
    'high_contrast': False,
    'large_text': False,
    'focus_mode': False,
}

DEFAULT_FONT = ("Arial", 11)

def speak(text):
    """Speak text via TTS engine if available, otherwise quietly no-op."""
    if not ACCESSIBILITY.get('tts'):
        return
    try:
        global _TTS_ENGINE, has_tts
        # prefer the already-initialized engine
        if has_tts and _TTS_ENGINE is not None:
            _TTS_ENGINE.say(text)
            _TTS_ENGINE.runAndWait()
            return
        # try to lazily initialize pyttsx3 if it wasn't available at import time
        try:
            import pyttsx3 as _pyttsx3
            _TTS_ENGINE = _pyttsx3.init()
            has_tts = True
            _TTS_ENGINE.say(text)
            _TTS_ENGINE.runAndWait()
            return
        except Exception:
            # fallback: print to console (non-blocking) so screen-readers or assistive tech can pick it up
            try:
                print('NARRATION:', text)
            except Exception:
                pass
    except Exception:
        # swallow tts errors
        pass

def get_font(base_size=11):
    if ACCESSIBILITY.get('large_text'):
        return ("Arial", max(base_size + 4, 14))
    return ("Arial", base_size)


# Theme constants to make visual tuning easier
THEME = {
    'bg': '#f0f0f0',
    'card_bg': '#ffffff',
    'header_bg': '#1f1f1f',
    'primary': "#2fbad3",
    'muted': '#757575',
}


def apply_a11y(widget, text_label: str):
    """Attach simple accessibility handlers to a widget: hover/focus speak the label."""
    if not widget:
        return
    def on_enter(evt=None):
        try:
            speak(text_label)
        except Exception:
            pass
    def on_focus(evt=None):
        try:
            speak(text_label)
        except Exception:
            pass
    try:
        # make widget focusable via keyboard if possible
        try:
            widget.configure(takefocus=True)
        except Exception:
            pass
        widget.bind('<Enter>', on_enter)
        widget.bind('<FocusIn>', on_focus)
        # speak also on click and keyboard activation to make narration more reliable
        widget.bind('<Button-1>', on_enter)
        widget.bind('<Return>', on_enter)
    except Exception:
        pass

# Optional stronger crypto (migrate if available) — use importlib to avoid static lint errors when packages absent
try:
    _mod = importlib.import_module("cryptography.fernet")
    Fernet = _mod.Fernet
    has_fernet = True
except Exception:
    has_fernet = False
try:
    _bcrypt = importlib.import_module("bcrypt")
    bcrypt = _bcrypt
    has_bcrypt = True
except Exception:
    has_bcrypt = False

# === Configuração da biblioteca C ===
LIBRARY_NAME = "notas.dll"  # use "notas.so" ou "notas.dylib" conforme o sistema
lib_path = os.path.join(os.path.dirname(__file__), LIBRARY_NAME)
lib = ctypes.CDLL(lib_path)

# Define tipos da função C
lib.calcular_media.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
lib.calcular_media.restype = ctypes.c_float
try:
    lib.semester_from_iso_date.argtypes = [ctypes.c_char_p]
    lib.semester_from_iso_date.restype = ctypes.c_int
    has_semester_helper = True
except Exception:
    has_semester_helper = False


# === Função que abre o popup ===
def abrir_popup():
    popup = tk.Toplevel()
    popup.title("Cálculo de Média")
    popup.geometry("300x300")

    tk.Label(popup, text="Digite as notas do aluno", font=("Arial", 12, "bold")).pack(pady=10)

    frame = tk.Frame(popup)
    frame.pack(pady=10)

    tk.Label(frame, text="Nota 1:").grid(row=0, column=0, sticky="e")
    n1_entry = tk.Entry(frame, width=10)
    n1_entry.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(frame, text="Nota 2:").grid(row=1, column=0, sticky="e")
    n2_entry = tk.Entry(frame, width=10)
    n2_entry.grid(row=1, column=1, padx=5, pady=5)

    tk.Label(frame, text="PIM:").grid(row=2, column=0, sticky="e")
    n3_entry = tk.Entry(frame, width=10)
    n3_entry.grid(row=2, column=1, padx=5, pady=5)

    resultado_label = tk.Label(popup, text="", font=("Arial", 12), fg="blue")
    resultado_label.pack(pady=10)

    # Função interna para calcular e mostrar o resultado
    def calcular():
        try:
            n1 = float(n1_entry.get())
            n2 = float(n2_entry.get())
            n3 = float(n3_entry.get())

            media = lib.calcular_media(n1, n2, n3)
            resultado_label.config(text=f"Média final: {media:.2f}")
        except ValueError:
            resultado_label.config(text="Erro: digite apenas números!", fg="red")

    tk.Button(popup, text="Calcular", command=calcular, bg="#4CAF50", fg="white").pack(pady=10)


# === Banco de dados (JSON) ===
BASE_DIR = Path(__file__).resolve().parent
BD_DIR = BASE_DIR / "BD"
DB_FILES = {
    "Aluno": BD_DIR / "BD_A.json",
    "Professor": BD_DIR / "BD_P.json",
    "Administrativo": BD_DIR / "BD_AD.json",
    "Atividades": BD_DIR / "BD_ACT.json",
}

ATTACH_DIR = BD_DIR / "attachments"


def ensure_db_files():
    BD_DIR.mkdir(exist_ok=True)
    ATTACH_DIR.mkdir(exist_ok=True)
    for path in DB_FILES.values():
        if not path.exists():
            path.write_text("[]", encoding="utf-8")
    # Ensure default admin exists in administrativo DB
    ad_path = DB_FILES["Administrativo"]
    try:
        with open(ad_path, "r", encoding="utf-8") as f:
            ad_users = json.load(f)
    except Exception:
        ad_users = []
    if not any(u.get("username") == "admin" for u in ad_users):
        # create encrypted admin entry
        admin_entry = {"username": "admin", "password": None, "name": None}
        # ensure key exists
        ensure_key()
        admin_entry["password"] = encrypt_field("admin")
        admin_entry["name"] = encrypt_field("Administrador")
        ad_users.append(admin_entry)
        with open(ad_path, "w", encoding="utf-8") as f:
            json.dump(ad_users, f, indent=2, ensure_ascii=False)


def key_path():
    return BD_DIR / "secret.key"


def ensure_key():
    kpath = key_path()
    if not kpath.exists():
        # generate a 32-byte random key and store base64
        raw = secrets.token_bytes(32)
        kpath.write_bytes(base64.b64encode(raw))


def load_key():
    kpath = key_path()
    if not kpath.exists():
        ensure_key()
    raw = base64.b64decode(kpath.read_bytes())
    return raw


def xor_bytes(data, key):
    # simple XOR with repeating key (not cryptographically strong)
    out = bytearray(len(data))
    for i in range(len(data)):
        out[i] = data[i] ^ key[i % len(key)]
    return bytes(out)


def encrypt_field(plaintext):
    if plaintext is None:
        return None
    key = load_key()
    data = plaintext.encode("utf-8")
    x = xor_bytes(data, key)
    return "ENC:" + base64.b64encode(x).decode("ascii")


def decrypt_field(token):
    if token is None:
        return None
    if not isinstance(token, str):
        return token
    if not token.startswith("ENC:"):
        return token
    try:
        key = load_key()
        b = base64.b64decode(token[4:])
        p = xor_bytes(b, key)
        return p.decode("utf-8")
    except Exception:
        return token


def get_field_str(obj, key):
    """Return decrypted string value for obj[key] or empty string."""
    v = obj.get(key)
    if v is None:
        return ""
    if isinstance(v, str):
        # cache decrypted values on the object to avoid repeated decrypts during UI flows
        cache_key = f"_dec_{key}"
        if obj.get(cache_key) is not None:
            return obj.get(cache_key)
        try:
            dv = migrate_decrypt_field(v) if v.startswith("FERN:") else decrypt_field(v)
            obj[cache_key] = dv or ""
            return dv or ""
        except Exception:
            return v or ""
    return str(v)


# Migration helpers: if Fernet available, support FERN: prefix
def migrate_encrypt_field(plaintext):
    if plaintext is None:
        return None
    if has_fernet:
        try:
            k = load_key()
            f = Fernet(base64.urlsafe_b64encode(k[:32]))
            return "FERN:" + f.encrypt(plaintext.encode("utf-8")).decode("ascii")
        except Exception:
            return encrypt_field(plaintext)
    return encrypt_field(plaintext)


def migrate_decrypt_field(token):
    if token is None:
        return None
    if isinstance(token, str) and token.startswith("FERN:") and has_fernet:
        try:
            k = load_key()
            f = Fernet(base64.urlsafe_b64encode(k[:32]))
            return f.decrypt(token[5:].encode("ascii")).decode("utf-8")
        except Exception:
            return token
    return decrypt_field(token)


def load_db(role):
    path = DB_FILES[role]
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def load_activities():
    return load_db("Atividades")


def save_activities(data):
    save_db("Atividades", data)


import datetime


def parse_date(s):
    # expect YYYY-MM-DD or try to parse
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        try:
            return datetime.date.fromisoformat(s)
        except Exception:
            return None


def matches_target(activity, user):
    # activity target keys: curso, turma, semestre, periodo (values or None)
    target = activity.get("target") or {}
    if not target:
        return True
    for k in ("curso", "turma", "semestre", "periodo"):
        tv = target.get(k)
        if tv:
            uval = user.get(k) or user.get(k.lower()) or user.get(k.capitalize())
            # user's fields may be decrypted under same keys or different; check common ones
            if uval is None:
                return False
            if str(uval) != str(tv):
                return False
    return True


def format_date(d):
    if not d:
        return ""
    if isinstance(d, str):
        return d
    return d.isoformat()


def save_db(role, data):
    path = DB_FILES[role]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# === Interface de Login / Registro ===
ensure_db_files()


def start_app():
    janela = tk.Tk()
    janela.title("Plataforma de Estudos")
    janela.geometry("380x640")
    janela.configure(bg="#f0f0f0")

    # Dark header to mimic mobile mockup
    header = tk.Frame(janela, bg=THEME['header_bg'], height=60)
    header.pack(fill="x")
    tk.Label(header, text="Plataforma de estudos 8BIT-Devs", fg="white", bg=THEME['header_bg'], font=get_font(12)).pack(side="left", padx=12, pady=12)
    # accessibility quick toggles on header (TTS, contrast, large text)
    acc_frame = tk.Frame(header, bg=THEME['header_bg'])
    acc_frame.pack(side="right", padx=8)
    tts_btn = tk.Button(acc_frame, text="🔊", bg="#333333", fg="white", bd=0)
    tts_btn.pack(side="left", padx=6)
    contrast_btn = tk.Button(acc_frame, text="⚫", bg="#333333", fg="white", bd=0)
    contrast_btn.pack(side="left", padx=6)
    large_btn = tk.Button(acc_frame, text="A+", bg="#333333", fg="white", bd=0)
    large_btn.pack(side="left", padx=6)

    def toggle_tts():
        ACCESSIBILITY['tts'] = not ACCESSIBILITY.get('tts')
        # announce the change and the currently focused widget (if any)
        if ACCESSIBILITY['tts']:
            speak('Narração ativada')
            try:
                fw = janela.focus_get()
                if fw:
                    try:
                        lbl = fw.cget('text')
                    except Exception:
                        lbl = None
                    if lbl:
                        speak(f'Foco: {lbl}')
            except Exception:
                pass
        else:
            speak('Narração desativada')

    def toggle_contrast():
        ACCESSIBILITY['high_contrast'] = not ACCESSIBILITY.get('high_contrast')
        # immediate feedback: change header bg and relayout
        header.config(bg="#000000" if ACCESSIBILITY['high_contrast'] else "#1f1f1f")
        speak('Contraste alto ativado' if ACCESSIBILITY['high_contrast'] else 'Contraste alto desativado')

    def toggle_large():
        ACCESSIBILITY['large_text'] = not ACCESSIBILITY.get('large_text')
        # re-render current dashboard view if logged
        try:
            if getattr(start_app, 'current_user', None):
                show_dashboard(start_app.current_user.get('_role'), start_app.current_user)
        except Exception:
            pass
        speak('Texto maior ativado' if ACCESSIBILITY['large_text'] else 'Texto maior desativado')

    tts_btn.config(command=toggle_tts)
    contrast_btn.config(command=toggle_contrast)
    large_btn.config(command=toggle_large)
    # a11y bindings for header buttons
    apply_a11y(tts_btn, 'Ativar narração')
    apply_a11y(contrast_btn, 'Modo alto contraste')
    apply_a11y(large_btn, 'Aumentar texto')

    # Frames
    entry_frame = tk.Frame(janela, bg="#f0f0f0")
    login_frame = tk.Frame(janela, bg="#f0f0f0")
    dashboard_frame = tk.Frame(janela, bg="#f0f0f0")
    # bottom bar placeholder (will be populated after login)
    bottom = tk.Frame(janela, bg="#1f1f1f")

    # --- Login/Register UI ---
    # Centered card for login
    card = tk.Frame(login_frame, bg="white", bd=0, relief="ridge")
    card.place(relx=0.5, rely=0.45, anchor="center", width=320, height=300)
    tk.Label(card, text="", bg="white").pack()
    tk.Label(card, text="Plataforma de estudos 8BIT-Devs", font=("Arial", 14, "bold"), bg="white", fg="#2f71d3").pack(pady=(8,2))
    tk.Label(card, text="Login", font=("Arial", 12, "bold"), bg="white").pack(pady=4)

    role_var = tk.StringVar(value="Aluno")
    roles = ["Aluno", "Professor", "Administrativo"]
    role_frame = tk.Frame(card, bg="white")
    role_frame.pack(pady=4)
    for r in roles:
        tk.Radiobutton(role_frame, text=r, variable=role_var, value=r, bg="white").pack(side="left", padx=6)

    form = tk.Frame(card, bg="white")
    form.pack(pady=6)

    tk.Label(form, text="Usuário:", bg="white").grid(row=0, column=0, sticky="e")
    user_entry = tk.Entry(form, width=25)
    user_entry.grid(row=0, column=1, pady=4)

    tk.Label(form, text="Senha:", bg="white").grid(row=1, column=0, sticky="e")
    pass_entry = tk.Entry(form, width=25, show="*")
    pass_entry.grid(row=1, column=1, pady=4)

    msg_label = tk.Label(card, text="", fg="red", bg="white")
    msg_label.pack(pady=4)


    def register_user_admin(role_to_create):
        # pop-up para administrador criar usuário com dados adicionais
        popup = tk.Toplevel()
        popup.title(f"Registrar {role_to_create}")
        popup.geometry("420x340")
        frm = tk.Frame(popup)
        frm.pack(pady=8)
        tk.Label(frm, text="Usuário:").grid(row=0, column=0, sticky="e")
        u = tk.Entry(frm, width=30)
        u.grid(row=0, column=1)
        tk.Label(frm, text="Senha:").grid(row=1, column=0, sticky="e")
        p = tk.Entry(frm, width=30)
        p.grid(row=1, column=1)
        tk.Label(frm, text="Nome completo:").grid(row=2, column=0, sticky="e")
        n = tk.Entry(frm, width=30)
        n.grid(row=2, column=1)
        tk.Label(frm, text="Idade:").grid(row=3, column=0, sticky="e")
        idade = tk.Entry(frm, width=10)
        idade.grid(row=3, column=1, sticky="w")
        tk.Label(frm, text="Email:").grid(row=4, column=0, sticky="e")
        email = tk.Entry(frm, width=30)
        email.grid(row=4, column=1)
        tk.Label(frm, text="CPF:").grid(row=5, column=0, sticky="e")
        cpf = tk.Entry(frm, width=20)
        cpf.grid(row=5, column=1, sticky="w")
        tk.Label(frm, text="Curso:").grid(row=6, column=0, sticky="e")
        curso = tk.Entry(frm, width=25)
        curso.grid(row=6, column=1, sticky="w")
        tk.Label(frm, text="Turma:").grid(row=7, column=0, sticky="e")
        turma = tk.Entry(frm, width=15)
        turma.grid(row=7, column=1, sticky="w")
        tk.Label(frm, text="Semestre:").grid(row=8, column=0, sticky="e")
        semestre = tk.Entry(frm, width=8)
        semestre.grid(row=8, column=1, sticky="w")
        tk.Label(frm, text="Período:").grid(row=9, column=0, sticky="e")
        periodo_var = tk.StringVar(value="Manhã")
        periodo_frame = tk.Frame(frm)
        periodo_frame.grid(row=9, column=1, sticky="w")
        for val in ["Manhã", "Tarde", "Noite"]:
            tk.Radiobutton(periodo_frame, text=val, variable=periodo_var, value=val).pack(side="left")

        def do_create():
            username = u.get().strip()
            password = p.get().strip()
            name = n.get().strip()
            age = idade.get().strip()
            mail = email.get().strip()
            cpfv = cpf.get().strip()
            cur = curso.get().strip()
            tur = turma.get().strip()
            sem = semestre.get().strip()
            per = periodo_var.get()
            if not username or not password or not name:
                return
            users = load_db(role_to_create)
            if any(x.get("username") == username for x in users):
                return
            user_obj = {
                "username": username,
                "password": encrypt_field(password),
                "name": encrypt_field(name),
                "age": encrypt_field(age),
                "email": encrypt_field(mail),
                "cpf": encrypt_field(cpfv),
                "curso": encrypt_field(cur),
                "turma": encrypt_field(tur),
                "semestre": encrypt_field(sem),
                "periodo": encrypt_field(per),
                "grades": {}
            }
            users.append(user_obj)
            save_db(role_to_create, users)
            popup.destroy()

        tk.Button(popup, text="Criar", command=do_create, bg="#4CAF50", fg="white", width=12).pack(pady=8)


    def login_user():
        role = role_var.get()
        username = user_entry.get().strip()
        password = pass_entry.get().strip()

        if not username or not password:
            msg_label.config(text="Preencha usuário e senha para entrar.")
            return

        users = load_db(role)
        # decrypt passwords if stored encrypted
        match = None
        for u in users:
            stored = u.get("password")
            stored_plain = decrypt_field(stored) if isinstance(stored, str) else stored
            if u.get("username") == username and stored_plain == password:
                # prepare a copy with decrypted fields for UI use
                u_copy = dict(u)
                # decrypt common fields
                if u_copy.get("name") is not None:
                    u_copy["name"] = decrypt_field(u_copy.get("name"))
                if u_copy.get("email") is not None:
                    u_copy["email"] = decrypt_field(u_copy.get("email"))
                if u_copy.get("cpf") is not None:
                    u_copy["cpf"] = decrypt_field(u_copy.get("cpf"))
                if u_copy.get("curso") is not None:
                    u_copy["curso"] = decrypt_field(u_copy.get("curso"))
                if u_copy.get("turma") is not None:
                    u_copy["turma"] = decrypt_field(u_copy.get("turma"))
                if u_copy.get("semestre") is not None:
                    u_copy["semestre"] = decrypt_field(u_copy.get("semestre"))
                if u_copy.get("periodo") is not None:
                    u_copy["periodo"] = decrypt_field(u_copy.get("periodo"))
                if u_copy.get("age") is not None:
                    u_copy["age"] = decrypt_field(u_copy.get("age"))
                # grades remain as-is (encrypted or plaintext depending on implementation)
                u_copy["_role"] = role
                match = u_copy
                break
        if match:
            msg_label.config(text="", fg="green")
            show_dashboard(role, match)
            # wire bottom navigation to this user (if function present)
            try:
                start_app.update_bottom_nav(match)
            except Exception:
                pass
        else:
            msg_label.config(text="Credenciais inválidas.")


    btn_frame = tk.Frame(card, bg="white")
    btn_frame.pack(pady=6)
    # Red CTA for primary action to match mockup
    b_login = tk.Button(btn_frame, text="Entrar", command=login_user, bg=THEME['primary'], fg="white", width=14)
    b_login.pack(side="left", padx=(6,4))
    apply_a11y(b_login, 'Entrar no sistema')
    b_back = tk.Button(btn_frame, text="Voltar", command=lambda: (login_frame.pack_forget(), entry_frame.pack(fill="both", expand=True)), bg="#9e9e9e", fg="white", width=10)
    b_back.pack(side="left", padx=(4,6))
    apply_a11y(b_back, 'Voltar')


    # --- Dashboard ---
    def show_dashboard(role, user):
        login_frame.pack_forget()
        for widget in dashboard_frame.winfo_children():
            widget.destroy()
        # record current view for help guidance
        start_app.current_view = 'dashboard'
        start_app.current_view_context = {}
        # dashboard header inside dark strip
        hdr = tk.Frame(dashboard_frame, bg="#1f1f1f")
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Bem-vindo, {user.get('name')}", fg="white", bg="#1f1f1f", font=get_font(12)).pack(side="left", padx=12, pady=10)
        tk.Label(hdr, text=role, fg="#bdbdbd", bg="#1f1f1f", font=get_font(10)).pack(side="right", padx=12)
        # student sees home widgets
        if role == "Aluno":
            student_home(user)
        else:
            # header button
            tk.Button(dashboard_frame, text="Abrir cálculo de média", command=abrir_popup, bg="#2196F3", fg="white", width=22).pack(pady=6)
            if role in ("Professor", "Administrativo"):
                act_frame = tk.Frame(dashboard_frame, bg="#f0f0f0")
                act_frame.pack(pady=6, fill="x", padx=12)
                tk.Button(act_frame, text="Criar Atividade", command=lambda: create_activity_popup(user), bg="#2f89d3", fg="white", width=18, height=1).pack(side="left", padx=6)
                # Professor tools
                tk.Button(act_frame, text="Ferramentas do Prof.", command=lambda: professor_tools(user), width=18, height=1).pack(side="left", padx=6)
            if role == "Administrativo":
                # admin actions: create aluno/professor
                admin_actions = tk.Frame(dashboard_frame)
                admin_actions.pack(pady=6)
                tk.Button(admin_actions, text="Criar Aluno", command=lambda: register_user_admin("Aluno"), width=15).pack(side="left", padx=6)
                tk.Button(admin_actions, text="Criar Professor", command=lambda: register_user_admin("Professor"), width=15).pack(side="left", padx=6)
        # dashboard main area
        dashboard_frame.pack(fill="both", expand=True)
        # populate bottom bar (navigation + logout) and show it
        for c in bottom.winfo_children():
            c.destroy()
        nav_frame = tk.Frame(bottom, bg="#1f1f1f")
        nav_frame.pack(side="left", padx=8, pady=6)
        nav_btn_acts = tk.Button(nav_frame, text="3E0\nAtiv.", bg="#1f1f1f", fg="white", bd=0)
        nav_btn_acts.pack(side="left", padx=10)
        nav_btn_grades = tk.Button(nav_frame, text="4C8\nNotas", bg="#1f1f1f", fg="white", bd=0)
        nav_btn_grades.pack(side="left", padx=10)
        nav_btn_profile = tk.Button(nav_frame, text="464\nPerfil", bg="#1f1f1f", fg="white", bd=0)
        nav_btn_profile.pack(side="left", padx=10)
        nav_btn_help = tk.Button(nav_frame, text="?\nDúvidas", bg="#1f1f1f", fg="white", bd=0)
        nav_btn_help.pack(side="left", padx=10)
        # logout placed at right
        logout_frame = tk.Frame(bottom, bg="#1f1f1f")
        logout_frame.pack(side="right", padx=8)
        logout_btn = tk.Button(logout_frame, text="Logout", command=lambda: do_logout(), bg="#9e9e9e", fg="white")
        logout_btn.pack()
        apply_a11y(nav_btn_acts, 'Atividades')
        apply_a11y(nav_btn_grades, 'Notas')
        apply_a11y(nav_btn_profile, 'Perfil')
        apply_a11y(nav_btn_help, 'Dúvidas')
        apply_a11y(logout_btn, 'Sair do sistema')

        # helper to wire bottom nav to the current user after login
        def update_bottom_nav(u):
            if not u:
                return
            nav_btn_acts.config(command=lambda: show_activities_list(u))
            nav_btn_grades.config(command=lambda: show_student_view(u) if u.get('_role')=='Aluno' else professor_tools(u))
            nav_btn_profile.config(command=lambda: show_profile(u))
            nav_btn_help.config(command=lambda: toggle_help_panel(u))
            # show bottom bar
            bottom.pack(side="bottom", fill="x")

        # make update_bottom_nav available in outer scope
        start_app.update_bottom_nav = update_bottom_nav


    # Student read-only view: subjects and two semesters
    def show_student_view(user):
        # For simplicity, store student grades inside student's JSON object under 'grades'
        # Subjects example
        subjects = ["Matemática", "Português", "Programação"]
        grades = user.get("grades") or {}
        for subj in subjects:
            g = grades.get(subj, {"sem1": None, "sem2": None})
            frame = tk.Frame(dashboard_frame)
            frame.pack(pady=4, fill="x", padx=20)
            tk.Label(frame, text=subj, width=15, anchor="w").pack(side="left")
            s1 = tk.StringVar(value="" if g.get("sem1") is None else str(g.get("sem1")))
            s2 = tk.StringVar(value="" if g.get("sem2") is None else str(g.get("sem2")))
            tk.Label(frame, textvariable=s1, width=8, bg="#f7f7f7").pack(side="left", padx=6)
            tk.Label(frame, textvariable=s2, width=8, bg="#f7f7f7").pack(side="left", padx=6)
        tk.Label(dashboard_frame, text="(Sem1)   (Sem2)").pack(pady=6)


    def show_profile(user):
        # simple profile view (read-only)
        for w in dashboard_frame.winfo_children():
            w.destroy()
        tk.Label(dashboard_frame, text="Perfil", font=get_font(14)).pack(pady=8)
        infof = tk.Frame(dashboard_frame)
        infof.pack(pady=6, padx=12, fill="x")
        fields = [
            ("Nome", get_field_str(user, 'name')),
            ("Usuário", user.get('username')),
            ("Email", get_field_str(user, 'email')),
            ("CPF", get_field_str(user, 'cpf')),
            ("Curso", get_field_str(user, 'curso')),
            ("Turma", get_field_str(user, 'turma')),
            ("Semestre", get_field_str(user, 'semestre')),
            ("Período", get_field_str(user, 'periodo')),
        ]
        for label, val in fields:
            row = tk.Frame(infof)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"{label}:", width=12, anchor="w", font=get_font(11)).pack(side="left")
            tk.Label(row, text=str(val) if val is not None else "", font=get_font(11)).pack(side="left")
        tk.Button(dashboard_frame, text="Voltar", command=lambda: show_dashboard(user.get('_role'), user)).pack(pady=8)
        if ACCESSIBILITY.get('tts'):
            speak(f"Perfil de {get_field_str(user,'name')}")


    def provide_guidance(user):
        # Produce a short contextual guide depending on the current view
        view = getattr(start_app, 'current_view', None)
        ctx = getattr(start_app, 'current_view_context', {}) or {}
        if view == 'student_home':
            text = "Você está na tela inicial do aluno. Use 'Ver Atividades' para ver tarefas, 'Calendário' para ver datas, e 'Ver Notas' para acompanhar seu desempenho.\nSe precisar entregar uma atividade, abra a atividade e clique em Enviar." 
        elif view == 'activities_list':
            text = "Esta é a lista de atividades. Clique em qualquer atividade para ver detalhes e enviar seu trabalho. Botões vermelhos indicam ações principais." 
        elif view == 'activity_detail':
            text = "Aqui você vê a descrição da atividade. Para enviar, escreva sua resposta e clique em Enviar. Professores podem abrir e atribuir notas." 
        elif view == 'professor_tools':
            text = "Ferramentas do professor: marque faltas e veja desempenho da turma. Use 'Marcar Faltas' para registrar ausências e 'Ver Desempenho' para gráficos." 
        elif view == 'profile':
            text = "Esta é sua página de perfil. Aqui você encontra seus dados pessoais, curso e turma. Use essa informação para confirmar seu cadastro." 
        elif view == 'dashboard':
            text = "Bem-vindo ao painel. Use os botões principais para criar atividades (se for professor), ver ferramentas, ou abrir o cálculo de média." 
        else:
            text = "Esta é a aplicação. Use a navegação inferior para alternar entre Atividades, Notas e Perfil. Abra 'Dúvidas' para ver orientações rápidas." 
        # show guidance popup and optionally speak
        try:
            p = tk.Toplevel()
            p.title('Ajuda rápida')
            p.geometry('420x240')
            tk.Label(p, text='Orientação rápida', font=get_font(14)).pack(pady=8)
            txt = tk.Text(p, wrap='word', height=8, width=50)
            txt.pack(padx=8)
            txt.insert('1.0', text)
            txt.config(state='disabled')
            tk.Button(p, text='Fechar', command=p.destroy).pack(pady=8)
        except Exception:
            messagebox.showinfo('Ajuda', text)
        speak(text)


    def show_help_popup(user):
        popup = tk.Toplevel()
        popup.title('Dúvidas e Ajuda')
        popup.geometry('520x380')
        tk.Label(popup, text='Dúvidas frequentes', font=get_font(14)).pack(pady=8)
        faqf = tk.Frame(popup)
        faqf.pack(fill='both', expand=True, padx=12)
        faqs = [
            ("Como eu envio uma atividade?", "Abra a atividade e clique em Enviar, escreva sua resposta e confirme."),
            ("Como vejo minhas notas?", "Vá em Notas no rodapé ou Ver Notas na tela principal."),
            ("Como eu recupero minha senha?", "Peça ao administrativo para resetar sua senha."),
        ]
        for q,a in faqs:
            tk.Label(faqf, text=q, font=get_font(11)).pack(anchor='w', pady=4)
            tk.Label(faqf, text=a, fg='#555555', wraplength=460).pack(anchor='w', pady=2)
        btns = tk.Frame(popup)
        btns.pack(pady=10)
        tk.Button(btns, text='Estou perdido', command=lambda: provide_guidance(user), bg=THEME['primary'], fg='white').pack(side='left', padx=8)
        tk.Button(btns, text='Fechar', command=popup.destroy).pack(side='left', padx=8)
        apply_a11y(btns.winfo_children()[0], 'Estou perdido — orientação passo a passo')


    def toggle_help_panel(user):
        """Show or hide a docked help panel on the right side of the dashboard."""
        # if panel exists, remove it
        existing = getattr(start_app, 'help_panel', None)
        if existing and hasattr(existing, 'winfo_exists') and existing.winfo_exists():
            try:
                existing.destroy()
            except Exception:
                pass
            start_app.help_panel = None
            return
        # create a new right-side panel
        panel = tk.Frame(dashboard_frame, bg="#ffffff", bd=1, relief="solid", width=260)
        panel.pack(side='right', fill='y', padx=6, pady=6)
        tk.Label(panel, text='Ajuda rápida', font=get_font(12)).pack(pady=8)
        faqs = [
            ("Como eu envio uma atividade?", "Abra a atividade e clique em Enviar, escreva sua resposta e confirme."),
            ("Como vejo minhas notas?", "Vá em Notas no rodapé ou Ver Notas na tela principal."),
            ("Como eu recupero minha senha?", "Peça ao administrativo para resetar sua senha."),
        ]
        for q,a in faqs:
            tk.Label(panel, text=q, font=get_font(11), anchor='w').pack(fill='x', padx=8, pady=(6,0))
            tk.Label(panel, text=a, fg='#555555', wraplength=220, anchor='w').pack(fill='x', padx=8, pady=(0,4))
        btn = tk.Button(panel, text='Estou perdido', command=lambda: provide_guidance(user), bg=THEME['primary'], fg='white')
        btn.pack(pady=10, padx=8)
        apply_a11y(btn, 'Estou perdido — orientação passo a passo')
        start_app.help_panel = panel
        if ACCESSIBILITY.get('tts'):
            speak('Painel de ajuda aberto')


    # ---------- Activities and student home ----------
    def student_home(user):
        # top widgets: pending activities count, recent comments, next deadlines
        acts = load_activities()
        today = datetime.date.today()

        pending = [a for a in acts if not any(s.get("student") == user.get("username") for s in a.get("submissions", []))]
        dated = [a for a in acts if parse_date(a.get("deadline")) is not None]
        upcoming = sorted(dated, key=lambda x: parse_date(x.get("deadline")) or datetime.date.max)[:5]
        comments = []
        for a in acts:
            for c in a.get("comments", []):
                comments.append({"activity": a.get("title"), "text": c.get("text")})
        # mark current view for contextual help
        start_app.current_view = 'student_home'
        start_app.current_view_context = {}

        top = tk.Frame(dashboard_frame)
        top.pack(pady=6, fill="x", padx=12)
        tk.Label(top, text=f"Atividades pendentes: {len(pending)}", bg="#ffefc6", font=get_font(11)).pack(fill="x", padx=6, pady=4)
        tk.Label(top, text=f"Comentários recentes: {len(comments)}", bg="#e8f4ff", font=get_font(11)).pack(fill="x", padx=6, pady=4)
        if upcoming:
            nxt = upcoming[0]
            tk.Label(top, text=f"Próxima entrega: {nxt.get('title')} em {nxt.get('deadline')}", bg="#ffdede", font=get_font(11)).pack(fill="x", padx=6, pady=4)

        btns = tk.Frame(dashboard_frame)
        btns.pack(pady=8)
        b1 = tk.Button(btns, text="Ver Atividades", command=lambda: show_activities_list(user), bg=THEME['primary'], fg="white", width=16, height=1)
        b1.pack(side="left", padx=6)
        apply_a11y(b1, 'Ver atividades')
        b2 = tk.Button(btns, text="Calendário", command=lambda: show_calendar(user), width=16, height=1)
        b2.pack(side="left", padx=6)
        apply_a11y(b2, 'Calendário escolar')
        # also show grades
        b3 = tk.Button(btns, text="Ver Notas", command=lambda: show_student_view(user), width=16, height=1)
        b3.pack(side="left", padx=6)
        apply_a11y(b3, 'Ver notas')
        # offer quick narration for students
        if ACCESSIBILITY.get('tts'):
            speak(f"Você tem {len(pending)} atividades pendentes. Próxima entrega: {upcoming[0].get('title') if upcoming else 'nenhuma'}")


    def show_activities_list(user):
        start_app.current_view = 'activities_list'
        start_app.current_view_context = {}
        for w in dashboard_frame.winfo_children():
            w.destroy()
        tk.Label(dashboard_frame, text="Atividades", font=get_font(14), bg="#f0f0f0").pack(pady=8)
        acts = load_activities()
        listf = tk.Frame(dashboard_frame, bg="#f0f0f0")
        listf.pack(fill="both", expand=True, padx=8, pady=6)
        for a in acts:
            # card-like activity item
            frame = tk.Frame(listf, bg="white", bd=0, relief="flat")
            frame.pack(fill="x", padx=4, pady=8)
            inner = tk.Frame(frame, bg="white", bd=1, relief="groove")
            inner.pack(fill="x", padx=6, pady=6)
            tk.Label(inner, text=a.get("title"), font=get_font(12), bg="white").pack(anchor="w", padx=8)
            tk.Label(inner, text=f"Entrega: {a.get('deadline')}", bg="white", fg="#757575", font=get_font(10)).pack(anchor="w", padx=8)
            btn = tk.Button(inner, text="Enviar Trabalho" if user.get('_role')=='Aluno' else "Ver", command=lambda act=a: show_activity_detail(user, act), bg="#2f97d3", fg="white")
            btn.pack(anchor="e", padx=8, pady=6)
        if ACCESSIBILITY.get('tts'):
            speak(f"Mostrando {len(acts)} atividades")
        tk.Button(dashboard_frame, text="Voltar", command=lambda: show_dashboard("Aluno", user)).pack(pady=6)


    def professor_tools(user):
        # Simple tools: mark attendance and show performance
        start_app.current_view = 'professor_tools'
        start_app.current_view_context = {}
        for w in dashboard_frame.winfo_children():
            w.destroy()
        tk.Label(dashboard_frame, text="Ferramentas do Professor", font=("Arial", 14, "bold")).pack(pady=8)
        tk.Button(dashboard_frame, text="Marcar Faltas", command=lambda: mark_attendance_popup(user), width=20).pack(pady=6)
        tk.Button(dashboard_frame, text="Atribuir Notas", command=lambda: assign_grades_popup(user), width=20).pack(pady=6)
        tk.Button(dashboard_frame, text="Ver Desempenho (Atividades)", command=lambda: show_performance_chart(user), width=30).pack(pady=6)
        tk.Button(dashboard_frame, text="Voltar", command=lambda: show_dashboard("Professor", user)).pack(pady=8)


    def mark_attendance_popup(user):
        # choose turma from professor (assume professor.curso/turma fields exist)
        popup = tk.Toplevel()
        popup.title("Marcar Faltas")
        popup.geometry("420x420")
        tk.Label(popup, text="Data (YYYY-MM-DD):").pack(pady=4)
        date_e = tk.Entry(popup)
        date_e.pack()
        tk.Label(popup, text="Turma: (deixe em branco para usar sua turma)").pack(pady=4)
        turma_e = tk.Entry(popup)
        turma_e.pack()
        # list students in the turma
        listf = tk.Frame(popup)
        listf.pack(fill="both", expand=True, pady=6)
        students = load_db("Aluno")
        check_items = []
        def refresh_students():
            for c in listf.winfo_children():
                c.destroy()
            tval = turma_e.get().strip() or get_field_str(user, 'turma')
            filtered = [s for s in students if get_field_str(s, 'turma') == tval]
            check_items.clear()
            for s in filtered:
                var = tk.IntVar(value=0)
                label = f"{get_field_str(s, 'name')} ({s.get('username')})"
                chk = tk.Checkbutton(listf, text=label, variable=var)
                chk.pack(anchor="w")
                check_items.append({'var': var, 'username': s.get('username')})
        refresh_students()
        def do_mark():
            d = date_e.get().strip()
            if not d:
                return
            # ensure date string is valid-ish
            if parse_date(d) is None:
                return
            # collect checked
            checked = [item for item in check_items if item['var'].get() == 1]
            if not checked:
                return
            studs = load_db("Aluno")
            changed = False
            for item in checked:
                uname = item['username']
                for st in studs:
                    if st.get('username') == uname:
                        att = st.setdefault('attendance', [])
                        att.append({'date': d, 'status': 'absent', 'marked_by': user.get('username')})
                        changed = True
            if changed:
                save_db('Aluno', studs)
            popup.destroy()
        tk.Button(popup, text="Salvar Faltas", command=do_mark, bg="#4CAF50", fg="white").pack(pady=8)


    def show_performance_chart(user):
        # compute percent submissions per student in this turma (or per curso)
        acts = load_activities()
        students = load_db('Aluno')
        # determine professor's turma (decrypted)
        tval = get_field_str(user, 'turma') or user.get('turma')
        # build list of relevant students (compare decrypted turma)
        relevant = [s for s in students if get_field_str(s, 'turma') == tval]
        if not relevant:
            messagebox.showinfo('Desempenho', 'Nenhum aluno encontrado para sua turma.')
            return

        names = [get_field_str(s, 'name') or s.get('username') for s in relevant]
        # relevant activities are those targeted at this turma
        rel_acts = [a for a in acts if (a.get('target') or {}).get('turma') == tval]
        total = len(rel_acts)
        perc = []
        for s in relevant:
            submitted = 0
            for a in rel_acts:
                if any(sb.get('student') == s.get('username') for sb in a.get('submissions', [])):
                    submitted += 1
            perc.append((submitted / total * 100) if total > 0 else 0)

        # try to show a matplotlib chart if available
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(6, 4))
            x = list(range(len(names)))
            ax.bar(x, perc, color='#2196F3')
            ax.set_ylabel('Percentual de atividades entregues')
            ax.set_ylim(0, 100)
            ax.set_xticks(x)
            ax.set_xticklabels(names, rotation=45, ha='right')
            plt.tight_layout()
            # show in a popup by saving to temp file
            import tempfile
            fp = tempfile.mktemp(suffix='.png')
            fig.savefig(fp)
            plt.close(fig)
            # show image in a simple popup
            p = tk.Toplevel()
            p.title('Desempenho da Turma')
            img = tk.PhotoImage(file=fp)
            _IMAGE_CACHE[fp] = img
            lbl = tk.Label(p, image=_IMAGE_CACHE[fp])
            lbl.pack()
        except Exception:
            # fallback textual summary
            out = '\n'.join([f"{get_field_str(s,'name') or s.get('username')}: {v:.1f}%" for s, v in zip(relevant, perc)])
            messagebox.showinfo('Desempenho (texto)', out)
        start_app.current_view = 'performance_chart'
        start_app.current_view_context = {}


    def assign_grades_popup(user):
        """Allow a professor to assign grades to each student in their turma for a given subject and semester."""
        popup = tk.Toplevel()
        popup.title('Atribuir Notas')
        popup.geometry('600x520')

        top = tk.Frame(popup)
        top.pack(pady=8, fill='x', padx=8)
        tk.Label(top, text='Disciplina (assunto):').grid(row=0, column=0, sticky='e')
        subj_e = tk.Entry(top, width=30)
        subj_e.grid(row=0, column=1, padx=6, pady=4)
        tk.Label(top, text='Semestre:').grid(row=1, column=0, sticky='e')
        sem_var = tk.StringVar(value='1')
        tk.Radiobutton(top, text='1', variable=sem_var, value='1').grid(row=1, column=1, sticky='w')
        tk.Radiobutton(top, text='2', variable=sem_var, value='2').grid(row=1, column=1, sticky='e')
        load_btn = tk.Button(top, text='Carregar alunos', bg=THEME['primary'], fg='white')
        load_btn.grid(row=0, column=2, rowspan=2, padx=8)

        students_frame = tk.Frame(popup)
        students_frame.pack(fill='both', expand=True, padx=8, pady=6)

        entries = {}

        def load_students():
            for w in students_frame.winfo_children():
                w.destroy()
            subj = subj_e.get().strip()
            sem = sem_var.get()
            if not subj:
                messagebox.showinfo('Atribuir Notas', 'Digite o nome da disciplina antes de carregar alunos.')
                return
            students = load_db('Aluno')
            tval = get_field_str(user, 'turma') or user.get('turma')
            filtered = [s for s in students if get_field_str(s, 'turma') == tval]
            if not filtered:
                messagebox.showinfo('Atribuir Notas', 'Nenhum aluno encontrado para sua turma.')
                return
            # header
            hdr = tk.Frame(students_frame)
            hdr.pack(fill='x')
            tk.Label(hdr, text='Aluno', width=40, anchor='w').pack(side='left')
            tk.Label(hdr, text='Nota', width=10).pack(side='left')
            for s in filtered:
                row = tk.Frame(students_frame)
                row.pack(fill='x', pady=2)
                name = get_field_str(s, 'name') or s.get('username')
                tk.Label(row, text=f"{name} ({s.get('username')})", width=40, anchor='w').pack(side='left')
                ent = tk.Entry(row, width=10)
                ent.pack(side='left')
                # prefill existing grade if present
                existing = s.get('grades', {}).get(subj, {})
                gkey = 'sem1' if sem == '1' else 'sem2'
                if existing and existing.get(gkey) is not None:
                    ent.insert(0, str(existing.get(gkey)))
                entries[s.get('username')] = ent

        def save_grades():
            subj = subj_e.get().strip()
            sem = sem_var.get()
            if not subj:
                messagebox.showinfo('Atribuir Notas', 'Digite a disciplina antes de salvar.')
                return
            studs = load_db('Aluno')
            changed = False
            for st in studs:
                uname = st.get('username')
                if uname in entries:
                    val = entries[uname].get().strip()
                    if val == '':
                        continue
                    try:
                        v = float(val)
                    except Exception:
                        v = val
                    grades = st.setdefault('grades', {})
                    subj_gr = grades.setdefault(subj, {})
                    key = 'sem1' if sem == '1' else 'sem2'
                    subj_gr[key] = v
                    changed = True
            if changed:
                save_db('Aluno', studs)
                speak('Notas salvas com sucesso')
                messagebox.showinfo('Atribuir Notas', 'Notas salvas com sucesso.')
            else:
                messagebox.showinfo('Atribuir Notas', 'Nenhuma alteração realizada.')

        load_btn.config(command=load_students)
        save_btn = tk.Button(popup, text='Salvar Notas', command=save_grades, bg='#4CAF50', fg='white')
        save_btn.pack(pady=8)
        apply_a11y(load_btn, 'Carregar alunos da turma')
        apply_a11y(save_btn, 'Salvar notas')


    def show_activity_detail(user, activity):
        for w in dashboard_frame.winfo_children():
            w.destroy()
        tk.Label(dashboard_frame, text=activity.get("title"), font=("Arial", 14, "bold")).pack(pady=8)
        tk.Label(dashboard_frame, text=f"Descrição: {activity.get('description')}").pack(pady=4)
        tk.Label(dashboard_frame, text=f"Prazo: {activity.get('deadline')}").pack(pady=4)
        # show comments
        tk.Label(dashboard_frame, text="Comentários:", font=("Arial", 11, "bold")).pack(pady=6)
        for c in activity.get("comments", []):
            tk.Label(dashboard_frame, text=f"- {c.get('author')}: {c.get('text')}").pack(anchor="w", padx=20)
        # submission (student) or submissions overview (professor/admin)
        subm_frame = tk.Frame(dashboard_frame)
        subm_frame.pack(pady=8)
        tk.Label(subm_frame, text="Sua resposta:").pack(anchor="w")
        resp = tk.Text(subm_frame, height=6, width=60)
        resp.pack()
        def submit_resp():
            text = resp.get("1.0", tk.END).strip()
            if not text:
                return
            acts = load_activities()
            for a in acts:
                if a.get("id") == activity.get("id"):
                    a.setdefault("submissions", []).append({"student": user.get("username"), "text": text, "date": datetime.date.today().isoformat(), "grade": None})
            save_activities(acts)
            show_activity_detail(user, activity)
        tk.Button(dashboard_frame, text="Enviar", command=submit_resp, bg="#4CAF50", fg="white").pack(pady=6)

        # If user is Professor or Administrativo, show submissions list and grading UI
        role = user.get("_role")
        if role in ("Professor", "Administrativo"):
            tk.Label(dashboard_frame, text="\nSubmissões:", font=("Arial", 11, "bold")).pack(pady=6)
            subs = activity.get("submissions", [])
            tk.Label(dashboard_frame, text=f"Total: {len(subs)}").pack()
            listf = tk.Frame(dashboard_frame)
            listf.pack(pady=6)
            def open_submission(sub):
                # popup to view and grade
                sp = tk.Toplevel()
                sp.title(f"Submissão de {sub.get('student')}")
                sp.geometry("500x400")
                tk.Label(sp, text=f"Aluno: {sub.get('student')}", font=("Arial", 11, "bold")).pack(pady=6)
                tk.Label(sp, text=f"Data: {sub.get('date')}").pack()
                txt = tk.Text(sp, height=12, width=60)
                txt.pack(pady=8)
                txt.insert("1.0", sub.get("text") or "")
                # grading controls
                tk.Label(sp, text="Atribuir nota (0-10):").pack()
                grade_var = tk.StringVar(value="" if sub.get("grade") is None else str(sub.get("grade")))
                grade_entry = tk.Entry(sp, textvariable=grade_var, width=8)
                grade_entry.pack()
                tk.Label(sp, text="Matéria:").pack()
                subj_var = tk.StringVar(value="Matemática")
                subj_menu = tk.OptionMenu(sp, subj_var, "Matemática", "Português", "Programação")
                subj_menu.pack()
                def do_grade():
                    try:
                        g = float(grade_var.get())
                        if g < 0 or g > 10:
                            return
                    except Exception:
                        return
                    # persist grade in activity submission and in student's record
                    acts = load_activities()
                    for a in acts:
                        if a.get("id") == activity.get("id"):
                            for s in a.setdefault("submissions", []):
                                if s.get("student") == sub.get("student") and s.get("date") == sub.get("date"):
                                    s["grade"] = g
                                    s["graded_by"] = user.get("username")
                    save_activities(acts)
                    # update student DB
                    students = load_db("Aluno")
                    for st in students:
                        if st.get("username") == sub.get("student"):
                            # ensure grades structure
                            st_grades = st.setdefault("grades", {})
                            subj = subj_var.get()
                            # decide semester placement: if activity deadline in first half of year -> sem1 else sem2 (simple heuristic)
                            # determine semester using C helper if available (faster), otherwise fallback to Python
                            sem_key = "sem1"
                            dl = activity.get("deadline")
                            try:
                                if has_semester_helper and isinstance(dl, str):
                                    # call C helper (returns 1 or 2)
                                    res = lib.semester_from_iso_date(dl.encode('ascii'))
                                    sem_key = "sem1" if res == 1 else ("sem2" if res == 2 else "sem1")
                                else:
                                    ad = parse_date(dl)
                                    sem_key = "sem1" if ad and ad.month <= 6 else "sem2"
                            except Exception:
                                sem_key = "sem1"
                            st_grades.setdefault(subj, {"sem1": None, "sem2": None})
                            st_grades[subj][sem_key] = g
                    save_db("Aluno", students)
                    # refresh
                    sp.destroy()
                    show_activity_detail(user, activity)
                tk.Button(sp, text="Salvar Nota", command=do_grade, bg="#4CAF50", fg="white").pack(pady=8)

            for s in subs:
                btn = tk.Button(listf, text=f"{s.get('student')} ({'nota: ' + str(s.get('grade')) if s.get('grade') is not None else 'sem nota'})", command=lambda ss=s: open_submission(ss))
                btn.pack(fill="x", padx=8, pady=2)

        tk.Button(dashboard_frame, text="Voltar", command=lambda: show_activities_list(user)).pack(pady=6)


    def create_activity_popup(user):
        popup = tk.Toplevel()
        popup.title("Criar Atividade")
        popup.geometry("520x380")
        frm = tk.Frame(popup)
        frm.pack(pady=8)
        tk.Label(frm, text="Título:").grid(row=0, column=0, sticky="e")
        title = tk.Entry(frm, width=45)
        title.grid(row=0, column=1)
        tk.Label(frm, text="Descrição:").grid(row=1, column=0, sticky="e")
        desc = tk.Entry(frm, width=45)
        desc.grid(row=1, column=1)
        tk.Label(frm, text="Prazo (YYYY-MM-DD):").grid(row=2, column=0, sticky="e")
        deadline = tk.Entry(frm, width=18)
        deadline.grid(row=2, column=1, sticky="w")
        # Targets
        tk.Label(frm, text="Curso (opcional):").grid(row=3, column=0, sticky="e")
        t_curso = tk.Entry(frm, width=25)
        t_curso.grid(row=3, column=1, sticky="w")
        tk.Label(frm, text="Turma (opcional):").grid(row=4, column=0, sticky="e")
        t_turma = tk.Entry(frm, width=12)
        t_turma.grid(row=4, column=1, sticky="w")
        tk.Label(frm, text="Semestre (opcional):").grid(row=5, column=0, sticky="e")
        t_sem = tk.Entry(frm, width=6)
        t_sem.grid(row=5, column=1, sticky="w")
        tk.Label(frm, text="Período (opcional):").grid(row=6, column=0, sticky="e")
        t_period = tk.Entry(frm, width=10)
        t_period.grid(row=6, column=1, sticky="w")
        # Attachment
        tk.Label(frm, text="Anexos:").grid(row=7, column=0, sticky="e")
        attach_label = tk.Label(frm, text="Nenhum")
        attach_label.grid(row=7, column=1, sticky="w")
        attach_path = {"path": ""}
        def pick_file():
            from tkinter import filedialog
            fp = filedialog.askopenfilename()
            if fp:
                attach_label.config(text=os.path.basename(fp))
                attach_path["path"] = fp
        tk.Button(frm, text="Selecionar anexo", command=pick_file).grid(row=7, column=2, sticky="w")

        def do_create_act():
            t = title.get().strip()
            d = deadline.get().strip()
            de = desc.get().strip()
            if not t or not d:
                return
            acts = load_activities()
            aid = max([a.get("id", 0) for a in acts], default=0) + 1
            attachments = []
            if attach_path.get("path"):
                src = attach_path.get("path")
                if src:
                    try:
                        src_str = str(src)
                        dstname = f"act_{aid}_" + os.path.basename(src_str)
                        dst = ATTACH_DIR / dstname
                        import shutil
                        shutil.copyfile(src_str, str(dst))
                        attachments.append(dstname)
                    except Exception:
                        pass
            target = {"curso": t_curso.get().strip() or None, "turma": t_turma.get().strip() or None, "semestre": t_sem.get().strip() or None, "periodo": t_period.get().strip() or None}
            acts.append({"id": aid, "title": t, "description": de, "deadline": d, "comments": [], "submissions": [], "attachments": attachments, "target": target})
            save_activities(acts)
            popup.destroy()

        tk.Button(popup, text="Criar", command=do_create_act, bg="#4CAF50", fg="white").pack(pady=8)


    def show_calendar(user):
        # Simple calendar: group activities by date and list
        for w in dashboard_frame.winfo_children():
            w.destroy()
        tk.Label(dashboard_frame, text="Calendário Escolar", font=("Arial", 14, "bold")).pack(pady=8)
        acts = load_activities()
        bydate = {}
        for a in acts:
            d = parse_date(a.get("deadline"))
            key = d.isoformat() if d else "Sem data"
            bydate.setdefault(key, []).append(a)
        for date in sorted([k for k in bydate.keys() if k != "Sem data"]):
            tk.Label(dashboard_frame, text=date, font=("Arial", 11, "bold")).pack(anchor="w", padx=12)
            for a in bydate.get(date, []):
                tk.Label(dashboard_frame, text=f" - {a.get('title')}").pack(anchor="w", padx=24)
        if "Sem data" in bydate:
            tk.Label(dashboard_frame, text="Sem data", font=("Arial", 11, "bold")).pack(anchor="w", padx=12)
            for a in bydate.get("Sem data", []):
                tk.Label(dashboard_frame, text=f" - {a.get('title')}").pack(anchor="w", padx=24)
        tk.Button(dashboard_frame, text="Voltar", command=lambda: show_dashboard("Aluno", user)).pack(pady=8)


    def do_logout():
        # Show initial entry screen on logout
        dashboard_frame.pack_forget()
        user_entry.delete(0, tk.END)
        pass_entry.delete(0, tk.END)
        msg_label.config(text="", fg="red")
        entry_frame.pack(fill="both", expand=True)
        try:
            bottom.pack_forget()
        except Exception:
            pass
    # initial entry screen: single button to choose login
    tk.Label(entry_frame, text="Plataforma de Estudos", font=("Arial", 16, "bold")).pack(pady=20)
    tk.Button(entry_frame, text="Entrar", command=lambda: (entry_frame.pack_forget(), login_frame.pack(fill="both", expand=True)), bg="#2196F3", fg="white", width=18).pack(pady=10)
    entry_frame.pack(fill="both", expand=True)
    janela.mainloop()


# ----------------------------
# Aliases e wrappers em Português
# ----------------------------
# Traduções de nomes de variáveis e funções para facilitar manutenção
ACESSIBILIDADE = ACCESSIBILITY
TEMA = THEME
CACHE_IMAGENS = _IMAGE_CACHE

# Funções/aliases (mantém os nomes originais também para compatibilidade)
def narrar(texto):
    """Alias em português para narrar texto via TTS."""
    return speak(texto)

def aplicar_acessibilidade(widget, texto_label: str):
    """Alias em português para aplicar handlers de acessibilidade."""
    return apply_a11y(widget, texto_label)

def iniciar_aplicacao():
    """Alias em português para iniciar a aplicação (compatível com start_app)."""
    return start_app()

def carregar_db(role):
    return load_db(role)

def salvar_db(role, data):
    return save_db(role, data)

def carregar_atividades():
    return load_activities()

def salvar_atividades(data):
    return save_activities(data)

# Observação: muitas funções de UI (criar_atividade_popup, assign_grades_popup, etc.)
# estão definidas dentro de `start_app()` (escopo local). Para convertê-las para
# nomes em português persistentemente, é necessário mover essas funções para o
# escopo do módulo (de-indentá-las). Isso é um refactor maior. Por enquanto
# fornecemos aliases para as funções e constantes de nível de módulo.


if __name__ == "__main__":
    start_app()
