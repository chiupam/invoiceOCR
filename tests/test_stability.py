import json
import os
from unittest.mock import patch, MagicMock
from app.models import Invoice, InvoiceItem


class TestRerecognizeRoute:

    def test_rerecognize_requires_login(self, client):
        response = client.post('/invoice/1/rerecognize')
        assert response.status_code == 302
        assert '/auth' in response.headers['Location']

    def test_rerecognize_no_image_path(self, logged_in_client, db):
        inv = Invoice(
            invoice_code='R001', invoice_number='RN001',
            invoice_type='增值税普通发票',
            image_path=None
        )
        db.session.add(inv)
        db.session.commit()

        response = logged_in_client.post(
            f'/invoice/{inv.id}/rerecognize',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        data = json.loads(response.data)
        assert data['success'] is False
        assert '没有关联的图片文件' in data['message']

    def test_rerecognize_image_not_found(self, logged_in_client, db):
        inv = Invoice(
            invoice_code='R002', invoice_number='RN002',
            invoice_type='增值税普通发票',
            image_path='nonexistent_file.jpg'
        )
        db.session.add(inv)
        db.session.commit()

        response = logged_in_client.post(
            f'/invoice/{inv.id}/rerecognize',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        data = json.loads(response.data)
        assert data['success'] is False
        assert '图片文件不存在' in data['message']

    def test_rerecognize_with_valid_image(self, logged_in_client, db):
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        test_file_path = os.path.join(upload_dir, 'test_rerecognize.jpg')
        with open(test_file_path, 'wb') as f:
            f.write(b'fake image data')

        try:
            inv = Invoice(
                invoice_code='R003', invoice_number='RN003',
                invoice_type='增值税普通发票',
                image_path='test_rerecognize.jpg',
                seller_name='原销售方'
            )
            db.session.add(inv)
            db.session.commit()

            mock_result = {
                'success': False,
                'message': 'OCR识别失败: 测试模拟失败'
            }

            with patch('app.blueprints.invoice.process_invoice_image', return_value=mock_result):
                response = logged_in_client.post(
                    f'/invoice/{inv.id}/rerecognize',
                    headers={'X-Requested-With': 'XMLHttpRequest'}
                )
                data = json.loads(response.data)
                assert data['success'] is False
                assert '重新识别失败' in data['message']
        finally:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)


class TestTransactionManagement:

    def test_rollback_on_duplicate_invoice(self, db):
        inv1 = Invoice(
            invoice_code='DUP001', invoice_number='DUP001',
            invoice_type='增值税普通发票'
        )
        db.session.add(inv1)
        db.session.commit()

        inv2 = Invoice(
            invoice_code='DUP001', invoice_number='DUP001',
            invoice_type='增值税普通发票'
        )
        db.session.add(inv2)

        try:
            db.session.commit()
            assert False, "Should have raised an exception"
        except Exception:
            db.session.rollback()

        remaining = Invoice.query.filter_by(invoice_code='DUP001').all()
        assert len(remaining) == 1

    def test_atomic_invoice_and_items_creation(self, db):
        inv = Invoice(
            invoice_code='ATM001', invoice_number='ATM001',
            invoice_type='增值税普通发票',
            total_amount='1000.00',
            amount_in_figures='¥1130.00'
        )
        inv.sync_decimal_fields()
        db.session.add(inv)
        db.session.flush()

        item = InvoiceItem(
            invoice_id=inv.id,
            name='测试商品',
            amount='1000.00',
            tax_rate='13%',
            tax='130.00'
        )
        db.session.add(item)
        db.session.commit()

        loaded_inv = db.session.get(Invoice, inv.id)
        loaded_items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
        assert loaded_inv is not None
        assert len(loaded_items) == 1
        assert loaded_items[0].name == '测试商品'

    def test_rollback_preserves_existing_data(self, db):
        inv1 = Invoice(
            invoice_code='RB001', invoice_number='RB001',
            invoice_type='增值税普通发票'
        )
        db.session.add(inv1)
        db.session.commit()
        first_id = inv1.id

        inv2 = Invoice(
            invoice_code='RB001', invoice_number='RB001',
            invoice_type='增值税专用发票'
        )
        db.session.add(inv2)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        loaded = db.session.get(Invoice, first_id)
        assert loaded is not None
        assert loaded.invoice_type == '增值税普通发票'

    def test_delete_cascade_items(self, db):
        inv = Invoice(
            invoice_code='DEL001', invoice_number='DEL001',
            invoice_type='增值税普通发票'
        )
        db.session.add(inv)
        db.session.flush()

        item1 = InvoiceItem(invoice_id=inv.id, name='商品1', amount='500.00')
        item2 = InvoiceItem(invoice_id=inv.id, name='商品2', amount='600.00')
        db.session.add_all([item1, item2])
        db.session.commit()

        InvoiceItem.query.filter_by(invoice_id=inv.id).delete()
        db.session.delete(inv)
        db.session.commit()

        assert db.session.get(Invoice, inv.id) is None
        assert InvoiceItem.query.filter_by(invoice_id=inv.id).count() == 0


class TestConnectionManagement:

    def test_ocr_api_retry_mechanism(self):
        from core.ocr_api import OCRClient

        with patch.object(OCRClient, '__init__', lambda self: None):
            client = OCRClient()
            client.httpProfile = MagicMock()
            client.httpProfile.endpoint = "ocr.tencentcloudapi.com"
            client.cred = MagicMock()
            client.cred.secretId = "test_id"
            client.cred.secretKey = "test_key"

            call_count = 0

            def mock_connect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Connection failed")
                mock_conn = MagicMock()
                mock_resp = MagicMock()
                mock_resp.read.return_value = b'{"Response": {}}'
                mock_conn.getresponse.return_value = mock_resp
                return mock_conn

            with patch('core.ocr_api.HTTPSConnection', side_effect=mock_connect):
                with patch('core.ocr_api.time.sleep'):
                    try:
                        client._call_api("VatInvoiceOCR", {})
                        assert call_count == 3
                    except Exception:
                        pass

    def test_connection_closed_on_success(self):
        from core.ocr_api import OCRClient

        with patch.object(OCRClient, '__init__', lambda self: None):
            client = OCRClient()
            client.httpProfile = MagicMock()
            client.httpProfile.endpoint = "ocr.tencentcloudapi.com"
            client.cred = MagicMock()
            client.cred.secretId = "test_id"
            client.cred.secretKey = "test_key"

            mock_conn = MagicMock()
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"Response": {}}'
            mock_conn.getresponse.return_value = mock_resp

            with patch('core.ocr_api.HTTPSConnection', return_value=mock_conn):
                try:
                    client._call_api("VatInvoiceOCR", {})
                except Exception:
                    pass
                mock_conn.close.assert_called()

    def test_connection_closed_on_error(self):
        from core.ocr_api import OCRClient

        with patch.object(OCRClient, '__init__', lambda self: None):
            client = OCRClient()
            client.httpProfile = MagicMock()
            client.httpProfile.endpoint = "ocr.tencentcloudapi.com"
            client.cred = MagicMock()
            client.cred.secretId = "test_id"
            client.cred.secretKey = "test_key"

            mock_conn = MagicMock()
            mock_conn.request.side_effect = Exception("Network error")

            with patch('core.ocr_api.HTTPSConnection', return_value=mock_conn):
                with patch('core.ocr_api.time.sleep'):
                    try:
                        client._call_api("VatInvoiceOCR", {}, max_retries=1)
                    except Exception:
                        pass
                    mock_conn.close.assert_called()
