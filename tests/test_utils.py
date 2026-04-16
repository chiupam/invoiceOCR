from app.utils import PaginationObj, get_invoice_statistics
from app.models import Invoice


class TestPaginationObj:

    def test_basic_pagination(self):
        p = PaginationObj(items=[1, 2, 3, 4, 5], page=1, per_page=2, total=5)
        assert p.pages == 3
        assert p.has_prev == False
        assert p.has_next == True
        assert p.prev_num is None
        assert p.next_num == 2

    def test_middle_page(self):
        p = PaginationObj(items=[3, 4], page=2, per_page=2, total=5)
        assert p.has_prev == True
        assert p.has_next == True
        assert p.prev_num == 1
        assert p.next_num == 3

    def test_last_page(self):
        p = PaginationObj(items=[5], page=3, per_page=2, total=5)
        assert p.has_prev == True
        assert p.has_next == False
        assert p.next_num is None

    def test_single_page(self):
        p = PaginationObj(items=[1], page=1, per_page=10, total=1)
        assert p.pages == 1
        assert p.has_prev == False
        assert p.has_next == False

    def test_iter_pages(self):
        p = PaginationObj(items=[], page=5, per_page=1, total=10)
        pages = list(p.iter_pages())
        assert 1 in pages
        assert 5 in pages
        assert 10 in pages

    def test_zero_total(self):
        p = PaginationObj(items=[], page=1, per_page=10, total=0)
        assert p.pages == 0
        assert p.has_prev == False
        assert p.has_next == False


class TestGetInvoiceStatistics:

    def test_empty_invoices(self, db):
        stats = get_invoice_statistics([])
        assert stats['invoice_count'] == 0
        assert stats['total_amount'] == '0.00'

    def test_single_invoice(self, db, sample_invoice):
        stats = get_invoice_statistics([sample_invoice])
        assert stats['invoice_count'] == 1
        assert '1,313.46' in stats['total_amount']

    def test_multiple_invoices(self, db):
        inv1 = Invoice(invoice_code='X1', invoice_number='Y1', amount_in_figures='100.00')
        inv1.sync_decimal_fields()
        inv2 = Invoice(invoice_code='X2', invoice_number='Y2', amount_in_figures='200.00')
        inv2.sync_decimal_fields()
        db.session.add_all([inv1, inv2])
        db.session.commit()

        stats = get_invoice_statistics([inv1, inv2])
        assert stats['invoice_count'] == 2
        assert '300.00' in stats['total_amount']

    def test_invoice_with_no_amount(self, db):
        inv = Invoice(invoice_code='X1', invoice_number='Y1', amount_in_figures='')
        inv.sync_decimal_fields()
        db.session.add(inv)
        db.session.commit()

        stats = get_invoice_statistics([inv])
        assert stats['invoice_count'] == 1
        assert stats['total_amount'] == '0.00'
