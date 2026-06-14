import customtkinter as ctk
from PIL import Image 
from tkinter import messagebox, Toplevel, filedialog
import sqlite3
import pandas as pd
import os
import datetime
import webbrowser 
import urllib.parse 
import shutil 
from tkcalendar import DateEntry 
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet 
import json

# --- 1A. CONFIGURATION MANAGEMENT ---

CONFIG_FILE = "config.json"

def load_config():
    """Loads configuration from config.json or returns defaults."""
    default_config = {
        # Prescription Header Settings (Default Professional Header)
        # NOTE: Edit these values directly in config.json to customize the slip.
        "HEADER_LINE_1": "MASOOD CLINIC",
        "HEADER_LINE_2": "DR. KHALID MASOOD",
        "HEADER_LINE_3": "M.Sc, D.H.M.S (PUNJAB)",
        "HEADER_LINE_4": "R.H.M.P (NCH)",
        "HEADER_LINE_5": "VICE PRINCIPLE - Farabi Homeo Medical College",
        "HEADER_LINE_6": "X-Public Health Physician (THQ) Hospital, Shah pur",
        "HEADER_LINE_7": "BLOCK W, NEW SATELLITE TOWN, SARGODHA",
        "HEADER_LINE_8": "0300-3500075, 0332-3500075"
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                default_config.update(loaded_config)
                return default_config
        except json.JSONDecodeError:
            print(f"Error reading {CONFIG_FILE}. Using default config.")
            return default_config
    
    # If file doesn't exist, save the default config for the user to edit later
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"Created default {CONFIG_FILE}. Edit this file for header customization.")
    except Exception as e:
        print(f"Warning: Could not save default config file: {e}")

    return default_config

def save_config(config_data):
    """Saves the configuration to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

# --- 1B. Global Variables and Database Setup ---

DB_NAME = "pharmaflow.db"
SELECTED_RECORD_DATA = {} 
COLUMN_NAMES = [] 

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Existing migration and table creation logic (unchanged)
    
    cursor.execute("PRAGMA table_info(patients)")
    columns = [col[1] for col in cursor.fetchall()]
    
    is_old_schema = ('id' in columns) and ('mc' not in columns)
    
    if is_old_schema:
        # Migration logic skipped for brevity, assumed to be working
        pass
            
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            mc INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            medicine TEXT NOT NULL,
            dosage TEXT, 
            address TEXT,
            phone TEXT,
            date_created TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
        )
    """)
    
    # Schema check/fix (unchanged)
    try:
        cursor.execute("PRAGMA table_info(patients)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'date_created' not in columns:
            cursor.execute("ALTER TABLE patients ADD COLUMN date_created TEXT DEFAULT NULL")

        cursor.execute("SELECT COUNT(*) FROM patients WHERE date_created IS NULL OR date_created = ''")
        null_count = cursor.fetchone()[0]

        if null_count > 0:
            cursor.execute("UPDATE patients SET date_created = '2025-01-01 00:00:00' WHERE date_created IS NULL OR date_created = ''")
        
    except sqlite3.Error as e:
        print(f"DATABASE MIGRATION ERROR: {e}")
    
    # MC Reset Logic (unchanged)
    cursor.execute("SELECT COUNT(*) FROM patients")
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='patients'")
    
    # Users Table for Login (unchanged)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', 'password'))
    
    conn.commit()
    conn.close()

def execute_db_query(query, params=()): 
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def fetch_db_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()
    return data

# --- 2. HTML Generation Functions (User styles applied & Slip layout updated) ---

def _get_print_css_and_header(config): 
    IMAGE_FILENAME = 'logo.png'
    try:
        absolute_path = os.path.abspath(IMAGE_FILENAME)
        path_segments = absolute_path.replace('\\', '/').lstrip('/')
        encoded_path = urllib.parse.quote(path_segments)
        image_uri = f'file:///{encoded_path}'
        
    except Exception as e:
        print(f"Error resolving image path. Falling back to relative path. Error: {e}")
        image_uri = IMAGE_FILENAME 

    # --- CSS STYLE (UPDATED to ensure content-section border matches details-section border) ---
    css_style = f"""
        body {{
            font-family: 'Times New Roman', serif;
            color: #333;
            margin: 0;
            padding: 20mm; 
            box-sizing: border-box;
            line-height: 1.5;
            min-height: 297mm; 
            position: relative; 
            font-size: 11pt; 
        }}
        .container {{
            width: 100%;
            max-width: 210mm; 
            margin: 0 auto;
            position: relative;
            z-index: 10; 
        }}
        .header {{
    position: relative;
    text-align: center;
    margin-bottom: 20px;
    padding-top: 60px; /* This creates the empty space at the top for the logo */
        }}
        /* LOGO CONTAINER STYLING (User Requested: Width 120, Height 150) */
        .logo-container {{
    position: absolute;
    top: -10px;   /* Pulls it higher up into the new padding space */
    right: 10px;  /* Moves it slightly away from the very edge */
    width: 120px; 
    height: 120px; /* Keep this square to match your logo shape */
        }}
        .logo-img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        /* CLINIC NAME STYLING (User Requested: Color #FF0000, Size 36pt) */
        .clinic-name {{
            font-size: 36px; /* USER SET SIZE: changed from pt to px for consistency with CSS usage */
            font-weight: bold;
            color: #FF0000; /* USER SET COLOR */
            margin-bottom: 3px;
            border-bottom: 2px solid #004d40;
            padding-bottom: 5px;
        }}
        .doctor-name {{
            font-size: 20px;
            font-weight: bold;
            color: #006064; 
            margin-top: 5px;
        }}
        .degrees {{
            margin: 5px 0 10px 0;
            font-size: 11pt;
            line-height: 1.3;
        }}

        .contact-info {{
            font-size: 11pt;
            margin-top: 5px;
            padding: 5px 0;
            border-top: 1px solid #ccc;
            border-bottom: 1px solid #ccc;
        }}
        .contact-info p {{
            margin: 2px 0;
            display: inline-block;
            width: 48%;
            text-align: left;
        }}
        .details-section {{
            margin-top: 15px;
            margin-bottom: 20px;
            padding: 10px 15px;
            border: 2px solid #004d40; /* ID Box Border */
            border-radius: 8px;
            background-color: #f0fafa; 
            overflow: hidden; 
        }}
        .details-section strong {{
            color: #004d40;
        }}
        .detail-item {{
            float: left;
            width: 33%;
            margin-bottom: 5px;
        }}
        .diagnosis {{
            width: 100%;
            float: none;
            margin-top: 10px; 
            padding-top: 5px;
            font-size: 14pt;
            font-weight: bold;
            color: #cc0000; 
        }}
        .rx-title {{
            text-align: center;
            font-size: 30px;
            font-weight: bold;
            color: #004d40;
            margin: 30px 0 10px 0;
            padding: 5px 20px;
            border: 3px double #004d40;
            display: inline-block;
            border-radius: 5px;
        }}
        /* NEW STYLING: Content Section Border now matches Details Section Border */
        .content-section {{
            margin-top: 20px;
            margin-bottom: 30px;
            padding: 15px;
            border: 2px solid #004d40; /* MATCHES DETAILS BORDER */
            border-radius: 8px; /* MATCHES DETAILS BORDER */
            background-color: #ffffff;
        }}
        .medicine-list {{
            font-size: 16pt; 
            margin-left: 20px; 
            margin-top: 10px;
            font-weight: bold;
            white-space: pre-wrap;
        }}
        .instructions {{
            margin-top: 25px;
            padding-top: 10px;
            border-top: 1px solid #ccc;
            font-size: 12pt;
        }}
        .signature {{
            margin-top: 70px;
            padding-top: 10px;
            border-top: 1px solid #333;
            text-align: right;
            font-size: 14pt;
        }}

        @media print {{
            body {{
                padding: 10mm;
                margin: 0;
            }}
            .no-print {{
                display: none !important;
            }}
        }}
    """
    
    # --- DYNAMIC HTML HEADER GENERATION ---
    
    header_lines = [config.get(f"HEADER_LINE_{i}", "") for i in range(3, 7)]
    
    html_header = f"""
        <div class="header">
            <div class="logo-container">
                <img src="{image_uri}" class="logo-img" alt="Clinic Logo">
            </div>
            <div class="clinic-name">{config.get("HEADER_LINE_1", "N/A")}</div>
            <div class="doctor-name">{config.get("HEADER_LINE_2", "N/A")}</div>
            <div class="degrees">
                {'<br>'.join(filter(None, header_lines))}
            </div>
            <div class="contact-info">
                <p><strong>Address:</strong> {config.get("HEADER_LINE_7", "N/A")}</p>
                <p style="text-align: right;"><strong>Contact:</strong> {config.get("HEADER_LINE_8", "N/A")}</p>
            </div>
        </div>
    """
    
    return css_style, html_header, image_uri

def generate_html_prescription(data, config):
    css_style, html_header, _ = _get_print_css_and_header(config)
    current_date = datetime.date.today().strftime("%d %B, %Y")

    name = data.get('name', 'N/A')
    age = data.get('age', 'N/A')
    gender = data.get('gender', 'N/A')
    phone = data.get('phone', 'N/A')
    address = data.get('address', 'N/A')
    medicine = data.get('medicine', 'N/A')
    diagnosis = data.get('dosage', 'N/A') 
    mc_no = data.get('mc', 'N/A')
    
    # --- STYLED HTML Structure for Prescription (UPDATED) ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prescription Slip - {name}</title>
        <style>{css_style}</style>
        <script>window.onload = function() {{ window.print(); }};</script>
    </head>
    <body>
        
        <div class="container">
            {html_header}

            <div class="details-section">
                <div class="detail-item"><strong>Date:</strong> {current_date}</div>
                <div class="detail-item"><strong>MC No:</strong> {mc_no}</div>
                <div class="detail-item"><strong>Age/Gender:</strong> {age} / {gender}</div>
                
                <div class="detail-item" style="width: 66%;"><strong>Patient Name:</strong> {name}</div>
                <div class="detail-item"><strong>Contact No:</strong> {phone}</div>

                <div class="detail-item" style="width: 99%;"><strong>Address:</strong> {address}</div>

                <div class="diagnosis">
                    Diagnosis: <span style="text-decoration: underline;">{diagnosis}</span>
                </div>
                <div style="clear: both;"></div>
            </div>

            <div style="text-align: center;">
                <span class="rx-title">Medicine</span>
            </div>

            <div class="content-section">
                <strong>Prescribed Medicine(s):</strong>
                <p class="medicine-list">{medicine}</p>
                
                <div class="instructions">
                    <strong>Instructions / Dosage:</strong>
                    <p>As advised by the physician. Please follow the guidance strictly.</p>
                </div>
            </div>
            
            <div class="signature">
                Physician Signature:
                <br>
                ________________________________
            </div>

        </div>
    </body>
    </html>
    """
    return html_content

def generate_html_certification(custom_content, config):
    css_style, html_header, _ = _get_print_css_and_header(config)
    current_date = datetime.date.today().strftime("%d %B, %Y")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>General Clinic Slip</title>
        <style>{css_style}</style>
        <script>window.onload = function() {{ window.print(); }};</script>
    </head>
    <body>
        
        <div class="container">
            {html_header}

            <div class="details-section" style="border: none;">
                <div style="float: right; font-weight: bold;">Date: {current_date}</div>
                <h2 style="text-align: center; margin-bottom: 20px; color: #004d40;">GENERAL CERTIFICATION / SLIP</h2>
                <div style="clear: both;"></div>
            </div>

            <div class="content-section" style="min-height: 250px;">
                <pre class="content-body" style="font-family: Arial, sans-serif; font-size: 12pt; white-space: pre-wrap;">{custom_content}</pre>
            </div>
            
            <div class="signature">
                Physician Signature:
                <br>
                ________________________________
            </div>

        </div>
    </body>
    </html>
    """
    return html_content


# --- 3. Reporting Window Class (Unchanged) ---
class ReportingWindow(ctk.CTkToplevel):
    def __init__(self, master, disease_list):
        super().__init__(master)
        self.title("PharmaFlow Reporting Module")
        self.geometry("750x650")
        self.transient(master) 
        self.grab_set() 
        self.disease_list = ["-- ALL --"] + disease_list
        self.master = master
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        filter_frame = ctk.CTkFrame(self)
        filter_frame.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")
        filter_frame.grid_columnconfigure((0, 2, 4, 6), weight=0) 
        filter_frame.grid_columnconfigure((1, 3, 5, 7, 8), weight=1) 

        ctk.CTkLabel(filter_frame, text="Start Date:").grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        self.start_date = DateEntry(filter_frame, selectmode='day', date_pattern='yyyy-mm-dd', width=10)
        self.start_date.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.start_date.set_date(datetime.date.today() - datetime.timedelta(days=30)) 

        ctk.CTkLabel(filter_frame, text="End Date:").grid(row=0, column=2, padx=(10, 5), pady=5, sticky="w")
        self.end_date = DateEntry(filter_frame, selectmode='day', date_pattern='yyyy-mm-dd', width=10)
        self.end_date.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.end_date.set_date(datetime.date.today())

        ctk.CTkLabel(filter_frame, text="Diagnosis:").grid(row=0, column=4, padx=(10, 5), pady=5, sticky="w")
        self.disease_var = ctk.StringVar(value=self.disease_list[0])
        self.disease_combo = ctk.CTkComboBox(filter_frame, values=self.disease_list, variable=self.disease_var, width=150)
        self.disease_combo.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        
        load_button = ctk.CTkButton(filter_frame, text="⚙️ Run Report", command=self.load_report, fg_color="#008080", hover_color="#006666", width=120)
        load_button.grid(row=0, column=6, padx=(15, 5), pady=5, sticky="e")
        
        export_csv_button = ctk.CTkButton(filter_frame, text="⬇️ Export CSV", command=lambda: self.export_data('csv'), fg_color="#006400", hover_color="#004d00", width=100)
        export_csv_button.grid(row=0, column=7, padx=5, pady=5, sticky="e")
        
        export_pdf_button = ctk.CTkButton(filter_frame, text="⬇️ Export PDF", command=lambda: self.export_data('pdf'), fg_color="#4169e1", hover_color="#304f9e", width=100)
        export_pdf_button.grid(row=0, column=8, padx=5, pady=5, sticky="e")

        self.report_display_frame = ctk.CTkScrollableFrame(self) 
        self.report_display_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.report_display_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.report_display_frame, text="Filtered Patient Records Preview", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.report_widgets = []
        self.current_data = [] 

        self.load_report()
        
    def load_report(self):
        start_date = self.start_date.get_date().strftime('%Y-%m-%d 00:00:00')
        end_date = self.end_date.get_date().strftime('%Y-%m-%d 23:59:59') 
        selected_disease = self.disease_var.get()
        
        query = "SELECT mc, name, age, gender, medicine, dosage, date_created FROM patients WHERE date_created BETWEEN ? AND ?"
        params = [start_date, end_date]
        
        if selected_disease != "-- ALL --":
            query += " AND dosage LIKE ?"
            params.append(f'%{selected_disease}%') 
            
        try:
            records = fetch_db_query(query, tuple(params))
            self.current_data = records
            self._display_report_preview(records)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to run report query: {e}")
            self.current_data = []
            self._display_report_preview([])
            
    def _display_report_preview(self, records):
        # Clear existing content below the manually added header
        for widget in self.report_widgets:
            widget.destroy()
        self.report_widgets = []

        if not records:
            msg = ctk.CTkLabel(self.report_display_frame, text="No records found matching the current filters.", text_color="red")
            msg.grid(row=1, column=0, padx=10, pady=10) # Start from row 1
            self.report_widgets.append(msg)
            return

        headers = ["MC No", "Name", "Age", "Gender", "Medicine", "Diagnosis", "Date Added"]
        header_frame = ctk.CTkFrame(self.report_display_frame, fg_color=("#3A88D1", "#1E6C9F")) 
        header_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5)) # Start from row 1
        header_frame.grid_columnconfigure(tuple(range(len(headers))), weight=1)

        for j, header in enumerate(headers):
            label = ctk.CTkLabel(header_frame, text=header, font=ctk.CTkFont(weight="bold"), text_color="white")
            label.grid(row=0, column=j, padx=5, pady=5, sticky="ew")
            self.report_widgets.append(label)

        for i, record in enumerate(records):
            row_frame = ctk.CTkFrame(self.report_display_frame, fg_color=("#F0F0F0", "#303030"))
            row_frame.grid(row=i + 2, column=0, sticky="ew", pady=(0, 2)) # Start data rows from row 2
            row_frame.grid_columnconfigure(tuple(range(len(headers))), weight=1) 
            
            for j, data_item in enumerate(record):
                if headers[j] == "Date Added":
                    display_text = str(data_item).split(' ')[0] if data_item else 'N/A'
                else:
                    display_text = str(data_item)
                    
                label = ctk.CTkLabel(row_frame, text=display_text, text_color=("black", "white"), anchor="w", wraplength=100)
                label.grid(row=0, column=j, padx=5, pady=2, sticky="ew")
                self.report_widgets.append(label)
                
            self.report_widgets.append(row_frame)
            
    def export_data(self, format_type):
        if not self.current_data:
            messagebox.showwarning("Export Failed", "No data to export. Please run the report first.")
            return

        headers = ["MC No", "Name", "Age", "Gender", "Medicine", "Diagnosis", "Date Added"]
        df = pd.DataFrame(self.current_data, columns=headers)
        
        current_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type == 'csv':
            file_path = f"report_patients_{current_datetime}.csv"
            df.to_csv(file_path, index=False)
            messagebox.showinfo("Export Success", f"CSV report saved successfully to:\n{os.path.abspath(file_path)}")
            webbrowser.open_new_tab(os.path.abspath(file_path))

        elif format_type == 'pdf':
            file_path = f"report_patients_{current_datetime}.pdf"
            self._generate_pdf_report(df, file_path)
            messagebox.showinfo("Export Success", f"PDF report generated and saved to:\n{os.path.abspath(file_path)}")
            webbrowser.open_new_tab(os.path.abspath(file_path))
            
    def _generate_pdf_report(self, df, filename):
        try:
            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            title = Paragraph(f"PharmaFlow Patient Report", styles['Title'])
            story.append(title)
            
            subtitle_text = (
                f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
                f"Filters: {self.start_date.get_date().strftime('%Y-%m-%d')} to {self.end_date.get_date().strftime('%Y-%m-%d')}<br/>"
                f"Diagnosis: {self.disease_var.get()}"
            )
            story.append(Paragraph(subtitle_text, styles['Normal']))
            story.append(Spacer(1, 12))

            data = [df.columns.tolist()] + df.values.tolist()
            table_data = [[str(cell) for cell in row] for row in data]

            table = Table(table_data, colWidths=[0.5*letter[0]/len(df.columns)]*len(df.columns))

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkcyan), 
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), 
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige), 
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))

            story.append(table)
            doc.build(story)
            
        except Exception as e:
            messagebox.showerror("PDF Error", f"Failed to generate PDF report: {e}")

# --- 4. CustomTkinter Application Classes ---

class PharmaFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("MASOOD CLINIC Management System")
        self.geometry("600x700")
        # 1. Load configuration FIRST
        self.config = load_config()
        initialize_db()

        # 2. NOW set the appearance (Memory fixed!)
        ctk.set_appearance_mode(self.config.get("appearance_mode", "Light"))
        ctk.set_default_color_theme("blue")
        initialize_db()
        
        # Configure grid for two columns: Input and Data
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure((0, 1), weight=1) 

        self.login_window = LoginWindow(self, self.show_main_app)
        self.login_window.grid(row=0, column=0, columnspan=2, sticky="nsew") 
        
    def show_main_app(self):
        self.login_window.grid_forget()
        
        # Pass the loaded config to MainFrame
        self.main_frame = MainFrame(self, config=self.config) 
        
        # Display main frame across two columns
        self.main_frame.grid(row=0, column=0, columnspan=2, sticky="nsew") 
        
        # Adjust column weights after login
        self.grid_columnconfigure(0, weight=30) 
        self.grid_columnconfigure(1, weight=70)
        # --- THEME TOGGLE (TARGETING YOUR BOX) ---
        self.theme_menu = ctk.CTkOptionMenu(self.main_frame, 
                                            values=["Light", "Dark", "System"],
                                            width=100, 
                                            command=self.change_appearance_mode)
        
        # pady=(15, 0) -> Moves it down from the top edge
        # padx=(0, 100) -> Increases the distance from the right wall significantly
        self.theme_menu.grid(row=0, column=1, padx=(0, 200), pady=(40, 0), sticky="ne")
        
        # Sync the menu with your saved preference
        self.theme_menu.set(self.config.get("appearance_mode", "Light"))
        # --- REPEATING MAINTENANCE REMINDER SYSTEM ---
        import threading
        import time

        def reminder_loop():
            # Initial wait of 10 seconds after login
            time.sleep(10)
            while True:
                messagebox.showinfo("Safety Reminder", 
                    "🕒 Scheduled Maintenance Check:\n\n"
                    "Please ensure you have exported your latest data.\n"
                    "Regular backups prevent patient record loss!")
                
                # Wait for 5 hours (5 * 60 minutes * 60 seconds)
                time.sleep(5 * 3600)

        # Start the timer in the background so the app doesn't freeze
        threading.Thread(target=reminder_loop, daemon=True).start()   
    def change_appearance_mode(self, new_appearance_mode: str):
        # Apply the new theme (Light or Dark) instantly
        ctk.set_appearance_mode(new_appearance_mode)
        
        # Save this choice to config.json
        self.config["appearance_mode"] = new_appearance_mode
        with open('config.json', 'w') as f:
            import json
            json.dump(self.config, f, indent=4)
class LoginWindow(ctk.CTkFrame):
    def __init__(self, master, login_callback):
        super().__init__(master)
        self.login_callback = login_callback
        self.failed_attempts = 0  # Tracks wrong passwords
        self.grid_rowconfigure((0, 6), weight=1)
        self.grid_columnconfigure(0, weight=1)
        # 1. Load the Logo Image
        self.logo_path = "logo.png"
        self.logo_image = ctk.CTkImage(light_image=Image.open(self.logo_path),
                                       dark_image=Image.open(self.logo_path),
                                       size=(200, 200))

        # 2. Place Logo directly on the screen (Modern Minimalist Look)
        self.logo_label = ctk.CTkLabel(self, image=self.logo_image, text="", fg_color="transparent")
        self.logo_label.grid(row=0, column=0, pady=(30, 0)) # row=0 puts it at the very top
        
        ctk.CTkLabel(self, text="MASOOD CLINIC", font=ctk.CTkFont(size=24, weight="bold")).grid(row=1, column=0, pady=40)
        
        self.username_entry = ctk.CTkEntry(self, placeholder_text="Username", width=250)
        self.username_entry.grid(row=2, column=0, pady=10, padx=30)
        
        self.password_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=250)
        self.password_entry.grid(row=3, column=0, pady=(0, 5), padx=30)
        
        self.login_button = ctk.CTkButton(self, text="Login", command=self.attempt_login, width=250)
        self.login_button.grid(row=4, column=0, pady=(5, 15), padx=30)
        
        ctk.CTkLabel(self, text="Hint: admin / password", text_color="gray").grid(row=6, column=0, pady=(5, 20))
        # --- DISPLAY LAST BACKUP TIME WITH SMART COLOR ---
        import datetime
        last_backup_str = master.config.get('last_backup', 'Never')
        display_color = "gray" # Default color

        if last_backup_str != 'Never':
            try:
                # Calculate if it has been more than 24 hours
                last_time = datetime.datetime.strptime(last_backup_str, "%Y-%m-%d %I:%M:%S %p")
                if datetime.datetime.now() - last_time > datetime.timedelta(hours=24):
                    display_color = "#FF4B4B"  # Professional Red
            except:
                pass

        self.backup_label = ctk.CTkLabel(self, 
            text=f"Last Data Export: {last_backup_str}", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=display_color)
        self.backup_label.grid(row=5, column=0, pady=(10))
    def attempt_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        # Database query to check user
        user_record = fetch_db_query("SELECT * FROM users WHERE username=? AND password=?", (username, password))

        if user_record:
            self.failed_attempts = 0 # Reset counter on success
            messagebox.showinfo("Login Success", "Welcome to PharmaFlow!")
            self.login_callback()
        else:
            self.failed_attempts += 1
            
            if self.failed_attempts >= 3:
                # This triggers the security lockout
                self.start_login_cooldown()
            else:
                remaining = 3 - self.failed_attempts
                messagebox.showerror("Login Failed", f"Invalid username or password.\n{remaining} attempts left.")

    def start_login_cooldown(self):
        import time
        # Disable button and entries
        # We add text_color_disabled="white" to stop it from turning grey
        self.login_button.configure(state="disabled", fg_color="#FF4B4B", text_color_disabled="white", font=ctk.CTkFont(weight="bold"))
        self.username_entry.configure(state="disabled")
        self.password_entry.configure(state="disabled")
        
        self.failed_attempts = 0 # Reset for next try
        
        # Countdown loop
        for i in range(15, 0, -1):
            self.login_button.configure(text=f"Locked ({i}s)")
            self.update() 
            time.sleep(1)
            
        # Re-enable
        # Reset back to your original blue and normal text settings
        self.login_button.configure(state="normal", text="Login", fg_color="#1f6aa5", text_color="white")
        self.username_entry.configure(state="normal")
        self.password_entry.configure(state="normal")

class CertificationWindow(ctk.CTkToplevel):
    def __init__(self, master, config):
        super().__init__(master)
        self.config = config 
        self.title("New Certification / General Slip")
        self.geometry("600x600")
        self.transient(master) 
        self.grab_set() 
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(main_frame, text="Type Custom Slip Content Below:", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=(0, 10), sticky="w")
        
        self.content_textbox = ctk.CTkTextbox(main_frame, width=550, height=450, font=("Arial", 12))
        self.content_textbox.grid(row=1, column=0, sticky="nsew", pady=10)
        
        default_content = (
            f"Date: {datetime.date.today().strftime('%d %B, %Y')}\n\n"
            "TO WHOM IT MAY CONCERN\n\n"
            "This is to certify that [Patient Name] aged [Age] has been examined on [Date] "
            "and is advised a rest period of [Days] due to [Diagnosis].\n\n\n"
            "_____________________________\n"
            "Doctor's Notes / Instructions"
        )
        self.content_textbox.insert("1.0", default_content)

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(15, 0), sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkButton(button_frame, text="🖨️ Print Custom Slip", command=self.print_slip, height=40, fg_color="#008080", hover_color="#006666").grid(row=0, column=0, padx=5, sticky="ew")
        ctk.CTkButton(button_frame, text="❌ Close", command=self.destroy, height=40, fg_color="#990000", hover_color="#700000").grid(row=0, column=1, padx=5, sticky="ew")

    def print_slip(self):
        custom_content = self.content_textbox.get("1.0", "end-1c").strip()
        
        if not custom_content:
            messagebox.showwarning("Warning", "Please type the certification or notes before printing.")
            return

        try:
            html_content = generate_html_certification(custom_content, self.config) 
            
            temp_file_path = "temp_certification_slip.html"
            with open(temp_file_path, "w") as f:
                f.write(html_content)
            
            webbrowser.open_new_tab(os.path.abspath(temp_file_path))
            
            messagebox.showinfo(
                "Print Initiated", 
                "The custom slip has been opened in a new browser tab, and printing has been automatically started."
            )

        except Exception as e:
            messagebox.showerror("Print Error", f"An error occurred during print preparation: {e}")

# --- Patient History Viewer Class (Updated to use Name for fetching) ---

class HistoryViewer(ctk.CTkToplevel):
    def __init__(self, master, patient_mc_no, patient_name, patient_phone):
        super().__init__(master)
        self.title(f"History for: {patient_name} (MC: {patient_mc_no})")
        self.geometry("900x600")
        self.transient(master) 
        self.grab_set() 
        
        self.patient_mc_no = patient_mc_no
        self.patient_name = patient_name
        self.patient_phone = patient_phone 
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Display MC No and Name
        ctk.CTkLabel(self, text=f"Patient: {self.patient_name} (MC: {self.patient_mc_no})", 
                     font=ctk.CTkFont(size=20, weight="bold"), text_color="#004d40").grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")
        
        self.history_frame = ctk.CTkScrollableFrame(self)
        self.history_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.history_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.load_history()

    def load_history(self):
        # Clear previous widgets
        for widget in self.history_frame.winfo_children():
            widget.destroy()

        # Query all records for the patient using Name only 
        query = """
            SELECT mc, date_created, dosage, medicine 
            FROM patients 
            WHERE name = ? 
            ORDER BY date_created DESC
        """
        records = fetch_db_query(query, (self.patient_name,))

        if not records:
            ctk.CTkLabel(self.history_frame, text="No previous records found for this patient.", 
                         text_color="red").grid(row=0, column=0, columnspan=4, pady=20)
            return

        # Headers
        headers = ["Date", "MC No", "Diagnosis/Chief Complaint", "Prescribed Medicine"]
        header_frame = ctk.CTkFrame(self.history_frame, fg_color=("#3A88D1", "#1E6C9F"))
        header_frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        header_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        for j, header in enumerate(headers):
            label = ctk.CTkLabel(header_frame, text=header, font=ctk.CTkFont(weight="bold"), text_color="white", padx=10, pady=5)
            label.grid(row=0, column=j, sticky="ew")

        # Display Records
        for i, record in enumerate(records):
            mc_no, full_date, diagnosis, medicine = record
            
            date_only = full_date.split(' ')[0] if full_date else 'N/A'
            
            # Use alternating colors for rows
            bg_color = ("#E8E8E8", "#2E2E2E") if i % 2 == 0 else ("#F8F8F8", "#3A3A3A")
            
            row_frame = ctk.CTkFrame(self.history_frame, fg_color=bg_color, corner_radius=0)
            row_frame.grid(row=i + 1, column=0, columnspan=4, sticky="ew", pady=(0, 1))
            row_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

            # Date (0)
            ctk.CTkLabel(row_frame, text=date_only, anchor="w", padx=10).grid(row=0, column=0, sticky="ew", padx=2, pady=5)
            
            # MC No (1)
            ctk.CTkLabel(row_frame, text=mc_no, anchor="w", padx=10).grid(row=0, column=1, sticky="ew", padx=2, pady=5)

            # Diagnosis (2) - Limit length for table view
            diag_display = (diagnosis[:50] + '...') if diagnosis and len(diagnosis) > 50 else (diagnosis or 'N/A')
            ctk.CTkLabel(row_frame, text=diag_display, anchor="w", padx=10, wraplength=200).grid(row=0, column=2, sticky="ew", padx=2, pady=5)
            
            # Medicine (3) - Limit length for table view
            med_display = (medicine[:50] + '...') if medicine and len(medicine) > 50 else (medicine or 'N/A')
            ctk.CTkLabel(row_frame, text=med_display, anchor="w", padx=10, wraplength=250).grid(row=0, column=3, sticky="ew", padx=2, pady=5)

# --- 5. MainFrame Class (Modified open_history_viewer) ---

class MainFrame(ctk.CTkFrame):
    
    DEFAULT_MEDICINES = [
        "Nux Vomica", "Arsenicum Album", "Pulsatilla", "Sepia", 
        "Sulphur", "Calcarea Carb", "Belladonna", "Ignatia",
        "Kali Bichromicum", "Rhus Tox", "Bryonia", "Gelsemium",
        "Arnica Montana", "Aconitum Napellus", "Chamomilla", 
        "Hydrastis Canadensis", "Echinacea", "Cinchona Officinalis (China)"
    ]
    
    DEFAULT_DISEASES = [
        "Fever (High Grade)", "Common Cold", "Influenza", "Cough (Dry)", 
        "Cough (Wet)", "Headache (Tension)", "Migraine", "Gastritis",
        "Constipation", "Diarrhea", "Joint Pain (Arthritis)", "Back Pain (Lumbar)",
        "Dermatitis (Eczema)", "Tonsillitis", "Anemia", "Insomnia",
        "Anxiety Disorder", "Allergies (Seasonal)"
    ]
    
    def __init__(self, master, config): 
        super().__init__(master)
        self.master = master
        self.config = config
        self.selected_record_mc = None
        
        self.medicine_suggestion_frame = None
        self.disease_suggestion_frame = None
        
        self.medicine_autocomplete_list = [] 
        self.disease_autocomplete_list = [] 
        
        self.label_font = ctk.CTkFont(size=14, weight="bold")
        self.header_font = ctk.CTkFont(size=20, weight="bold")
        self.action_button_font = ctk.CTkFont(size=16, weight="bold") 
        self.records_count_font = ctk.CTkFont(size=18, weight="bold") 
        self.filter_label_font = ctk.CTkFont(size=12, weight="bold") 
        
        self.grid_columnconfigure(0, weight=1) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)
        
        # --- Left Panel (Input/Action) ---
        self.input_frame = ctk.CTkFrame(self, border_width=2, border_color="#004d40") 
        self.input_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.input_frame.grid_columnconfigure(0, weight=1)
        self.input_frame.grid_rowconfigure(20, weight=1) 

        ctk.CTkLabel(self.input_frame, text="Patient Record Entry", font=self.header_font).grid(row=0, column=0, pady=(15, 10)) 

        # --- Input Widgets ---
        r = 1 
        self.name_entry = self._create_input_widget("Name:", r, mandatory=True); r += 2
        self.age_entry = self._create_input_widget("Age:", r, mandatory=True); r += 2
        
        ctk.CTkLabel(self.input_frame, text="Gender:", font=self.label_font).grid(row=r, column=0, padx=20, sticky="w")
        r += 1
        self.gender_var = ctk.StringVar(value="Male")
        self.gender_combobox = ctk.CTkComboBox(self.input_frame, values=["Male", "Female", "Other"], variable=self.gender_var)
        self.gender_combobox.grid(row=r, column=0, padx=20, pady=(0, 8), sticky="ew") 
        r += 1
        
        # Medicine Entry (with Autocomplete)
        self.medicine_entry = self._create_input_widget("Medicine:", r, mandatory=True); r += 1 
        self.medicine_entry._entry.bind("<KeyRelease>", self.check_autocomplete) 
        self.medicine_entry._entry.bind("<FocusOut>", lambda e: self.after(100, self.hide_suggestion_box, 'medicine')) 
        r += 1 
        self.medicine_suggestion_frame_row = r 
        r += 1 

        # Dosage/Disease Entry (with Autocomplete)
        self.dosage_entry = self._create_input_widget("Disease/Diagnosis:", r, mandatory=True); r += 1 
        self.dosage_entry._entry.bind("<KeyRelease>", self.check_autocomplete) 
        self.dosage_entry._entry.bind("<FocusOut>", lambda e: self.after(100, self.hide_suggestion_box, 'disease')) 
        r += 1
        self.disease_suggestion_frame_row = r 
        r += 1
        
        self.address_entry = self._create_input_widget("Address:", r); r += 2
        self.phone_entry = self._create_input_widget("Phone:", r); r += 2
        
        self.refresh_autocomplete_lists() 

        # Action Buttons Frame 
        action_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        action_frame.grid(row=r, column=0, padx=20, pady=(10, 0), sticky="ew") 
        action_frame.grid_columnconfigure((0, 1, 2), weight=1) 

        self.add_button = ctk.CTkButton(action_frame, text="➕ Add Patient", command=self.add_patient, height=40, font=self.action_button_font)
        self.add_button.grid(row=0, column=0, padx=5, pady=4, sticky="ew") 
        
        self.edit_button = ctk.CTkButton(action_frame, text="✏️ Update Selected", command=self.update_patient, fg_color="#ff8c00", hover_color="#cc7000", height=40, font=self.action_button_font) 
        self.edit_button.grid(row=0, column=1, padx=5, pady=4, sticky="ew")
        
        self.delete_button = ctk.CTkButton(action_frame, text="❌ Delete Selected", command=self.delete_patient, fg_color="#cc0000", hover_color="#990000", height=40, font=self.action_button_font) 
        self.delete_button.grid(row=0, column=2, padx=5, pady=4, sticky="ew")
        
        # New Row for Print/History
        self.print_button = ctk.CTkButton(action_frame, text="🖨️ Print Prescription", command=self.print_selected_record, fg_color="#008080", hover_color="#006666", height=40, font=self.action_button_font) 
        self.print_button.grid(row=1, column=0, padx=5, pady=4, sticky="ew")
        
        # HISTORY BUTTON
        self.history_button = ctk.CTkButton(action_frame, text="📚 View History", command=self.open_history_viewer, fg_color="#006064", hover_color="#004d50", height=40, font=self.action_button_font)
        self.history_button.grid(row=1, column=1, padx=5, pady=4, sticky="ew")

        self.report_button = ctk.CTkButton(action_frame, text="📈 Reports", command=self.open_reporting_module, fg_color="#4B0082", hover_color="#3A0064", height=40, font=self.action_button_font) 
        self.report_button.grid(row=1, column=2, padx=5, pady=4, sticky="ew")

        # Third Row (Certification/Clear)
        self.certification_button = ctk.CTkButton(action_frame, text="📝 New Certification/Slip", command=self.open_certification_slip, fg_color="#4169e1", hover_color="#304f9e", height=40, font=self.action_button_font) 
        self.certification_button.grid(row=2, column=0, columnspan=2, padx=5, pady=4, sticky="ew")
        
        self.clear_button = ctk.CTkButton(action_frame, text="🧹 Clear Fields", command=self.clear_fields, font=self.action_button_font)
        self.clear_button.grid(row=2, column=2, padx=5, pady=(4, 10), sticky="ew") 
        
        r += 1 

        # --- Right Panel (Data Display/Search/Export) ---
        self.display_frame = ctk.CTkFrame(self)
        self.display_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")
        self.display_frame.grid_columnconfigure(0, weight=1)
        self.display_frame.grid_rowconfigure(2, weight=1) 

        stats_export_frame = ctk.CTkFrame(self.display_frame, fg_color="transparent")
        stats_export_frame.grid(row=0, column=0, pady=(15, 10), padx=10, sticky="ew")
        stats_export_frame.grid_columnconfigure((0, 1), weight=1)

        self.record_count_label = ctk.CTkLabel(stats_export_frame, text="Total Records: 0", font=self.records_count_font, text_color="#00A0A0") 
        self.record_count_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        self.export_button = ctk.CTkButton(stats_export_frame, text="⬇️ Full Export CSV", command=self.export_to_csv, fg_color="#006400", hover_color="#004d00", width=150) 
        self.export_button.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        
        # --- ADVANCED SEARCH FRAME ---
        filter_frame = ctk.CTkFrame(self.display_frame)
        filter_frame.grid(row=1, column=0, pady=10, padx=10, sticky="ew")
        filter_frame.grid_columnconfigure((1, 3), weight=1) 
        filter_frame.grid_columnconfigure((0, 2, 4), weight=0) 
        
        filter_entry_style = {
            "border_width": 1, 
            "border_color": ("black", "white"), 
            "corner_radius": 5
        }

        # Row 0: MC and Name
        row_mc_name = 0
        ctk.CTkLabel(filter_frame, text="MC No:", font=self.filter_label_font).grid(row=row_mc_name, column=0, padx=(10, 2), pady=(10, 5), sticky="w")
        self.filter_mc_entry = ctk.CTkEntry(filter_frame, width=80, placeholder_text="Enter MC No", **filter_entry_style)
        self.filter_mc_entry.grid(row=row_mc_name, column=1, padx=(0, 10), pady=(10, 5), sticky="w") 
        
        ctk.CTkLabel(filter_frame, text="Name:", font=self.filter_label_font).grid(row=row_mc_name, column=2, padx=(10, 2), pady=(10, 5), sticky="w")
        self.filter_name_entry = ctk.CTkEntry(filter_frame, placeholder_text="Enter Patient Name", **filter_entry_style)
        self.filter_name_entry.grid(row=row_mc_name, column=3, padx=(0, 10), pady=(10, 5), sticky="ew")
        
        # Row 1: Medicine and Diagnosis
        row_med_dx = 1
        ctk.CTkLabel(filter_frame, text="Medicine:", font=self.filter_label_font).grid(row=row_med_dx, column=0, padx=(10, 2), pady=5, sticky="w")
        self.filter_med_entry = ctk.CTkEntry(filter_frame, placeholder_text="Filter Medicine", **filter_entry_style)
        self.filter_med_entry.grid(row=row_med_dx, column=1, padx=(0, 10), pady=5, sticky="ew")
        
        ctk.CTkLabel(filter_frame, text="Diagnosis:", font=self.filter_label_font).grid(row=row_med_dx, column=2, padx=(10, 2), pady=5, sticky="w")
        self.filter_disease_entry = ctk.CTkEntry(filter_frame, placeholder_text="Filter Diagnosis", **filter_entry_style)
        self.filter_disease_entry.grid(row=row_med_dx, column=3, padx=(0, 10), pady=5, sticky="ew")
        
        # Row 2: Age Range
        row_age = 2
        ctk.CTkLabel(filter_frame, text="Age Min:", font=self.filter_label_font).grid(row=row_age, column=0, padx=(10, 2), pady=(5, 10), sticky="w")
        self.filter_age_min_entry = ctk.CTkEntry(filter_frame, width=50, placeholder_text="Min", **filter_entry_style)
        self.filter_age_min_entry.grid(row=row_age, column=1, padx=(0, 10), pady=(5, 10), sticky="w")

        ctk.CTkLabel(filter_frame, text="Age Max:", font=self.filter_label_font).grid(row=row_age, column=2, padx=(10, 2), pady=(5, 10), sticky="w")
        self.filter_age_max_entry = ctk.CTkEntry(filter_frame, width=50, placeholder_text="Max", **filter_entry_style)
        self.filter_age_max_entry.grid(row=row_age, column=3, padx=(0, 10), pady=(5, 10), sticky="w")
        
        # Search Button 
        self.search_button = ctk.CTkButton(filter_frame, text="🔍 Search/Reset", command=lambda: self.search_records(None), 
                                           fg_color="#006064", hover_color="#004d50", width=120, height=100)
        self.search_button.grid(row=0, column=4, rowspan=3, padx=(5, 10), pady=(10, 10), sticky="nsew")
        
        # Bind search method to key release on all filter fields
        self.filter_mc_entry.bind("<KeyRelease>", self.search_records)
        self.filter_name_entry.bind("<KeyRelease>", self.search_records)
        self.filter_med_entry.bind("<KeyRelease>", self.search_records)
        self.filter_disease_entry.bind("<KeyRelease>", self.search_records)
        self.filter_age_min_entry.bind("<KeyRelease>", self.search_records)
        self.filter_age_max_entry.bind("<KeyRelease>", self.search_records)
        
        self.listbox = ctk.CTkScrollableFrame(self.display_frame, border_width=2, border_color="#000000") 
        self.listbox.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.listbox.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.listbox, text="Patient Records (Click to Select)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.record_widgets = [] 
        self.refresh_records() 
    
    # --- History Viewer Method (MODIFIED) ---
    def open_history_viewer(self):
        if self.selected_record_mc is None:
            messagebox.showwarning("Warning", "Please select a patient record in the list before viewing history.")
            return

        # Use the Name from the selected record. Name is required now.
        mc_no = SELECTED_RECORD_DATA.get('mc') 
        name = SELECTED_RECORD_DATA.get('name')
        
        # Added check for missing Name from SELECTED_RECORD_DATA (to fix issue from screenshot)
        if not mc_no or not name:
             messagebox.showwarning("Warning", "The selected record is missing a Name or MC No, which is required to fetch history.")
             return
            
        phone = SELECTED_RECORD_DATA.get('phone', 'N/A') 
            
        if hasattr(self, 'history_window') and self.history_window.winfo_exists():
            self.history_window.destroy() 
            
        # Pass MC No, Name, and Phone to the viewer. The viewer uses Name for lookup.
        self.history_window = HistoryViewer(self.master, mc_no, name, phone)
    
    # --- UTILITY METHODS (Unchanged) ---
    def check_autocomplete(self, event):
        if event.widget == self.medicine_entry._entry:
            entry_widget = self.medicine_entry
            suggestion_frame_row = self.medicine_suggestion_frame_row
            suggestion_list = self.medicine_autocomplete_list
            frame_attribute = 'medicine_suggestion_frame'
        elif event.widget == self.dosage_entry._entry: 
            entry_widget = self.dosage_entry
            suggestion_frame_row = self.disease_suggestion_frame_row
            suggestion_list = self.disease_autocomplete_list
            frame_attribute = 'disease_suggestion_frame'
        else:
            return

        full_text = entry_widget.get()
        
        if ',' in full_text:
            search_term = full_text.split(',')[-1].strip().title()
        else:
            search_term = full_text.strip().title()

        if len(search_term) < 1 or event.keysym in ['BackSpace', 'Delete']: 
            if len(search_term) < 1:
                self.hide_suggestion_box(frame_attribute.split('_')[0])
                return

        suggestions = [
            item for item in suggestion_list 
            if search_term in item and item != search_term
        ]
        
        if suggestions:
            self.show_suggestion_box(entry_widget, suggestion_frame_row, suggestions, frame_attribute)
        else:
            self.hide_suggestion_box(frame_attribute.split('_')[0])

    def show_suggestion_box(self, entry_widget, row, suggestions, frame_attribute):
        if getattr(self, frame_attribute):
            getattr(self, frame_attribute).destroy()
        
        suggestion_frame = ctk.CTkFrame(self.input_frame, border_width=1, border_color="#008080")
        suggestion_frame.grid(row=row, column=0, padx=20, pady=(0, 5), sticky="ew")
        suggestion_frame.grid_columnconfigure(0, weight=1)
        setattr(self, frame_attribute, suggestion_frame)
        
        for i, suggestion in enumerate(suggestions[:8]):
            label = ctk.CTkLabel(suggestion_frame, text=suggestion, anchor="w", cursor="hand2", 
                                 fg_color=("#E0E0E0", "#2E2E2E"), corner_radius=5, padx=5, pady=2)
            label.grid(row=i, column=0, sticky="ew", padx=2, pady=1)
            
            label.bind("<Button-1>", lambda event, text=suggestion, entry=entry_widget, frame=frame_attribute: self.select_suggestion(text, entry, frame))
            label.bind("<Enter>", lambda event, widget=label: widget.configure(fg_color=("#A0C0E0", "#4A6C96")))
            label.bind("<Leave>", lambda event, widget=label: widget.configure(fg_color=("#E0E0E0", "#2E2E2E")))

    def select_suggestion(self, suggestion, entry_widget, frame_attribute):
        current_text = entry_widget.get()
        
        if ',' in current_text:
            last_comma_index = current_text.rfind(',')
            prefix = current_text[:last_comma_index + 1].strip() 
            new_text = f"{prefix} {suggestion}, "
        else:
            new_text = f"{suggestion}, "
            
        entry_widget.delete(0, 'end')
        entry_widget.insert(0, new_text)
        
        self.hide_suggestion_box(frame_attribute.split('_')[0])
        entry_widget._entry.focus()
    
    def hide_suggestion_box(self, box_type):
        """Hides the specified autocomplete suggestion box."""
        if box_type == 'medicine' and self.medicine_suggestion_frame:
            self.medicine_suggestion_frame.destroy()
            self.medicine_suggestion_frame = None
        elif box_type == 'disease' and self.disease_suggestion_frame:
            self.disease_suggestion_frame.destroy()
            self.disease_suggestion_frame = None
    
    def open_reporting_module(self):
        if hasattr(self, 'reporting_window') and self.reporting_window.winfo_exists():
            self.reporting_window.focus()
        else:
            self.refresh_autocomplete_lists() 
            self.reporting_window = ReportingWindow(self.master, self.disease_autocomplete_list)
            
    def open_certification_slip(self):
        if hasattr(self, 'certification_window') and self.certification_window.winfo_exists():
            self.certification_window.focus()
        else:
            self.certification_window = CertificationWindow(self.master, self.config) 
            
    def fetch_unique_data(self, column_name, default_list):
        try:
            all_raw_data = fetch_db_query(f"SELECT {column_name} FROM patients WHERE {column_name} IS NOT NULL AND {column_name} != ''")
            
            unique_items = set()
            for record in all_raw_data:
                if record and record[0]:
                    for item in record[0].split(','):
                        cleaned_item = item.strip().title()
                        if cleaned_item:
                            unique_items.add(cleaned_item)
            
            all_items = unique_items.union(set([item.title() for item in default_list]))
            
            return sorted(list(all_items))
        except Exception as e:
            print(f"Error fetching unique data from {column_name}: {e}")
            return sorted([item.title() for item in default_list])
            
    def refresh_autocomplete_lists(self):
        self.medicine_autocomplete_list = self.fetch_unique_data("medicine", self.DEFAULT_MEDICINES)
        self.disease_autocomplete_list = self.fetch_unique_data("dosage", self.DEFAULT_DISEASES) 
            
    def _create_input_widget(self, label_text, row, mandatory=False):
        ctk.CTkLabel(self.input_frame, text=label_text, font=self.label_font).grid(row=row, column=0, padx=20, sticky="w")
        entry = ctk.CTkEntry(self.input_frame, width=280)
        entry.grid(row=row + 1, column=0, padx=20, pady=(0, 8), sticky="ew") 
        return entry

    # --- CORE LOGIC: ADVANCED SEARCH IMPLEMENTATION (Unchanged) ---
    def refresh_records(self, event=None):
        global COLUMN_NAMES
        
        # Clear existing content below the manually added header
        for widget in self.record_widgets:
            widget.destroy()
        self.record_widgets = []
        
        data_start_row = 1 
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(patients)")
        COLUMN_NAMES = [col[1] for col in cursor.fetchall()]
        conn.close()
        
        all_cols = ", ".join(COLUMN_NAMES)
        
        # --- Dynamic Filtering Logic ---
        where_clauses = []
        params = []
        
        # 1. Filter by MC No
        filter_mc = self.filter_mc_entry.get().strip()
        if filter_mc and filter_mc.isdigit():
            where_clauses.append("mc = ?")
            params.append(int(filter_mc))
            
        # 2. Filter by Name
        filter_name = self.filter_name_entry.get().strip()
        if filter_name:
            where_clauses.append("name LIKE ?")
            params.append(f'%{filter_name.title()}%')

        # 3. Filter by Medicine
        filter_med = self.filter_med_entry.get().strip()
        if filter_med:
            where_clauses.append("medicine LIKE ?")
            params.append(f'%{filter_med.title()}%')

        # 4. Filter by Diagnosis/Disease
        filter_disease = self.filter_disease_entry.get().strip()
        if filter_disease:
            where_clauses.append("dosage LIKE ?")
            params.append(f'%{filter_disease.title()}%')
            
        # 5. Filter by Age Range
        filter_age_min_str = self.filter_age_min_entry.get().strip()
        filter_age_max_str = self.filter_age_max_entry.get().strip()
        
        try:
            filter_age_min = int(filter_age_min_str) if filter_age_min_str.isdigit() else 0
        except ValueError:
            filter_age_min = 0 # Default to 0 if invalid

        try:
            filter_age_max = int(filter_age_max_str) if filter_age_max_str.isdigit() else float('inf')
        except ValueError:
            filter_age_max = float('inf') # Default to infinity if invalid

        if filter_age_min > 0 or filter_age_max != float('inf'):
            if filter_age_min > 0:
                where_clauses.append("age >= ?")
                params.append(filter_age_min)
            if filter_age_max != float('inf'):
                where_clauses.append("age <= ?")
                params.append(filter_age_max)
        
        # Construct the final query
        query = f"SELECT {all_cols} FROM patients"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " ORDER BY mc DESC"
        
        records = fetch_db_query(query, tuple(params))
        expected_cols = len(COLUMN_NAMES)
        
        # --- Display Logic (Updated to use dynamic column names) ---
        
        # Find index of required columns dynamically
        try:
            mc_index = COLUMN_NAMES.index('mc')
            name_index = COLUMN_NAMES.index('name')
            age_index = COLUMN_NAMES.index('age')
            gender_index = COLUMN_NAMES.index('gender')
            medicine_index = COLUMN_NAMES.index('medicine')
            disease_index = COLUMN_NAMES.index('dosage')
            date_index = COLUMN_NAMES.index('date_created')
        except ValueError as e:
            print(f"ERROR: Database schema is missing required columns: {e}.")
            return
            
        for i, record in enumerate(records):
            
            if len(record) < expected_cols:
                record_list = list(record) + [None] * (expected_cols - len(record))
                record = tuple(record_list)
                
            try:
                # Accessing data by dynamic index
                mc_no = record[mc_index]
                name = record[name_index]
                age = record[age_index]
                gender = record[gender_index]
                medicine = record[medicine_index]
                disease = record[disease_index]
                date_created_full = record[date_index]
            except IndexError as e:
                print(f"Index Error processing record {record}: {e}")
                continue 
            
            date_only = date_created_full.split(' ')[0] if date_created_full else 'N/A'
            
            display_text = (
                f"MC: {mc_no} | Name: {name} ({age}, {gender}) | "
                f"Med: {medicine or 'N/A'} | Dx: {disease or 'N/A'} | "
                f"Date: {date_only}"
            )
            
            record_label = ctk.CTkLabel(self.listbox, text=display_text, 
                                        fg_color=("#F0F0F0", "#303030"), 
                                        text_color=("black", "white"),
                                        corner_radius=6, 
                                        wraplength=450, 
                                        padx=10, 
                                        pady=5,
                                        cursor="hand2", 
                                        anchor="w")
            record_label.grid(row=i + data_start_row, column=0, padx=5, pady=2, sticky="ew")
            
            record_label.bind("<Button-1>", lambda event, rec=record, widget=record_label: self.select_record(rec, widget))
            self.record_widgets.append(record_label)
            
            if self.selected_record_mc == mc_no:
                record_label.configure(fg_color="#008080", text_color="yellow") 

        total_records = fetch_db_query("SELECT COUNT(*) FROM patients")[0][0]
        self.record_count_label.configure(text=f"Total Records: {total_records} (Filtered: {len(records)})")


    def search_records(self, event):
        self.refresh_records()

    def select_record(self, record, clicked_widget):
        global SELECTED_RECORD_DATA
        global COLUMN_NAMES 
        
        for widget in self.record_widgets:
            widget.configure(fg_color=("#F0F0F0", "#303030"), text_color=("black", "white"))
            
        clicked_widget.configure(fg_color="#008080", text_color="yellow") 

        SELECTED_RECORD_DATA = dict(zip(COLUMN_NAMES, record))
        self.selected_record_mc = SELECTED_RECORD_DATA.get('mc')
        
        # Accessing by column name is safer after the column name change
        self.name_entry.delete(0, 'end'); self.name_entry.insert(0, SELECTED_RECORD_DATA.get('name', ''))
        self.age_entry.delete(0, 'end'); self.age_entry.insert(0, SELECTED_RECORD_DATA.get('age', ''))
        self.gender_var.set(SELECTED_RECORD_DATA.get('gender', 'Male'))
        self.medicine_entry.delete(0, 'end'); self.medicine_entry.insert(0, SELECTED_RECORD_DATA.get('medicine', ''))
        self.dosage_entry.delete(0, 'end'); self.dosage_entry.insert(0, SELECTED_RECORD_DATA.get('dosage', '')) 
        self.address_entry.delete(0, 'end'); self.address_entry.insert(0, SELECTED_RECORD_DATA.get('address', ''))
        self.phone_entry.delete(0, 'end'); self.phone_entry.insert(0, SELECTED_RECORD_DATA.get('phone', ''))
        
    def clear_fields(self):
        global SELECTED_RECORD_DATA
        self.selected_record_mc = None
        SELECTED_RECORD_DATA = {}
        
        self.name_entry.delete(0, 'end')
        self.age_entry.delete(0, 'end')
        self.gender_var.set("Male")
        self.medicine_entry.delete(0, 'end')
        self.dosage_entry.delete(0, 'end') 
        self.address_entry.delete(0, 'end')
        self.phone_entry.delete(0, 'end')
        
        self.hide_suggestion_box('medicine')
        self.hide_suggestion_box('disease')
        
        for widget in self.record_widgets:
            widget.configure(fg_color=("#F0F0F0", "#303030"), text_color=("black", "white"))
        
        messagebox.showinfo("Fields Cleared", "Input fields and selection have been reset.")
        
    def add_patient(self):
        name = self.name_entry.get(); age_str = self.age_entry.get(); medicine = self.medicine_entry.get().strip(', ')
        gender = self.gender_var.get(); disease = self.dosage_entry.get().strip(', '); address = self.address_entry.get(); phone = self.phone_entry.get()
        
        if not (name and age_str and medicine):
            messagebox.showerror("Validation Error", "Name, Age, and Medicine are required fields.")
            return
        
        try:
            age = int(age_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Age must be a valid number.")
            return
            
        execute_db_query(
            "INSERT INTO patients (name, age, gender, medicine, dosage, address, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name.strip().title(), age, gender, medicine.title(), disease.title(), address.strip(), phone.strip())
        )
        messagebox.showinfo("Success", f"Patient {name} added successfully! MC No will be assigned automatically.")
        
        self.refresh_autocomplete_lists() 
        self.clear_fields()
        self.refresh_records()

    def update_patient(self):
        if self.selected_record_mc is None:
            messagebox.showwarning("Warning", "Please select a record to update first by clicking on it in the list.")
            return
            
        name = self.name_entry.get(); age_str = self.age_entry.get(); medicine = self.medicine_entry.get().strip(', ')
        gender = self.gender_var.get(); disease = self.dosage_entry.get().strip(', '); address = self.address_entry.get(); phone = self.phone_entry.get()

        if not (name and age_str and medicine):
            messagebox.showerror("Validation Error", "Name, Age, and Medicine are required fields.")
            return
        try:
            age = int(age_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Age must be a valid number.")
            return
            
        execute_db_query(
            """UPDATE patients SET name=?, age=?, gender=?, medicine=?, dosage=?, address=?, phone=? WHERE mc=?""",
            (name.strip().title(), age, gender, medicine.title(), disease.title(), address.strip(), phone.strip(), self.selected_record_mc)
        )
        messagebox.showinfo("Success", f"Record MC No {self.selected_record_mc} updated successfully!")
        
        self.refresh_autocomplete_lists() 
        self.clear_fields()
        self.refresh_records()

    def delete_patient(self):
        if self.selected_record_mc is None:
            messagebox.showwarning("Warning", "Please select a record to delete first by clicking on it in the list.")
            return
            
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete Record MC No {self.selected_record_mc}?"):
            execute_db_query("DELETE FROM patients WHERE mc=?", (self.selected_record_mc,)) 
            messagebox.showinfo("Success", "Record deleted successfully!")
            
            self.refresh_autocomplete_lists() 
            self.clear_fields() 
            
            initialize_db()
            self.refresh_records()

    def export_to_csv(self):
        records = fetch_db_query("SELECT mc, name, age, gender, medicine, dosage, address, phone, date_created FROM patients")
        if not records:
            messagebox.showwarning("Export Failed", "No records found to export.")
            return
            
        csv_column_names = ["mc", "name", "age", "gender", "medicine", "disease", "address", "phone", "date_created"]

        df = pd.DataFrame(records, columns=csv_column_names)
        file_path = "pharmaflow_data_export_full.csv"
        df.to_csv(file_path, index=False)
        # Save the backup timestamp to config
        import datetime
        self.config['last_backup'] = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        with open('config.json', 'w') as f:
            import json
            json.dump(self.config, f, indent=4)
        messagebox.showinfo("Export Successful", f"All data exported successfully to:\n{os.path.abspath(file_path)}")

    def print_selected_record(self):
        if self.selected_record_mc is None:
            messagebox.showwarning("Warning", "Please select a patient record to print first by clicking on it in the list.")
            return
            
        try:
            html_content = generate_html_prescription(SELECTED_RECORD_DATA, self.config) 
            
            temp_file_path = "temp_prescription.html"
            with open(temp_file_path, "w") as f:
                f.write(html_content)
            
            webbrowser.open_new_tab(os.path.abspath(temp_file_path))
            
            messagebox.showinfo(
                "Print Initiated", 
                "The prescription slip has been opened in a new browser tab, and printing has been automatically started."
            )

        except Exception as e:
            messagebox.showerror("Print Error", f"An error occurred during print preparation: {e}")


# --- 6. Main Execution ---

if __name__ == "__main__":
    app = PharmaFlowApp()
    app.mainloop()