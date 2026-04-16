from flask import jsonify
from flask_login import login_required
from ..models import Invoice


def register_api_routes(bp):

    @bp.route('/api/statistics')
    @login_required
    def api_statistics():
        invoices = Invoice.query.all()
        invoice_count = len(invoices)
        total_amount = sum(float(invoice.amount_decimal) if invoice.amount_decimal is not None else 0
                           for invoice in invoices)

        monthly_data = {}
        for invoice in invoices:
            if invoice.invoice_date:
                month_key = invoice.invoice_date.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'count': 0, 'amount': 0}
                monthly_data[month_key]['count'] += 1
                amount = 0
                if invoice.amount_decimal is not None:
                    amount = float(invoice.amount_decimal)
                elif invoice.amount_in_figures:
                    try:
                        amount = float(invoice.amount_in_figures.replace('¥', '').replace('￥', '').replace(' ', '').replace('元', '').strip())
                    except ValueError:
                        pass
                monthly_data[month_key]['amount'] += amount

        sorted_months = sorted(monthly_data.keys())

        type_data = {}
        for invoice in invoices:
            if invoice.invoice_type:
                if invoice.invoice_type not in type_data:
                    type_data[invoice.invoice_type] = 0
                type_data[invoice.invoice_type] += 1

        formatted_data = {
            'invoice_count': invoice_count,
            'total_amount': "{:,.2f}".format(total_amount),
            'monthly_data': {
                'labels': sorted_months,
                'counts': [monthly_data[month]['count'] for month in sorted_months],
                'amounts': [monthly_data[month]['amount'] for month in sorted_months]
            },
            'type_data': {
                'labels': list(type_data.keys()),
                'counts': list(type_data.values())
            }
        }
        return jsonify(formatted_data)

    @bp.route('/api/update-all-invoices', methods=['POST'])
    @login_required
    def api_update_all_invoices():
        from ..utils import update_all_invoices_from_json
        result = update_all_invoices_from_json()
        if result:
            return jsonify({
                'success': True,
                'message': f'成功更新了 {result} 条发票记录',
                'updated_count': result
            })
        return jsonify({
            'success': False,
            'message': '没有需要更新的发票记录'
        })

    @bp.route('/api/cleanup-exported-files', methods=['POST'])
    @login_required
    def cleanup_files():
        from ..utils import cleanup_exported_files, cleanup_old_exported_files
        deleted_count1 = cleanup_exported_files()
        deleted_count2 = cleanup_old_exported_files()
        return jsonify({
            'success': True,
            'message': f'成功清理了 {deleted_count1 + deleted_count2} 个文件',
            'deleted_count': deleted_count1 + deleted_count2
        })
