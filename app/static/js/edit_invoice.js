document.addEventListener('DOMContentLoaded', function() {
    // 绑定添加明细项按钮
    const addItemBtn = document.getElementById('addItemBtn');
    if (addItemBtn) {
        addItemBtn.addEventListener('click', addNewItem);
    }
    
    // 绑定删除明细项按钮
    const removeButtons = document.querySelectorAll('.remove-item');
    removeButtons.forEach(button => {
        button.addEventListener('click', removeItem);
    });
    
    // 绑定计算功能
    const itemsTable = document.getElementById('itemsTable');
    if (itemsTable) {
        itemsTable.addEventListener('input', function(e) {
            if (e.target && e.target.tagName === 'INPUT') {
                const input = e.target;
                const row = input.closest('tr');
                
                if (input.name.includes('[quantity]') || input.name.includes('[price]') || input.name.includes('[tax_rate]')) {
                    calculateRowValues(row);
                }
            }
        });
    }
});

// 添加新行项目
function addNewItem() {
    const itemsTable = document.getElementById('itemsTable');
    const tbody = itemsTable.querySelector('tbody');
    const template = document.getElementById('itemRowTemplate');
    const newRow = template.content.cloneNode(true);
    
    // 设置正确的索引
    const rows = tbody.querySelectorAll('tr');
    const nextIndex = rows.length;
    
    // 更新索引
    let html = newRow.querySelector('tr').innerHTML;
    html = html.replace(/INDEX/g, nextIndex);
    
    const tr = document.createElement('tr');
    tr.innerHTML = html;
    tbody.appendChild(tr);
    
    // 绑定删除按钮
    const removeBtn = tr.querySelector('.remove-item');
    removeBtn.addEventListener('click', removeItem);
}

// 删除行项目
function removeItem(e) {
    const row = e.target.closest('tr');
    if (row) {
        row.remove();
        
        // 更新索引
        const tbody = document.querySelector('#itemsTable tbody');
        const rows = tbody.querySelectorAll('tr');
        
        rows.forEach((row, index) => {
            const inputs = row.querySelectorAll('input');
            inputs.forEach(input => {
                const name = input.name;
                const newName = name.replace(/items\[\d+\]/, `items[${index}]`);
                input.name = newName;
            });
        });
    }
}

// 计算行金额和税额
function calculateRowValues(row) {
    const quantityInput = row.querySelector('input[name*="[quantity]"]');
    const priceInput = row.querySelector('input[name*="[price]"]');
    const taxRateInput = row.querySelector('input[name*="[tax_rate]"]');
    const amountInput = row.querySelector('input[name*="[amount]"]');
    const taxInput = row.querySelector('input[name*="[tax]"]');
    
    if (quantityInput && priceInput && taxRateInput && amountInput && taxInput) {
        const quantity = parseFloat(quantityInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const taxRate = parseFloat(taxRateInput.value) || 0;
        
        const amount = quantity * price;
        const tax = amount * (taxRate / 100);
        
        amountInput.value = amount.toFixed(2);
        taxInput.value = tax.toFixed(2);
    }
}

// 表单提交前验证
document.getElementById('invoiceForm').addEventListener('submit', function(e) {
    // 更新发票总金额和总税额
    let totalAmount = 0;
    let totalTax = 0;
    
    document.querySelectorAll('.item-amount').forEach(function(input) {
        totalAmount += parseFloat(input.value) || 0;
    });
    
    document.querySelectorAll('.item-tax').forEach(function(input) {
        totalTax += parseFloat(input.value) || 0;
    });
    
    document.getElementById('total_amount').value = totalAmount.toFixed(2);
    document.getElementById('tax_amount').value = totalTax.toFixed(2);
}); 