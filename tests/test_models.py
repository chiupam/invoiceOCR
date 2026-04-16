from decimal import Decimal
from app.models import Invoice, Project, User, Settings


class TestInvoiceModel:

    def test_clean_amount_str_with_yuan_sign(self):
        result = Invoice._clean_amount_str('¥1,234.56')
        assert result == Decimal('1234.56')

    def test_clean_amount_str_with_fullwidth_yuan(self):
        result = Invoice._clean_amount_str('￥999.00')
        assert result == Decimal('999.00')

    def test_clean_amount_str_with_chinese_yuan(self):
        result = Invoice._clean_amount_str('1,313.46元')
        assert result == Decimal('1313.46')

    def test_clean_amount_str_none(self):
        result = Invoice._clean_amount_str(None)
        assert result is None

    def test_clean_amount_str_empty(self):
        result = Invoice._clean_amount_str('')
        assert result is None

    def test_clean_amount_str_spaces_only(self):
        result = Invoice._clean_amount_str('   ')
        assert result is None

    def test_clean_amount_str_invalid(self):
        result = Invoice._clean_amount_str('abc')
        assert result is None

    def test_sync_decimal_fields(self, db):
        inv = Invoice(
            invoice_code='S001', invoice_number='N001',
            total_amount='¥2,000.00', total_tax='¥120.00',
            amount_in_figures='¥2,120.00'
        )
        inv.sync_decimal_fields()
        db.session.add(inv)
        db.session.commit()

        assert inv.total_amount_decimal == Decimal('2000.00')
        assert inv.total_tax_decimal == Decimal('120.00')
        assert inv.amount_decimal == Decimal('2120.00')

    def test_sync_decimal_fields_no_overwrite(self, db):
        inv = Invoice(
            invoice_code='S002', invoice_number='N002',
            total_amount='¥500.00', total_tax='¥30.00',
            amount_in_figures='¥530.00'
        )
        inv.sync_decimal_fields()
        inv.amount_decimal = Decimal('999.99')
        inv.sync_decimal_fields()
        assert inv.amount_decimal == Decimal('999.99')

    def test_get_total_amount_decimal_from_column(self, db):
        inv = Invoice(
            invoice_code='S003', invoice_number='N003',
            amount_in_figures='¥100.00'
        )
        inv.sync_decimal_fields()
        db.session.add(inv)
        db.session.commit()
        assert inv.get_total_amount_decimal() == Decimal('100.00')

    def test_get_total_amount_decimal_fallback(self, db):
        inv = Invoice(
            invoice_code='S004', invoice_number='N004',
            amount_in_figures='¥200.00'
        )
        assert inv.get_total_amount_decimal() == Decimal('200.00')

    def test_get_total_amount_decimal_empty(self, db):
        inv = Invoice(
            invoice_code='S005', invoice_number='N005',
            amount_in_figures=''
        )
        assert inv.get_total_amount_decimal() == Decimal('0')


class TestInvoiceSorting:

    def test_sort_by_amount_desc(self, db):
        inv1 = Invoice(invoice_code='A1', invoice_number='B1', amount_in_figures='100.00')
        inv1.sync_decimal_fields()
        inv2 = Invoice(invoice_code='A2', invoice_number='B2', amount_in_figures='500.00')
        inv2.sync_decimal_fields()
        inv3 = Invoice(invoice_code='A3', invoice_number='B3', amount_in_figures='300.00')
        inv3.sync_decimal_fields()
        db.session.add_all([inv1, inv2, inv3])
        db.session.commit()

        results = Invoice.query.order_by(Invoice.amount_decimal.desc().nulls_last()).all()
        amounts = [float(r.amount_decimal) for r in results]
        assert amounts == sorted(amounts, reverse=True)

    def test_sort_by_amount_asc(self, db):
        inv1 = Invoice(invoice_code='A1', invoice_number='B1', amount_in_figures='100.00')
        inv1.sync_decimal_fields()
        inv2 = Invoice(invoice_code='A2', invoice_number='B2', amount_in_figures='500.00')
        inv2.sync_decimal_fields()
        db.session.add_all([inv1, inv2])
        db.session.commit()

        results = Invoice.query.order_by(Invoice.amount_decimal.asc().nulls_last()).all()
        assert float(results[0].amount_decimal) <= float(results[1].amount_decimal)

    def test_sort_nulls_last(self, db):
        inv1 = Invoice(invoice_code='A1', invoice_number='B1', amount_in_figures='100.00')
        inv1.sync_decimal_fields()
        inv2 = Invoice(invoice_code='A2', invoice_number='B2', amount_in_figures='')
        inv2.sync_decimal_fields()
        db.session.add_all([inv1, inv2])
        db.session.commit()

        results = Invoice.query.order_by(Invoice.amount_decimal.desc().nulls_last()).all()
        assert results[-1].amount_decimal is None


class TestProjectModel:

    def test_create_project(self, db):
        proj = Project(name='新项目', description='测试描述')
        db.session.add(proj)
        db.session.commit()
        assert proj.id is not None
        assert proj.name == '新项目'

    def test_project_invoice_relationship(self, db, sample_project, sample_invoice):
        sample_invoice.project_id = sample_project.id
        db.session.commit()
        assert len(sample_project.invoices) == 1
        assert sample_project.invoices[0].invoice_code == 'TEST001'


class TestUserModel:

    def test_password_hashing(self, db):
        user = User(username='test', email='test@test.com')
        user.set_password('mypassword')
        assert user.check_password('mypassword')
        assert not user.check_password('wrongpassword')

    def test_can_register(self, db):
        assert User.can_register() == True
        user = User(username='owner', email='owner@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        assert User.can_register() == False


class TestSettingsModel:

    def test_set_and_get_value(self, db):
        Settings.set_value('TEST_KEY', 'test_value')
        result = Settings.get_value('TEST_KEY')
        assert result == 'test_value'

    def test_get_default_value(self, db):
        result = Settings.get_value('NONEXISTENT_KEY', 'default')
        assert result == 'default'

    def test_update_value(self, db):
        Settings.set_value('TEST_KEY', 'value1')
        Settings.set_value('TEST_KEY', 'value2')
        result = Settings.get_value('TEST_KEY')
        assert result == 'value2'
