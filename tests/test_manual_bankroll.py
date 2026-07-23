import pytest

from app import app, db, update_bookmaker_stats
from models import Bookmaker, BetSlip


@pytest.fixture
def test_app():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_manual_balance_is_preserved_when_slips_update(test_app):
    with app.app_context():
        bookmaker = Bookmaker(name='Manual Bookmaker', balance=2500000.0, total_deposited=2000000.0)
        db.session.add(bookmaker)
        db.session.commit()

        slip = BetSlip(stake=1000.0, status='pending', bookmaker_id=bookmaker.id)
        db.session.add(slip)
        db.session.commit()

        update_bookmaker_stats(bookmaker.id)

        refreshed = Bookmaker.query.get(bookmaker.id)
        assert refreshed.balance == 2500000.0
        assert refreshed.total_deposited == 2000000.0
        assert refreshed.total_bets == 1
