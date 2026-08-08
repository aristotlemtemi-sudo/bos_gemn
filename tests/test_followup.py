import io
import os
import tempfile

import pytest

from app import app, db
from models import BetSlip


@pytest.fixture
def test_app():
    app.config.update(TESTING=True)
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_slip(**kwargs):
    defaults = {
        'slip_name': 'Test Slip',
        'slip_number': 'SLIP-FU-001',
        'stake': 1000.0,
        'odds': 3.0,
        'status': 'lost',
        'screenshot_path': '/static/uploads/slip_test.png',
        'raw_text': 'Test Raw Text',
        'settled_at': None,
    }
    defaults.update(kwargs)
    slip = BetSlip(**defaults)
    slip.set_matches([
        {'event': 'Team A vs Team B', 'selection': 'Home Win', 'odds': 1.5},
        {'event': 'Team C vs Team D', 'selection': 'Away Win', 'odds': 2.0},
    ])
    db.session.add(slip)
    db.session.commit()
    return slip


def test_followup_returns_only_settled_slips_with_attachment(test_app):
    with app.app_context():
        _make_slip(status='lost', settled_at=None)
        _make_slip(status='pending')            # pending -> excluded
        _make_slip(status='won', screenshot_path='', raw_text='')  # settled but no attachment -> excluded

    client = app.test_client()
    response = client.get('/api/followup')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['status'] == 'lost'


def test_followup_put_saves_notes_lost_matches_and_annotations(test_app):
    with app.app_context():
        slip = _make_slip(status='lost', settled_at=None)
        slip_id = slip.id

    client = app.test_client()
    response = client.put(f'/api/followup/{slip_id}', json={
        'follow_up_notes': 'Lost on the Arsenal game',
        'lost_matches': [{'index': 0, 'event': 'Team A vs Team B', 'selection': 'Home Win', 'lost': True}],
        'screenshot_annotations': [{'x': 42.5, 'y': 31.2, 'size': 4.0}]
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['follow_up_notes'] == 'Lost on the Arsenal game'
    assert data['lost_matches'][0]['index'] == 0
    assert data['lost_matches'][0]['lost'] is True
    assert data['screenshot_annotations'][0]['x'] == 42.5


def test_followup_pdf_returns_pdf(test_app):
    with app.app_context():
        _make_slip(status='lost', settled_at=None)

    client = app.test_client()
    response = client.get('/api/followup/pdf')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/pdf'
    assert response.data[:4] == b'%PDF'


def test_followup_pdf_errors_when_no_settled_slips(test_app):
    client = app.test_client()
    response = client.get('/api/followup/pdf')
    assert response.status_code == 400
