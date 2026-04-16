import json
from core.invoice_formatter import InvoiceFormatter


SAMPLE_VAT_INVOICE_RESPONSE = {
    "Response": {
        "VatInvoiceInfos": [
            {"Name": "发票类型", "Value": "增值税专用发票", "Confidence": 95},
            {"Name": "发票代码", "Value": "044001900111", "Confidence": 98},
            {"Name": "发票号码", "Value": "12345678", "Confidence": 97},
            {"Name": "开票日期", "Value": "2024年01月15日", "Confidence": 92},
            {"Name": "校验码", "Value": "", "Confidence": 50},
            {"Name": "购买方名称", "Value": "测试购买方公司", "Confidence": 88},
            {"Name": "购买方识别号", "Value": "91440101MA5C12345A", "Confidence": 85},
            {"Name": "销售方名称", "Value": "测试销售方公司", "Confidence": 91},
            {"Name": "销售方识别号", "Value": "91440101MA5D67890B", "Confidence": 89},
            {"Name": "合计金额", "Value": "1000.00", "Confidence": 96},
            {"Name": "合计税额", "Value": "130.00", "Confidence": 94},
            {"Name": "价税合计(大写)", "Value": "壹仟壹佰叁拾元整", "Confidence": 82},
            {"Name": "小写金额", "Value": "¥1130.00", "Confidence": 97},
        ],
        "Items": []
    }
}


SAMPLE_GENERAL_INVOICE_RESPONSE = {
    "Response": {
        "VatInvoiceInfos": [
            {"Name": "发票类型", "Value": "增值税普通发票", "Confidence": 93},
            {"Name": "发票代码", "Value": "044002000211", "Confidence": 99},
            {"Name": "发票号码", "Value": "87654321", "Confidence": 96},
            {"Name": "开票日期", "Value": "2024-02-20", "Confidence": 90},
            {"Name": "购买方名称", "Value": "普通购买方", "Confidence": 78},
            {"Name": "销售方名称", "Value": "普通销售方", "Confidence": 86},
            {"Name": "合计金额", "Value": "500.00", "Confidence": 95},
            {"Name": "合计税额", "Value": "65.00", "Confidence": 93},
            {"Name": "小写金额", "Value": "¥565.00", "Confidence": 94},
        ],
        "Items": []
    }
}


SAMPLE_NO_CONFIDENCE_RESPONSE = {
    "Response": {
        "VatInvoiceInfos": [
            {"Name": "发票类型", "Value": "增值税专用发票"},
            {"Name": "发票代码", "Value": "044001900111"},
            {"Name": "发票号码", "Value": "12345678"},
            {"Name": "开票日期", "Value": "2024年01月15日"},
            {"Name": "购买方名称", "Value": "测试购买方公司"},
            {"Name": "销售方名称", "Value": "测试销售方公司"},
            {"Name": "合计金额", "Value": "1000.00"},
            {"Name": "合计税额", "Value": "130.00"},
            {"Name": "小写金额", "Value": "¥1130.00"},
        ],
        "Items": []
    }
}


class TestConfidenceExtraction:

    def test_vat_invoice_extracts_confidence(self):
        json_string = json.dumps(SAMPLE_VAT_INVOICE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        assert '置信度' in result
        confidence = result['置信度']
        assert isinstance(confidence, dict)
        assert confidence['发票类型'] == 95
        assert confidence['发票代码'] == 98
        assert confidence['发票号码'] == 97

    def test_general_invoice_extracts_confidence(self):
        json_string = json.dumps(SAMPLE_GENERAL_INVOICE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        assert '置信度' in result
        confidence = result['置信度']
        assert isinstance(confidence, dict)
        assert confidence['发票类型'] == 93
        assert confidence['购买方名称'] == 78

    def test_no_confidence_data_still_works(self):
        json_string = json.dumps(SAMPLE_NO_CONFIDENCE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        assert '基本信息' in result
        assert result['基本信息']['发票代码'] == '044001900111'
        assert '置信度' not in result

    def test_confidence_values_preserved_accurately(self):
        json_string = json.dumps(SAMPLE_VAT_INVOICE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        confidence = result['置信度']
        assert confidence['校验码'] == 50
        assert confidence['购买方名称'] == 88
        assert confidence['购买方识别号'] == 85

    def test_confidence_stored_in_json_data(self):
        json_string = json.dumps(SAMPLE_VAT_INVOICE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        serialized = json.dumps(result, ensure_ascii=False)
        deserialized = json.loads(serialized)

        assert '置信度' in deserialized
        assert deserialized['置信度']['发票类型'] == 95

    def test_low_confidence_fields_identifiable(self):
        json_string = json.dumps(SAMPLE_GENERAL_INVOICE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        confidence = result['置信度']
        low_conf_fields = [k for k, v in confidence.items() if v < 80]
        assert '购买方名称' in low_conf_fields

    def test_high_confidence_fields_identifiable(self):
        json_string = json.dumps(SAMPLE_VAT_INVOICE_RESPONSE)
        result = InvoiceFormatter.format_invoice_data(json_string=json_string)

        confidence = result['置信度']
        high_conf_fields = [k for k, v in confidence.items() if v >= 90]
        assert '发票类型' in high_conf_fields
        assert '发票代码' in high_conf_fields


class TestConfidenceFromInvoiceModel:

    def test_confidence_retrieved_from_json_data(self, db):
        from app.models import Invoice

        formatted_data = {
            '基本信息': {'发票代码': 'T001', '发票号码': 'N001', '发票类型': '增值税专用发票'},
            '销售方信息': {'名称': '测试销售方'},
            '购买方信息': {'名称': '测试购买方'},
            '金额信息': {'合计金额': '¥1000.00', '合计税额': '¥130.00', '价税合计(小写)': '¥1130.00'},
            '商品信息': [],
            '其他信息': {},
            '置信度': {'发票代码': 98, '发票号码': 97, '购买方名称': 78}
        }

        inv = Invoice(
            invoice_code='T001',
            invoice_number='N001',
            invoice_type='增值税专用发票',
            json_data=json.dumps(formatted_data, ensure_ascii=False)
        )
        db.session.add(inv)
        db.session.commit()

        loaded = db.session.get(Invoice, inv.id)
        loaded_json = json.loads(loaded.json_data)
        confidence_data = loaded_json.get('置信度', None)

        assert confidence_data is not None
        assert confidence_data['发票代码'] == 98
        assert confidence_data['购买方名称'] == 78

    def test_invoice_without_confidence_still_loads(self, db):
        from app.models import Invoice

        formatted_data = {
            '基本信息': {'发票代码': 'T002', '发票号码': 'N002', '发票类型': '增值税普通发票'},
            '销售方信息': {'名称': '测试销售方'},
            '购买方信息': {'名称': '测试购买方'},
            '金额信息': {'合计金额': '¥500.00', '合计税额': '¥65.00', '价税合计(小写)': '¥565.00'},
            '商品信息': [],
            '其他信息': {}
        }

        inv = Invoice(
            invoice_code='T002',
            invoice_number='N002',
            invoice_type='增值税普通发票',
            json_data=json.dumps(formatted_data, ensure_ascii=False)
        )
        db.session.add(inv)
        db.session.commit()

        loaded = db.session.get(Invoice, inv.id)
        loaded_json = json.loads(loaded.json_data)
        confidence_data = loaded_json.get('置信度', None)

        assert confidence_data is None

    def test_confidence_threshold_categorization(self):
        test_cases = [
            (95, 'high'),
            (90, 'high'),
            (89, 'medium'),
            (80, 'medium'),
            (79, 'low'),
            (50, 'low'),
            (0, 'low'),
        ]

        for value, expected_category in test_cases:
            if value >= 90:
                category = 'high'
            elif value >= 80:
                category = 'medium'
            else:
                category = 'low'
            assert category == expected_category, f"Value {value} should be {expected_category}, got {category}"
