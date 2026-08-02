import io
import os
import tempfile

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


def test_screenshot_upload_uses_clear_name_and_saves_metadata(test_app):
    with tempfile.TemporaryDirectory() as temp_dir:
        app.config.update(UPLOAD_FOLDER=temp_dir)
        client = app.test_client()

        payload = {
            'slip_name': 'Weekend Acca',
            'stake': '50000',
            'odds': '2.35',
            'bookmaker': 'Bet365',
            'screenshot_name': 'Weekend Screenshot',
            'matches': '[]'
        }
        image_bytes = b'fake-image-bytes'
        response = client.post('/api/slips', data={
            **payload,
            'screenshot': (io.BytesIO(image_bytes), 'example.png')
        }, content_type='multipart/form-data')

        assert response.status_code == 201
        data = response.get_json()
        assert data['screenshot_name'] == 'Weekend Screenshot'
        assert data['screenshot_path'].startswith('/static/uploads/')

        saved_path = data['screenshot_path'].replace('/static/uploads/', '', 1)
        assert os.path.exists(os.path.join(temp_dir, saved_path))
        assert 'weekend_screenshot' in saved_path.lower()
