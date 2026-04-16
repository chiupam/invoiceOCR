import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db as _db
from app.models import Invoice, Project, User


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    return app


@pytest.fixture(scope='function')
def app_context(app):
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture(scope='function')
def db(app_context):
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture(scope='function')
def client(app, db):
    return app.test_client()


@pytest.fixture(scope='function')
def sample_invoice(db):
    inv = Invoice(
        invoice_code='TEST001',
        invoice_number='INV001',
        invoice_type='增值税普通发票',
        total_amount='1,234.56',
        total_tax='78.90',
        amount_in_figures='1,313.46',
        seller_name='测试销售方',
        buyer_name='测试购买方'
    )
    inv.sync_decimal_fields()
    db.session.add(inv)
    db.session.commit()
    return inv


@pytest.fixture(scope='function')
def sample_project(db):
    proj = Project(name='测试项目', description='用于单元测试')
    db.session.add(proj)
    db.session.commit()
    return proj


@pytest.fixture(scope='function')
def auth_user(db):
    user = User(username='testuser', email='test@example.com', is_admin=True)
    user.set_password('testpassword123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture(scope='function')
def logged_in_client(client, app, auth_user):
    with app.test_request_context():
        from flask_login import login_user
        login_user(auth_user)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_user.id)
        sess['_fresh'] = True
    return client
