from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


# ============================================================================
# NEW: User Model (for multi-user support & push notifications)
# ============================================================================
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    settings = db.relationship('UserSettings', backref='user', uselist=False, lazy=True)
    bookmakers = db.relationship('Bookmaker', backref='user', lazy=True)
    slips = db.relationship('BetSlip', backref='user', lazy=True)
    notifications = db.relationship('NotificationLog', backref='user', lazy=True)
    push_subscriptions = db.relationship('PushSubscription', backref='user', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# NEW: Push Subscription (for real Web Push notifications to device)
# ============================================================================
class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'endpoint': self.endpoint,
            'p256dh': self.p256dh,
            'auth': self.auth,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# MODIFIED: BetSlip — Slip #/Name focus, multiple matches per slip
# ============================================================================
class BetSlip(db.Model):
    __tablename__ = 'bet_slips'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    
    # SLIP IDENTITY (primary focus — NOT match title)
    slip_name = db.Column(db.String(200), nullable=False, default='Untitled Slip')
    slip_number = db.Column(db.String(50), nullable=False, default='SLIP-001')
    
    # MULTIPLE MATCHES per slip (stored as JSON array)
    # Example: [{"event":"Man Utd vs Liverpool","selection":"Over 2.5","odds":1.85},
    #           {"event":"Chelsea vs Arsenal","selection":"Home Win","odds":2.10}]
    matches = db.Column(db.Text, default='[]')
    
    # Keep single-match fields for backward compatibility / simple slips
    home_team = db.Column(db.String(100), default='')
    away_team = db.Column(db.String(100), default='')
    league = db.Column(db.String(100), default='')
    country = db.Column(db.String(100), default='')
    sport = db.Column(db.String(50), default='Football')
    market = db.Column(db.String(100), default='')
    prediction = db.Column(db.String(200), default='')
    
    # Odds & Stake
    odds = db.Column(db.Float, default=1.0)           # Combined odds (auto-calculated)
    stake = db.Column(db.Float, nullable=False)       # Total stake for entire slip
    potential_return = db.Column(db.Float, default=0.0)
    profit_loss = db.Column(db.Float, default=0.0)
    return_amount = db.Column(db.Float, default=0.0)  # Actual amount returned
    
    # Status: pending, won, lost, void, cashed, partial
    status = db.Column(db.String(20), default='pending')
    
    # Bookmaker link
    bookmaker_id = db.Column(db.Integer, db.ForeignKey('bookmakers.id'), nullable=True)
    bookmaker_name = db.Column(db.String(100), default='')
    
    # Meta
    confidence = db.Column(db.Integer, default=3)
    reasoning = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')
    screenshot_path = db.Column(db.String(255), default='')
    screenshot_name = db.Column(db.String(200), default='')
    raw_text = db.Column(db.Text, default='')
    strategy_tag = db.Column(db.String(100), default='')
    
    # FOLLOW UP (settled bet review)
    # Example: {"matchIndex": 2, "event": "Chelsea vs Arsenal", "selection": "Home Win"}
    lost_matches = db.Column(db.Text, default='[]')           # JSON list of matches that caused the loss
    # Example: {"x": 42.5, "y": 31.2, "size": 4.0}  (percentages of the screenshot dimensions)
    screenshot_annotations = db.Column(db.Text, default='[]')  # JSON list of X marks placed on the screenshot
    follow_up_notes = db.Column(db.Text, default='')           # comments about what went wrong / lost teams
    
    # Timestamps
    match_datetime = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True)

    def get_matches(self):
        """Parse matches JSON to Python list."""
        try:
            return json.loads(self.matches) if self.matches else []
        except:
            return []
    
    def set_matches(self, matches_list):
        """Store matches list as JSON."""
        self.matches = json.dumps(matches_list)
    
    def calculate_combined_odds(self):
        """Auto-calculate combined odds from all matches."""
        matches = self.get_matches()
        if not matches:
            return self.odds or 1.0
        combined = 1.0
        for m in matches:
            combined *= float(m.get('odds', 1.0))
        return round(combined, 2)
    
    def get_match_count(self):
        """Return number of matches in this slip."""
        return len(self.get_matches())

    def get_lost_matches(self):
        """Parse lost matches JSON to Python list."""
        try:
            return json.loads(self.lost_matches) if self.lost_matches else []
        except Exception:
            return []

    def set_lost_matches(self, lost_list):
        """Store lost matches list as JSON."""
        self.lost_matches = json.dumps(lost_list)

    def get_screenshot_annotations(self):
        """Parse screenshot annotation marks to Python list."""
        try:
            return json.loads(self.screenshot_annotations) if self.screenshot_annotations else []
        except Exception:
            return []

    def set_screenshot_annotations(self, annotations):
        """Store screenshot annotations as JSON."""
        self.screenshot_annotations = json.dumps(annotations)

    def to_dict(self):
        matches = self.get_matches()
        effective_odds = self.calculate_combined_odds() if matches else (self.odds or 1.0)
        return {
            'id': self.id,
            'user_id': self.user_id,
            'slip_name': self.slip_name,
            'slip_number': self.slip_number,
            'matches': matches,
            'match_count': len(matches),
            'home_team': self.home_team,
            'away_team': self.away_team,
            'match': f"{self.home_team} vs {self.away_team}" if self.home_team and self.away_team else '',
            'league': self.league,
            'country': self.country,
            'sport': self.sport,
            'market': self.market,
            'prediction': self.prediction,
            'odds': effective_odds,
            'stake': self.stake,
            'potential_return': round(self.stake * effective_odds, 2),
            'profit_loss': self.profit_loss,
            'return_amount': self.return_amount,
            'status': self.status,
            'bookmaker_id': self.bookmaker_id,
            'bookmaker_name': self.bookmaker_name,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'notes': self.notes,
            'screenshot_path': self.screenshot_path,
            'screenshot_name': self.screenshot_name,
            'raw_text': self.raw_text,
            'strategy_tag': self.strategy_tag,
            'lost_matches': self.get_lost_matches(),
            'screenshot_annotations': self.get_screenshot_annotations(),
            'follow_up_notes': self.follow_up_notes,
            'match_datetime': self.match_datetime.isoformat() if self.match_datetime else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None
        }


# ============================================================================
# MODIFIED: Bookmaker — Manual entry, balance tracking, user-scoped
# ============================================================================
class Bookmaker(db.Model):
    __tablename__ = 'bookmakers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    
    name = db.Column(db.String(100), nullable=False)
    website = db.Column(db.String(255), default='')
    
    # BALANCE TRACKING (user fills manually, auto-updates from slips)
    balance = db.Column(db.Float, default=0.0)          # Current available balance
    total_deposited = db.Column(db.Float, default=0.0)  # All deposits ever made
    total_withdrawn = db.Column(db.Float, default=0.0)  # All withdrawals

    # COMPANY DETAILS (manual entry)
    contact_person = db.Column(db.String(100), default='')
    phone = db.Column(db.String(50), default='')
    email = db.Column(db.String(120), default='')
    address = db.Column(db.String(255), default='')
    notes = db.Column(db.Text, default='')
    
    # PERFORMANCE STATS
    total_bets = db.Column(db.Integer, default=0)
    total_wins = db.Column(db.Integer, default=0)
    total_losses = db.Column(db.Integer, default=0)
    total_profit = db.Column(db.Float, default=0.0)
    roi = db.Column(db.Float, default=0.0)
    
    status = db.Column(db.String(20), default='active')  # active, inactive, suspended
    currency = db.Column(db.String(10), default='TZS')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    slips = db.relationship('BetSlip', backref='bookmaker', lazy=True)
    transactions = db.relationship('BankrollTransaction', backref='bookmaker', lazy=True)

    def update_balance_from_slip(self, slip):
        """Auto-update balance when a slip is placed or settled."""
        if slip.status == 'pending':
            # Deduct stake when placed
            self.balance -= slip.stake
        elif slip.status == 'won':
            # Add return when won
            self.balance += slip.return_amount
            self.total_wins += 1
        elif slip.status == 'lost':
            # Already deducted when placed, nothing to add
            self.total_losses += 1
        elif slip.status == 'void':
            # Return stake
            self.balance += slip.stake
        elif slip.status == 'cashed':
            # Add cashout amount
            self.balance += slip.return_amount
            
        self.total_bets += 1
        self.total_profit = self.balance - self.total_deposited + self.total_withdrawn
        self.roi = (self.total_profit / self.total_deposited * 100) if self.total_deposited > 0 else 0
        db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'website': self.website,
            'balance': self.balance,
            'total_deposited': self.total_deposited,
            'total_withdrawn': self.total_withdrawn,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'notes': self.notes,
            'net_position': round(self.balance - self.total_deposited + self.total_withdrawn, 2),
            'total_bets': self.total_bets,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_profit': self.total_profit,
            'roi': round(self.roi, 2),
            'status': self.status,
            'currency': self.currency,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# MODIFIED: BankrollTransaction — Tracks all money movements
# ============================================================================
class BankrollTransaction(db.Model):
    __tablename__ = 'bankroll_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    
    type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, slip_stake, slip_win, slip_loss, slip_void, cashout
    amount = db.Column(db.Float, nullable=False)
    
    bookmaker_id = db.Column(db.Integer, db.ForeignKey('bookmakers.id'), nullable=True)
    bookmaker_name = db.Column(db.String(100), default='')
    slip_id = db.Column(db.Integer, db.ForeignKey('bet_slips.id'), nullable=True)
    slip_number = db.Column(db.String(50), default='')
    
    description = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'amount': self.amount,
            'bookmaker_id': self.bookmaker_id,
            'bookmaker_name': self.bookmaker_name,
            'slip_id': self.slip_id,
            'slip_number': self.slip_number,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# NEW: BankrollHistory — Daily snapshots for growth graph
# ============================================================================
class BankrollHistory(db.Model):
    __tablename__ = 'bankroll_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    
    date = db.Column(db.Date, nullable=False)
    total_balance = db.Column(db.Float, default=0.0)      # Sum of all bookmaker balances
    total_deposited = db.Column(db.Float, default=0.0)    # Sum of all deposits
    total_withdrawn = db.Column(db.Float, default=0.0)
    net_profit = db.Column(db.Float, default=0.0)         # balance - deposited + withdrawn
    roi = db.Column(db.Float, default=0.0)
    at_stake = db.Column(db.Float, default=0.0)           # Pending stakes
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'date': self.date.isoformat() if self.date else None,
            'total_balance': self.total_balance,
            'total_deposited': self.total_deposited,
            'total_withdrawn': self.total_withdrawn,
            'net_profit': self.net_profit,
            'roi': self.roi,
            'at_stake': self.at_stake,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================================
# MODIFIED: UserSettings — Added bankroll_yellow_margin, push notifications
# ============================================================================
class UserSettings(db.Model):
    __tablename__ = 'user_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    
    display_name = db.Column(db.String(100), default='')
    email = db.Column(db.String(120), default='')
    currency = db.Column(db.String(10), default='TZS')
    timezone = db.Column(db.String(50), default='UTC+3')
    
    # THEME
    theme = db.Column(db.String(20), default='dark')  # dark, light, auto
    
    # NOTIFICATIONS
    bet_result_alerts = db.Column(db.Boolean, default=True)
    daily_summary = db.Column(db.Boolean, default=True)
    bankroll_alerts = db.Column(db.Boolean, default=True)
    push_notifications = db.Column(db.Boolean, default=False)  # Web Push to device
    
    # BANKROLL MARGINS (both configurable in settings)
    bankroll_red_margin = db.Column(db.Float, default=5.0)      # % — CRITICAL alert
    bankroll_yellow_margin = db.Column(db.Float, default=10.0)  # % — WARNING alert

    # MANUAL BANKROLL SUMMARY (used by bankroll page)
    manual_total_balance = db.Column(db.Float, default=0.0)
    manual_total_deposited = db.Column(db.Float, default=0.0)
    
    # UI
    accent_color = db.Column(db.String(20), default='blue')
    sidebar_collapsed = db.Column(db.Boolean, default=False)
    items_per_page = db.Column(db.Integer, default=25)
    
    # PDF
    pdf_currency = db.Column(db.String(10), default='TZS')
    pdf_company_name = db.Column(db.String(100), default='BOS GEMN')
    
    bio = db.Column(db.Text, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'display_name': self.display_name,
            'email': self.email,
            'currency': self.currency,
            'timezone': self.timezone,
            'theme': self.theme,
            'accent_color': self.accent_color,
            'sidebar_collapsed': self.sidebar_collapsed,
            'bet_result_alerts': self.bet_result_alerts,
            'daily_summary': self.daily_summary,
            'bankroll_alerts': self.bankroll_alerts,
            'push_notifications': self.push_notifications,
            'bankroll_red_margin': self.bankroll_red_margin,
            'bankroll_yellow_margin': self.bankroll_yellow_margin,
            'manual_total_balance': self.manual_total_balance,
            'manual_total_deposited': self.manual_total_deposited,
            'items_per_page': self.items_per_page,
            'pdf_currency': self.pdf_currency,
            'pdf_company_name': self.pdf_company_name,
            'bio': self.bio
        }


# ============================================================================
# MODIFIED: NotificationLog — User-scoped, supports push delivery
# ============================================================================
class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info')  # info, success, warning, danger
    is_read = db.Column(db.Boolean, default=False)
    pushed = db.Column(db.Boolean, default=False)  # Whether sent via Web Push
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'pushed': self.pushed,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }