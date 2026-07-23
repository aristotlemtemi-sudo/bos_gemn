from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
import io

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from config import Config
from models import db, User, BetSlip, Bookmaker, BankrollTransaction, BankrollHistory, UserSettings, NotificationLog, PushSubscription

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.context_processor
def inject_globals():
    return dict(vapid_public_key=app.config.get('VAPID_PUBLIC_KEY', ''))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_or_create_default_user():
    user = User.query.first()
    if not user:
        user = User(username='admin', email='admin@bosgemn.com', password_hash='default_hash')
        db.session.add(user)
        db.session.commit()
    return user


def get_or_create_settings():
    user = get_or_create_default_user()
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.session.add(settings)
        db.session.commit()
    return settings


def get_or_create_bookmaker(name):
    if not name:
        name = 'General Bookmaker'
    user = get_or_create_default_user()
    bm = Bookmaker.query.filter_by(name=name).first()
    if not bm:
        bm = Bookmaker(user_id=user.id, name=name)
        db.session.add(bm)
        db.session.commit()
    return bm


def create_notification(title, message, type='info'):
    user = get_or_create_default_user()
    notif = NotificationLog(user_id=user.id, title=title, message=message, type=type)
    db.session.add(notif)
    db.session.commit()
    return notif


def check_bankroll_alerts():
    settings = get_or_create_settings()
    if not settings.bankroll_alerts:
        return

    total_deposited = db.session.query(db.func.sum(Bookmaker.total_deposited)).scalar() or 0
    total_balance = db.session.query(db.func.sum(Bookmaker.balance)).scalar() or 0
    at_stake = db.session.query(db.func.sum(BetSlip.stake)).filter(BetSlip.status == 'pending').scalar() or 0

    if total_deposited > 0:
        available_pct = ((total_balance - at_stake) / total_deposited) * 100
        if available_pct < settings.bankroll_red_margin:
            create_notification(
                'Bankroll Alert',
                f'Your available bankroll is {available_pct:.1f}% of deposits. Below {settings.bankroll_red_margin}% red margin!',
                'warning'
            )


# ============ HTML ROUTES ============

@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/slips')
def slips():
    return render_template('slips.html')


@app.route('/analytics')
def analytics():
    return render_template('analytics.html')


@app.route('/reports')
def reports():
    return render_template('reports.html')


@app.route('/bankroll')
def bankroll():
    return render_template('bankroll.html')


@app.route('/bookmakers')
def bookmakers():
    return render_template('bookmakers.html')


@app.route('/settings')
def settings():
    return render_template('settings.html')


# ============ API ROUTES ============

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    notifs = NotificationLog.query.order_by(NotificationLog.created_at.desc()).limit(20).all()
    return jsonify([n.to_dict() for n in notifs])


@app.route('/api/notifications/<int:id>/read', methods=['PUT'])
def mark_notification_read(id):
    notif = NotificationLog.query.get_or_404(id)
    notif.is_read = True
    db.session.commit()
    return jsonify(notif.to_dict())


@app.route('/api/dashboard/stats')
def dashboard_stats():
    total_slips = BetSlip.query.count()
    won_slips = BetSlip.query.filter_by(status='won').count()
    lost_slips = BetSlip.query.filter_by(status='lost').count()
    pending_slips = BetSlip.query.filter_by(status='pending').count()

    total_staked = db.session.query(db.func.sum(BetSlip.stake)).scalar() or 0
    total_profit = db.session.query(db.func.sum(BetSlip.profit_loss)).scalar() or 0

    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    today_slips = BetSlip.query.filter(BetSlip.created_at >= today_start, BetSlip.created_at <= today_end).all()
    today_profit = sum(s.profit_loss for s in today_slips if s.status != 'pending')
    today_bets = len(today_slips)

    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
    strike_rate = (won_slips / (won_slips + lost_slips) * 100) if (won_slips + lost_slips) > 0 else 0

    total_balance = db.session.query(db.func.sum(Bookmaker.balance)).scalar() or 0
    total_deposited = db.session.query(db.func.sum(Bookmaker.total_deposited)).scalar() or 0
    bookmaker_count = Bookmaker.query.count()
    at_stake = db.session.query(db.func.sum(BetSlip.stake)).filter(BetSlip.status == 'pending').scalar() or 0

    recent_slips = BetSlip.query.filter(BetSlip.status.in_(['won', 'lost'])).order_by(BetSlip.settled_at.desc()).limit(10).all()
    streak = 0
    streak_type = None
    for slip in recent_slips:
        if streak_type is None:
            streak_type = slip.status
            streak = 1
        elif slip.status == streak_type:
            streak += 1
        else:
            break

    avg_odds = db.session.query(db.func.avg(BetSlip.odds)).scalar() or 0
    avg_stake = db.session.query(db.func.avg(BetSlip.stake)).scalar() or 0

    settings = get_or_create_settings()
    margin_alert = None
    if total_deposited > 0:
        available_pct = ((total_balance - at_stake) / total_deposited) * 100
        if available_pct < settings.bankroll_red_margin:
            margin_alert = 'red'
        elif available_pct < settings.bankroll_yellow_margin:
            margin_alert = 'yellow'

    return jsonify({
        'total_bankroll': round(total_balance, 2),
        'total_deposited': round(total_deposited, 2),
        'bookmaker_count': bookmaker_count,
        'today_profit': round(today_profit, 2),
        'today_bets': today_bets,
        'roi': round(roi, 1),
        'strike_rate': round(strike_rate, 1),
        'pending_bets': pending_slips,
        'pending_stake': round(at_stake, 2),
        'streak': streak,
        'streak_type': streak_type,
        'total_bets': total_slips,
        'total_wins': won_slips,
        'total_losses': lost_slips,
        'avg_odds': round(avg_odds, 2),
        'avg_stake': round(avg_stake, 2),
        'total_profit': round(total_profit, 2),
        'margin_alert': margin_alert,
        'red_margin': settings.bankroll_red_margin,
        'yellow_margin': settings.bankroll_yellow_margin,
        'red_margin_pct': settings.bankroll_red_margin,
        'yellow_margin_pct': settings.bankroll_yellow_margin
    })


@app.route('/api/dashboard/profit-chart')
def profit_chart():
    days = int(request.args.get('days', 7))
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)

    labels = []
    daily_data = []
    profit_data = []
    loss_data = []
    cumulative_list = []
    cumulative = 0

    for i in range(days):
        date = start_date + timedelta(days=i)
        date_start = datetime.combine(date.date(), datetime.min.time())
        date_end = datetime.combine(date.date(), datetime.max.time())

        day_slips = BetSlip.query.filter(
            BetSlip.settled_at >= date_start,
            BetSlip.settled_at <= date_end,
            BetSlip.status.in_(['won', 'lost', 'cashed', 'void'])
        ).all()

        day_profit = sum(s.profit_loss for s in day_slips)
        cumulative += day_profit

        labels.append(date.strftime('%a' if days <= 7 else '%d %b'))
        daily_data.append(round(day_profit, 2))
        profit_data.append(round(cumulative, 2) if cumulative >= 0 else 0)
        loss_data.append(round(cumulative, 2) if cumulative < 0 else 0)
        cumulative_list.append(round(cumulative, 2))

    return jsonify({
        'labels': labels,
        'daily_data': daily_data,
        'data': daily_data,
        'profit_data': profit_data,
        'loss_data': loss_data,
        'cumulative': cumulative_list
    })


@app.route('/api/slips', methods=['GET'])
def get_slips():
    status = request.args.get('status')
    sport = request.args.get('sport')
    search = request.args.get('search', '')

    query = BetSlip.query

    if status and status != 'all':
        query = query.filter_by(status=status)
    if sport and sport != 'all':
        query = query.filter_by(sport=sport)
    if search:
        search_filter = db.or_(
            BetSlip.slip_name.ilike(f'%{search}%'),
            BetSlip.slip_number.ilike(f'%{search}%'),
            BetSlip.home_team.ilike(f'%{search}%'),
            BetSlip.away_team.ilike(f'%{search}%'),
            BetSlip.league.ilike(f'%{search}%'),
            BetSlip.bookmaker_name.ilike(f'%{search}%')
        )
        query = query.filter(search_filter)

    slips = query.order_by(BetSlip.created_at.desc()).all()
    return jsonify([s.to_dict() for s in slips])


@app.route('/api/slips', methods=['POST'])
def create_slip():
    data = request.form.to_dict() if request.form else (request.get_json() or {})

    screenshot_path = ''
    if 'screenshot' in request.files:
        file = request.files['screenshot']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"slip_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            screenshot_path = f'/static/uploads/{filename}'

    raw_datetime = data.get('match_datetime')
    if raw_datetime:
        try:
            match_datetime = datetime.fromisoformat(raw_datetime)
        except Exception:
            match_datetime = datetime.now()
    else:
        match_datetime = datetime.now()

    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None and val != '' else default
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        try:
            return int(val) if val is not None and val != '' else default
        except (ValueError, TypeError):
            return default

    matches_raw = data.get('matches')
    matches_list = []
    if matches_raw:
        if isinstance(matches_raw, str):
            try:
                matches_list = json.loads(matches_raw)
            except Exception:
                matches_list = []
        elif isinstance(matches_raw, list):
            matches_list = matches_raw

    odds_val = safe_float(data.get('odds'), 1.0)
    if matches_list and odds_val == 1.0:
        combined = 1.0
        for m in matches_list:
            combined *= safe_float(m.get('odds'), 1.0)
        odds_val = round(combined, 2)

    user = get_or_create_default_user()

    slip = BetSlip(
        user_id=user.id,
        slip_name=data.get('slip_name', 'Slip #1') or 'Slip #1',
        slip_number=data.get('slip_number', f"SLIP-{BetSlip.query.count() + 1:03d}") or f"SLIP-{BetSlip.query.count() + 1:03d}",
        home_team=data.get('home_team', '') or '',
        away_team=data.get('away_team', '') or '',
        league=data.get('league', '') or '',
        country=data.get('country', '') or '',
        sport=data.get('sport', 'Football') or 'Football',
        market=data.get('market', '') or '',
        prediction=data.get('prediction', '') or '',
        odds=odds_val,
        stake=safe_float(data.get('stake'), 0.0),
        status=data.get('status', 'pending') or 'pending',
        bookmaker_name=data.get('bookmaker', '') or '',
        confidence=safe_int(data.get('confidence'), 3),
        reasoning=data.get('reasoning', '') or '',
        notes=data.get('notes', '') or '',
        screenshot_path=screenshot_path,
        strategy_tag=data.get('strategy_tag', '') or '',
        match_datetime=match_datetime
    )

    if matches_list:
        slip.set_matches(matches_list)

    if slip.bookmaker_name:
        bm = get_or_create_bookmaker(slip.bookmaker_name)
        slip.bookmaker_id = bm.id

    slip.potential_return = round(slip.stake * slip.odds, 2)

    if slip.status == 'won':
        slip.profit_loss = slip.potential_return - slip.stake
        slip.settled_at = datetime.now()
        slip.return_amount = slip.potential_return
    elif slip.status == 'lost':
        slip.profit_loss = -slip.stake
        slip.settled_at = datetime.now()
        slip.return_amount = 0.0
    elif slip.status == 'cashed':
        cashout_value = safe_float(data.get('cashout_value'), slip.potential_return * 0.7)
        slip.profit_loss = cashout_value - slip.stake
        slip.settled_at = datetime.now()
        slip.return_amount = cashout_value

    db.session.add(slip)
    db.session.commit()

    if slip.bookmaker_id:
        update_bookmaker_stats(slip.bookmaker_id)

    check_bankroll_alerts()

    return jsonify(slip.to_dict()), 201


@app.route('/api/slips/<int:id>', methods=['PUT'])
def update_slip(id):
    slip = BetSlip.query.get_or_404(id)
    data = request.get_json() or {}

    old_status = slip.status

    for key, value in data.items():
        if hasattr(slip, key) and key != 'id':
            setattr(slip, key, value)

    slip.potential_return = round(slip.stake * slip.odds, 2)

    if 'status' in data and data['status'] != old_status:
        if slip.status == 'won':
            slip.profit_loss = slip.potential_return - slip.stake
            slip.settled_at = datetime.now()
            slip.return_amount = slip.potential_return
        elif slip.status == 'lost':
            slip.profit_loss = -slip.stake
            slip.settled_at = datetime.now()
            slip.return_amount = 0.0
        elif slip.status == 'cashed':
            cashout_val = float(data.get('cashout_value', slip.potential_return * 0.7))
            slip.profit_loss = cashout_val - slip.stake
            slip.settled_at = datetime.now()
            slip.return_amount = cashout_val
        elif slip.status in ('pending', 'void'):
            slip.profit_loss = 0.0
            slip.settled_at = None if slip.status == 'pending' else datetime.now()
            slip.return_amount = slip.stake if slip.status == 'void' else 0.0

    db.session.commit()

    if slip.bookmaker_id:
        update_bookmaker_stats(slip.bookmaker_id)

    check_bankroll_alerts()

    return jsonify(slip.to_dict())


@app.route('/api/slips/<int:id>', methods=['DELETE'])
def delete_slip(id):
    slip = BetSlip.query.get_or_404(id)
    bm_id = slip.bookmaker_id
    db.session.delete(slip)
    db.session.commit()

    if bm_id:
        update_bookmaker_stats(bm_id)

    return jsonify({'message': 'Slip deleted'})


def update_bookmaker_stats(bookmaker_id):
    bm = Bookmaker.query.get(bookmaker_id)
    if not bm:
        return

    slips = BetSlip.query.filter_by(bookmaker_id=bookmaker_id).all()
    bm.total_bets = len(slips)
    bm.total_wins = len([s for s in slips if s.status == 'won'])
    bm.total_losses = len([s for s in slips if s.status == 'lost'])
    bm.total_profit = sum(s.profit_loss for s in slips)

    total_staked = sum(s.stake for s in slips)
    bm.roi = (bm.total_profit / total_staked * 100) if total_staked > 0 else 0

    # Keep balance and original deposit as manual values entered by the user.
    # Slip outcomes only update the bet stats, not overwrite the bankroll fields.
    if bm.total_deposited is None:
        bm.total_deposited = 0.0
    if bm.balance is None:
        bm.balance = 0.0

    db.session.commit()


@app.route('/api/analytics/by-sport')
def analytics_by_sport():
    sports = db.session.query(BetSlip.sport).distinct().all()
    result = []
    for (sport,) in sports:
        slips = BetSlip.query.filter_by(sport=sport).all()
        total_staked = sum(s.stake for s in slips)
        total_profit = sum(s.profit_loss for s in slips)
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        result.append({
            'name': sport or 'Other',
            'roi': round(roi, 1),
            'profit': round(total_profit, 2),
            'bets': len(slips),
            'wins': len([s for s in slips if s.status == 'won'])
        })
    return jsonify(sorted(result, key=lambda x: x['roi'], reverse=True))


@app.route('/api/analytics/by-market')
def analytics_by_market():
    markets = db.session.query(BetSlip.market).distinct().all()
    result = []
    for (market,) in markets:
        slips = BetSlip.query.filter_by(market=market).all()
        total_staked = sum(s.stake for s in slips)
        total_profit = sum(s.profit_loss for s in slips)
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        result.append({
            'name': market or 'General',
            'roi': round(roi, 1),
            'profit': round(total_profit, 2),
            'bets': len(slips)
        })
    return jsonify(sorted(result, key=lambda x: x['roi'], reverse=True))


@app.route('/api/analytics/by-bookmaker')
def analytics_by_bookmaker():
    bookmakers = Bookmaker.query.all()
    return jsonify([{
        'name': bm.name,
        'roi': round(bm.roi, 1),
        'profit': round(bm.total_profit, 2),
        'bets': bm.total_bets,
        'wins': bm.total_wins
    } for bm in bookmakers])


@app.route('/api/analytics/by-odds-range')
def analytics_by_odds():
    ranges = [
        ('1.01 - 1.50', 1.01, 1.50),
        ('1.51 - 2.00', 1.51, 2.00),
        ('2.01 - 3.00', 2.01, 3.00),
        ('3.01+', 3.01, 999)
    ]
    result = []
    for name, low, high in ranges:
        slips = BetSlip.query.filter(BetSlip.odds >= low, BetSlip.odds < high).all()
        total_staked = sum(s.stake for s in slips)
        total_profit = sum(s.profit_loss for s in slips)
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        result.append({
            'name': name,
            'roi': round(roi, 1),
            'profit': round(total_profit, 2),
            'bets': len(slips)
        })
    return jsonify(result)


@app.route('/api/analytics/by-strategy')
def analytics_by_strategy():
    strategies = db.session.query(BetSlip.strategy_tag).filter(BetSlip.strategy_tag != '').distinct().all()
    result = []
    for (strategy,) in strategies:
        slips = BetSlip.query.filter_by(strategy_tag=strategy).all()
        total_staked = sum(s.stake for s in slips)
        total_profit = sum(s.profit_loss for s in slips)
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        result.append({
            'name': strategy,
            'roi': round(roi, 1),
            'profit': round(total_profit, 2),
            'bets': len(slips)
        })
    return jsonify(sorted(result, key=lambda x: x['roi'], reverse=True))


@app.route('/api/analytics/monthly')
def analytics_monthly():
    months = []
    profits = []
    now = datetime.now()

    for i in range(5, -1, -1):
        # Calculate month date ranges accurately
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1

        month_start = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            next_month_start = datetime(year, month + 1, 1, 0, 0, 0)
        month_end = next_month_start - timedelta(seconds=1)

        slips = BetSlip.query.filter(
            BetSlip.settled_at >= month_start,
            BetSlip.settled_at <= month_end
        ).all()

        profit = sum(s.profit_loss for s in slips)
        months.append(month_start.strftime('%b'))
        profits.append(round(profit, 2))

    return jsonify({'labels': months, 'data': profits})


@app.route('/api/bookmakers', methods=['GET'])
def get_bookmakers():
    bookmakers = Bookmaker.query.all()
    return jsonify([bm.to_dict() for bm in bookmakers])


@app.route('/api/bookmakers', methods=['POST'])
def create_bookmaker():
    data = request.get_json() or {}
    user = get_or_create_default_user()
    bm = Bookmaker(
        user_id=user.id,
        name=data.get('name', 'Bookmaker') or 'Bookmaker',
        website=data.get('website', '') or '',
        balance=float(data.get('balance', 0) or 0),
        total_deposited=float(data.get('total_deposited', 0) or 0),
        contact_person=data.get('contact_person', '') or '',
        phone=data.get('phone', '') or '',
        email=data.get('email', '') or '',
        address=data.get('address', '') or '',
        notes=data.get('notes', '') or '',
        currency=data.get('currency', 'TZS') or 'TZS',
        status=data.get('status', 'active') or 'active'
    )
    db.session.add(bm)
    db.session.commit()
    return jsonify(bm.to_dict()), 201


@app.route('/api/bookmakers/<int:id>', methods=['PUT'])
def update_bookmaker(id):
    bm = Bookmaker.query.get_or_404(id)
    data = request.get_json() or {}
    for key, value in data.items():
        if hasattr(bm, key):
            if key in {'balance', 'total_deposited', 'total_withdrawn', 'total_profit', 'roi'}:
                try:
                    setattr(bm, key, float(value))
                except (TypeError, ValueError):
                    setattr(bm, key, value)
            else:
                setattr(bm, key, value)
    db.session.commit()
    return jsonify(bm.to_dict())


@app.route('/api/bankroll/manual-summary', methods=['GET'])
def manual_bankroll_summary():
    settings = get_or_create_settings()
    return jsonify({
        'manual_total_balance': round(settings.manual_total_balance, 2),
        'manual_total_deposited': round(settings.manual_total_deposited, 2)
    })


@app.route('/api/bankroll/manual-summary', methods=['PUT'])
def update_manual_bankroll_summary():
    settings = get_or_create_settings()
    data = request.get_json() or {}
    settings.manual_total_balance = float(data.get('manual_total_balance', settings.manual_total_balance) or settings.manual_total_balance)
    settings.manual_total_deposited = float(data.get('manual_total_deposited', settings.manual_total_deposited) or settings.manual_total_deposited)
    db.session.commit()
    return jsonify({
        'manual_total_balance': round(settings.manual_total_balance, 2),
        'manual_total_deposited': round(settings.manual_total_deposited, 2)
    })


@app.route('/api/bookmakers/<int:id>/deposit', methods=['POST'])
def deposit_to_bookmaker(id):
    bm = Bookmaker.query.get_or_404(id)
    data = request.get_json() or {}
    amount = float(data.get('amount', 0) or 0)

    bm.total_deposited += amount
    bm.balance += amount
    db.session.commit()

    user = get_or_create_default_user()
    txn = BankrollTransaction(
        user_id=user.id,
        type='deposit',
        amount=amount,
        bookmaker_id=bm.id,
        bookmaker_name=bm.name,
        description=data.get('description', 'Deposit') or 'Deposit'
    )
    db.session.add(txn)
    db.session.commit()

    return jsonify(bm.to_dict())


@app.route('/api/bookmakers/<int:id>/withdraw', methods=['POST'])
def withdraw_from_bookmaker(id):
    bm = Bookmaker.query.get_or_404(id)
    data = request.get_json() or {}
    amount = float(data.get('amount', 0) or 0)

    if amount > bm.balance:
        return jsonify({'error': 'Insufficient balance'}), 400

    bm.total_withdrawn += amount
    bm.balance -= amount
    db.session.commit()

    user = get_or_create_default_user()
    txn = BankrollTransaction(
        user_id=user.id,
        type='withdrawal',
        amount=amount,
        bookmaker_id=bm.id,
        bookmaker_name=bm.name,
        description=data.get('description', 'Withdrawal') or 'Withdrawal'
    )
    db.session.add(txn)
    db.session.commit()

    return jsonify(bm.to_dict())


@app.route('/api/bankroll/stats')
def bankroll_stats():
    settings = get_or_create_settings()
    total_balance = settings.manual_total_balance if settings.manual_total_balance else (db.session.query(db.func.sum(Bookmaker.balance)).scalar() or 0)
    total_deposited = settings.manual_total_deposited if settings.manual_total_deposited else (db.session.query(db.func.sum(Bookmaker.total_deposited)).scalar() or 0)
    total_withdrawn = db.session.query(db.func.sum(Bookmaker.total_withdrawn)).scalar() or 0
    at_stake = db.session.query(db.func.sum(BetSlip.stake)).filter(BetSlip.status == 'pending').scalar() or 0
    available = total_balance - at_stake

    all_profit = db.session.query(db.func.sum(BetSlip.profit_loss)).scalar() or 0

    red_triggered = False
    yellow_triggered = False
    if total_deposited > 0:
        available_pct = (available / total_deposited) * 100
        if available_pct < settings.bankroll_red_margin:
            red_triggered = True
        elif available_pct < settings.bankroll_yellow_margin:
            yellow_triggered = True

    return jsonify({
        'total_balance': round(total_balance, 2),
        'total_deposited': round(total_deposited, 2),
        'total_withdrawn': round(total_withdrawn, 2),
        'available': round(available, 2),
        'at_stake': round(at_stake, 2),
        'all_time_profit': round(all_profit, 2),
        'roi': round((all_profit / total_deposited * 100), 1) if total_deposited > 0 else 0,
        'red_margin_triggered': red_triggered,
        'yellow_margin_triggered': yellow_triggered,
        'red_margin_pct': settings.bankroll_red_margin,
        'yellow_margin_pct': settings.bankroll_yellow_margin
    })


@app.route('/api/bankroll/history')
def bankroll_history():
    days = int(request.args.get('days', 30))
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)

    labels = []
    balance_data = []
    deposited_data = []

    current_balance = db.session.query(db.func.sum(Bookmaker.balance)).scalar() or 0
    current_deposited = db.session.query(db.func.sum(Bookmaker.total_deposited)).scalar() or 0

    for i in range(days):
        date = start_date + timedelta(days=i)
        labels.append(date.strftime('%d %b'))
        date_end = datetime.combine(date.date(), datetime.max.time())
        slips_up_to_date = BetSlip.query.filter(
            BetSlip.settled_at != None,
            BetSlip.settled_at <= date_end,
            BetSlip.status.in_(['won', 'lost', 'cashed'])
        ).all()
        pl = sum(s.profit_loss for s in slips_up_to_date)
        balance_data.append(round(max(0, current_deposited + pl), 2))
        deposited_data.append(round(current_deposited, 2))

    return jsonify({
        'labels': labels,
        'balance_data': balance_data,
        'deposited_data': deposited_data
    })


@app.route('/api/bankroll/transactions')
def get_transactions():
    txns = BankrollTransaction.query.order_by(BankrollTransaction.created_at.desc()).limit(50).all()
    return jsonify([t.to_dict() for t in txns])


@app.route('/api/push/subscribe', methods=['POST'])
def push_subscribe():
    data = request.get_json() or {}
    endpoint = data.get('endpoint')
    p256dh = data.get('p256dh')
    auth = data.get('auth')

    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Invalid subscription payload'}), 400

    user = get_or_create_default_user()
    sub = PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).first()
    if not sub:
        sub = PushSubscription(user_id=user.id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.session.add(sub)
        db.session.commit()

    return jsonify(sub.to_dict()), 201


@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = get_or_create_settings()
    return jsonify(settings.to_dict())


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    settings = get_or_create_settings()
    data = request.get_json() or {}
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    db.session.commit()
    return jsonify(settings.to_dict())


@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'path': f'/static/uploads/{filename}', 'filename': filename})
    return jsonify({'error': 'Invalid file type'}), 400


@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/reports/pdf')
def generate_pdf_report():
    if not REPORTLAB_AVAILABLE:
        return jsonify({'error': 'ReportLab is not installed on the server. Unable to export PDF.'}), 500

    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    settings = get_or_create_settings()
    currency = settings.pdf_currency or 'TZS'
    company_name = settings.pdf_company_name or 'BOS GEMN'

    query = BetSlip.query

    if period == 'today':
        today = datetime.now().date()
        query = query.filter(db.func.date(BetSlip.match_datetime) == today)
    elif period == 'week':
        week_ago = datetime.now() - timedelta(days=7)
        query = query.filter(BetSlip.match_datetime >= week_ago)
    elif period == 'month':
        month_ago = datetime.now() - timedelta(days=30)
        query = query.filter(BetSlip.match_datetime >= month_ago)
    elif period == 'year':
        year_start = datetime.now().replace(month=1, day=1)
        query = query.filter(BetSlip.match_datetime >= year_start)
    elif start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            query = query.filter(BetSlip.match_datetime >= start, BetSlip.match_datetime <= end)
        except Exception:
            pass

    slips = query.order_by(BetSlip.created_at.desc()).all()
    bookmakers = Bookmaker.query.all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.4 * inch, bottomMargin=0.4 * inch, leftMargin=0.4 * inch, rightMargin=0.4 * inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=6,
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'CustomSubTitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=8,
        spaceBefore=14
    )

    normal_style = styles['Normal']
    normal_style.fontSize = 9

    story = []

    story.append(Paragraph(company_name.upper(), title_style))
    story.append(Paragraph(f"Betting Performance Report & Overview ({period.upper()})", subtitle_style))

    total_bets = len(slips)
    won = len([s for s in slips if s.status == 'won'])
    lost = len([s for s in slips if s.status == 'lost'])
    pending = len([s for s in slips if s.status == 'pending'])
    total_staked = sum(s.stake for s in slips)
    total_profit = sum(s.profit_loss for s in slips)
    roi_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    summary_data = [
        ['Total Bets', str(total_bets), 'Total Staked', f"{currency} {total_staked:,.0f}"],
        ['Won Slips', str(won), 'Net Profit / Loss', f"{currency} {total_profit:,.0f}"],
        ['Lost Slips', str(lost), 'ROI (%)', f"{roi_val:.1f}%"],
        ['Pending Slips', str(pending), 'Generated On', datetime.now().strftime('%Y-%m-%d %H:%M')]
    ]

    summary_table = Table(summary_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch, 1.8 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
    story.append(summary_table)

    if bookmakers:
        story.append(Paragraph("BOOKMAKER BREAKDOWN", heading_style))
        bm_data = [['Bookmaker', 'Balance', 'Total Deposited', 'Net P/L', 'Bets', 'ROI']]
        for bm in bookmakers:
            net_pl = bm.balance - bm.total_deposited + bm.total_withdrawn
            bm_data.append([
                bm.name,
                f"{currency} {bm.balance:,.0f}",
                f"{currency} {bm.total_deposited:,.0f}",
                f"{currency} {net_pl:,.0f}",
                str(bm.total_bets),
                f"{bm.roi:.1f}%"
            ])
        bm_table = Table(bm_data, colWidths=[1.5 * inch, 1.3 * inch, 1.4 * inch, 1.3 * inch, 0.8 * inch, 0.9 * inch])
        bm_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.HexColor('#ffffff')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(bm_table)

    if slips:
        story.append(Paragraph("DETAILED BETTING SLIPS", heading_style))
        table_data = [['Slip #', 'Slip Name / Details', 'Bookmaker', 'Odds', 'Stake', 'Status', 'P/L']]

        for slip in slips:
            pl = f"{currency} {slip.profit_loss:,.0f}" if slip.status != 'pending' else '-'
            matches = slip.get_matches()
            if matches:
                match_summary = ", ".join([f"{m.get('event','')} ({m.get('selection','')})" for m in matches[:2]])
                if len(matches) > 2:
                    match_summary += f" +{len(matches)-2} more"
                slip_desc = f"{slip.slip_name}\n[{match_summary}]"
            else:
                m_title = f"{slip.home_team} vs {slip.away_team}" if slip.home_team and slip.away_team else slip.prediction
                slip_desc = f"{slip.slip_name}\n[{m_title}]" if m_title else slip.slip_name

            table_data.append([
                slip.slip_number,
                slip_desc,
                slip.bookmaker_name or '-',
                f"{slip.odds:.2f}",
                f"{currency} {slip.stake:,.0f}",
                slip.status.upper(),
                pl
            ])

        detail_table = Table(table_data, colWidths=[0.9 * inch, 2.3 * inch, 1.1 * inch, 0.6 * inch, 0.9 * inch, 0.7 * inch, 0.7 * inch])
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.HexColor('#ffffff')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(detail_table)

    story.append(Spacer(1, 15))
    story.append(Paragraph(f"Report generated automatically by {company_name} — Confidential", normal_style))

    doc.build(story)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={company_name}_Report_{period}_{datetime.now().strftime("%Y%m%d")}.pdf'
    return response


@app.route('/api/seed', methods=['POST'])
def seed_data():
    user = get_or_create_default_user()
    get_or_create_settings()

    bookmakers_data = [
        {'name': 'Bet365', 'balance': 2500000.0, 'total_deposited': 3000000.0},
        {'name': 'Pinnacle', 'balance': 1800000.0, 'total_deposited': 2000000.0},
        {'name': 'DraftKings', 'balance': 1200000.0, 'total_deposited': 1500000.0},
        {'name': 'William Hill', 'balance': 900000.0, 'total_deposited': 1000000.0},
        {'name': 'Betfair', 'balance': 1500000.0, 'total_deposited': 1500000.0},
        {'name': 'Unibet', 'balance': 1100000.0, 'total_deposited': 1000000.0}
    ]

    for bm_info in bookmakers_data:
        bm = Bookmaker.query.filter_by(name=bm_info['name']).first()
        if not bm:
            bm = Bookmaker(
                user_id=user.id,
                name=bm_info['name'],
                balance=bm_info['balance'],
                total_deposited=bm_info['total_deposited']
            )
            db.session.add(bm)
    db.session.commit()

    sample_slips = [
        {
            'slip_name': 'Weekend Accumulator',
            'slip_number': 'SLIP-001',
            'matches': json.dumps([
                {'event': 'Man City vs Arsenal', 'selection': 'Over 2.5 Goals', 'odds': 1.85}
            ]),
            'home_team': 'Man City', 'away_team': 'Arsenal', 'league': 'Premier League',
            'country': 'England', 'sport': 'Football', 'market': 'Over/Under Goals',
            'prediction': 'Over 2.5 Goals', 'odds': 1.85, 'stake': 200000,
            'status': 'won', 'bookmaker_name': 'Bet365', 'confidence': 4,
            'strategy_tag': 'Over 2.5', 'match_datetime': datetime.now() - timedelta(days=1)
        },
        {
            'slip_name': 'NBA Night',
            'slip_number': 'SLIP-002',
            'matches': json.dumps([
                {'event': 'Lakers vs Warriors', 'selection': 'Lakers -4.5', 'odds': 1.92}
            ]),
            'home_team': 'Lakers', 'away_team': 'Warriors', 'league': 'NBA',
            'country': 'USA', 'sport': 'Basketball', 'market': 'Spread',
            'prediction': 'Lakers -4.5', 'odds': 1.92, 'stake': 150000,
            'status': 'won', 'bookmaker_name': 'DraftKings', 'confidence': 5,
            'strategy_tag': 'Spread Bet', 'match_datetime': datetime.now() - timedelta(days=1)
        },
        {
            'slip_name': 'El Clasico Special',
            'slip_number': 'SLIP-003',
            'matches': json.dumps([
                {'event': 'Barcelona vs Real Madrid', 'selection': 'BTTS Yes', 'odds': 1.65}
            ]),
            'home_team': 'Barcelona', 'away_team': 'Real Madrid', 'league': 'La Liga',
            'country': 'Spain', 'sport': 'Football', 'market': 'Both Teams to Score',
            'prediction': 'BTTS Yes', 'odds': 1.65, 'stake': 300000,
            'status': 'lost', 'bookmaker_name': 'Pinnacle', 'confidence': 3,
            'strategy_tag': 'BTTS', 'match_datetime': datetime.now() - timedelta(days=2)
        },
        {
            'slip_name': 'Wimbledon Bet',
            'slip_number': 'SLIP-004',
            'matches': json.dumps([
                {'event': 'Djokovic vs Alcaraz', 'selection': 'Djokovic Win', 'odds': 2.10}
            ]),
            'home_team': 'Djokovic', 'away_team': 'Alcaraz', 'league': 'Wimbledon',
            'country': 'UK', 'sport': 'Tennis', 'market': 'Match Winner',
            'prediction': 'Djokovic Win', 'odds': 2.10, 'stake': 100000,
            'status': 'pending', 'bookmaker_name': 'William Hill', 'confidence': 3,
            'strategy_tag': 'Match Winner', 'match_datetime': datetime.now() + timedelta(days=1)
        },
        {
            'slip_name': 'Bundesliga Value',
            'slip_number': 'SLIP-005',
            'matches': json.dumps([
                {'event': 'Bayern vs Dortmund', 'selection': 'Bayern Win', 'odds': 1.55}
            ]),
            'home_team': 'Bayern', 'away_team': 'Dortmund', 'league': 'Bundesliga',
            'country': 'Germany', 'sport': 'Football', 'market': 'Match Winner',
            'prediction': 'Bayern Win', 'odds': 1.55, 'stake': 250000,
            'status': 'cashed', 'bookmaker_name': 'Betfair', 'confidence': 5,
            'strategy_tag': 'Home Win', 'match_datetime': datetime.now() - timedelta(days=3)
        },
        {
            'slip_name': 'Ligue 1 Handicap',
            'slip_number': 'SLIP-007',
            'matches': json.dumps([
                {'event': 'PSG vs Marseille', 'selection': 'PSG -1', 'odds': 1.75}
            ]),
            'home_team': 'PSG', 'away_team': 'Marseille', 'league': 'Ligue 1',
            'country': 'France', 'sport': 'Football', 'market': 'Asian Handicap',
            'prediction': 'PSG -1', 'odds': 1.75, 'stake': 220000,
            'status': 'won', 'bookmaker_name': 'Unibet', 'confidence': 4,
            'strategy_tag': 'Asian Handicap', 'match_datetime': datetime.now() - timedelta(days=3)
        }
    ]

    for slip_data in sample_slips:
        if not BetSlip.query.filter_by(slip_number=slip_data['slip_number']).first():
            slip = BetSlip(user_id=user.id, **slip_data)
            slip.potential_return = round(slip.stake * slip.odds, 2)
            if slip.status == 'won':
                slip.profit_loss = slip.potential_return - slip.stake
                slip.settled_at = slip.match_datetime
                slip.return_amount = slip.potential_return
            elif slip.status == 'lost':
                slip.profit_loss = -slip.stake
                slip.settled_at = slip.match_datetime
                slip.return_amount = 0.0
            elif slip.status == 'cashed':
                slip.profit_loss = round(slip.potential_return * 0.7 - slip.stake, 2)
                slip.settled_at = slip.match_datetime
                slip.return_amount = round(slip.potential_return * 0.7, 2)

            bm = get_or_create_bookmaker(slip.bookmaker_name)
            slip.bookmaker_id = bm.id
            db.session.add(slip)

    db.session.commit()

    for bm in Bookmaker.query.all():
        update_bookmaker_stats(bm.id)

    return jsonify({'message': 'Seed data created successfully'})


def initialize_database():
    with app.app_context():
        db.create_all()
        get_or_create_default_user()
        get_or_create_settings()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_columns = {col['name'] for col in inspector.get_columns('user_settings')}
        if 'manual_total_balance' not in existing_columns:
            db.session.execute(db.text('ALTER TABLE user_settings ADD COLUMN manual_total_balance FLOAT DEFAULT 0'))
        if 'manual_total_deposited' not in existing_columns:
            db.session.execute(db.text('ALTER TABLE user_settings ADD COLUMN manual_total_deposited FLOAT DEFAULT 0'))
        db.session.commit()


initialize_database()


if __name__ == '__main__':
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)), host='0.0.0.0')