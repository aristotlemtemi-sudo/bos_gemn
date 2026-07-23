import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'bos-dev-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///bos.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    DEFAULT_CURRENCY = 'TZS'
    DEFAULT_TIMEZONE = 'UTC+3'
    
    # =========================================================================
    # NEW: Push Notification Settings (Web Push for real device notifications)
    # =========================================================================
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY') or ''
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY') or ''
    VAPID_CLAIMS_EMAIL = os.environ.get('VAPID_CLAIMS_EMAIL') or 'admin@bosgemn.com'
    
    # =========================================================================
    # NEW: Bankroll Alert Defaults (user can override in settings)
    # =========================================================================
    DEFAULT_BANKROLL_RED_MARGIN = 5.0      # % below deposits = CRITICAL alert
    DEFAULT_BANKROLL_YELLOW_MARGIN = 10.0  # % below deposits = WARNING alert
    
    # =========================================================================
    # NEW: PDF Export Settings
    # =========================================================================
    PDF_PAGE_SIZE = 'A4'
    PDF_CURRENCY_SYMBOL = 'TZS'
    PDF_COMPANY_NAME = 'BOS GEMN'
    PDF_REPORT_TITLE = 'BETTING OVERSIGHT SYSTEM'
    
    # =========================================================================
    # NEW: Dashboard / UI Defaults
    # =========================================================================
    DEFAULT_THEME = 'dark'
    DEFAULT_ITEMS_PER_PAGE = 25
    DASHBOARD_REFRESH_INTERVAL = 30  # seconds (auto-refresh stats)
    
    # =========================================================================
    # NEW: Slip Settings
    # =========================================================================
    SLIP_NUMBER_PREFIX = 'SLIP'
    SLIP_AUTO_NUMBER = True  # Auto-generate slip numbers (SLIP-001, SLIP-002...)
    
    # =========================================================================
    # NEW: Bookmaker Settings
    # =========================================================================
    ALLOW_MANUAL_BOOKMAKER_ENTRY = True  # User adds their own bookmakers
    TRACK_BOOKMAKER_BALANCE = True       # Auto-update balance from deposits/slips