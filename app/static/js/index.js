document.addEventListener('DOMContentLoaded', function() {
    // 加载图表数据
    const chartDataElement = document.getElementById('chartData');
    const typeDataElement = document.getElementById('typeData');
    
    if (chartDataElement) {
        const chartData = JSON.parse(chartDataElement.textContent);
        renderMonthlyChart(chartData);
    }
    
    if (typeDataElement) {
        const typeData = JSON.parse(typeDataElement.textContent);
        renderTypeChart(typeData);
    }
    
    // 处理排序链接点击事件
    const sortLinks = document.querySelectorAll('.sort-link');
    sortLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const field = this.dataset.field;
            const currentUrl = new URL(window.location.href);
            
            // 检查当前排序状态
            const sortField = currentUrl.searchParams.get('sort');
            const sortDir = currentUrl.searchParams.get('direction');
            
            // 切换排序方向或设置新的排序字段
            if (sortField === field) {
                currentUrl.searchParams.set('direction', sortDir === 'asc' ? 'desc' : 'asc');
            } else {
                currentUrl.searchParams.set('sort', field);
                currentUrl.searchParams.set('direction', 'asc');
            }
            
            window.location.href = currentUrl.toString();
        });
    });
    
    // 处理删除模态框
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const type = button.getAttribute('data-type');
            const number = button.getAttribute('data-number');
            
            const confirmText = deleteModal.querySelector('.modal-body p:first-child');
            const invoiceInfo = document.createElement('p');
            invoiceInfo.innerHTML = `<strong>发票信息: </strong>${type} - ${number}`;
            
            if (deleteModal.querySelector('.modal-body p:nth-child(2)')) {
                deleteModal.querySelector('.modal-body p:nth-child(2)').remove();
            }
            
            deleteModal.querySelector('.modal-body').appendChild(invoiceInfo);
            
            // 设置表单的action属性
            const deleteForm = deleteModal.querySelector('#deleteForm');
            deleteForm.action = `/invoice/${id}/delete`;
        });
    }
});

/**
 * 渲染月度发票统计图表
 */
function renderMonthlyChart(data) {
    const ctx = document.getElementById('monthlyChart').getContext('2d');
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '发票数量',
                    data: data.counts,
                    backgroundColor: 'rgba(78, 115, 223, 0.7)',
                    borderColor: 'rgba(78, 115, 223, 1)',
                    borderWidth: 1
                },
                {
                    label: '发票金额',
                    data: data.amounts,
                    backgroundColor: 'rgba(28, 200, 138, 0.7)',
                    borderColor: 'rgba(28, 200, 138, 1)',
                    borderWidth: 1,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '发票数量'
                    }
                },
                y1: {
                    beginAtZero: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: '发票金额'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: '每月发票趋势'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.datasetIndex === 1) {
                                label += '¥' + context.raw.toFixed(2);
                            } else {
                                label += context.raw;
                            }
                            return label;
                        }
                    }
                }
            }
        }
    });
}

/**
 * 渲染发票类型分布饼图
 */
function renderTypeChart(data) {
    const ctx = document.getElementById('typeChart').getContext('2d');
    
    // 生成随机颜色数组
    const backgroundColors = data.labels.map(() => {
        return `rgba(${Math.floor(Math.random() * 200)}, ${Math.floor(Math.random() * 200)}, ${Math.floor(Math.random() * 200)}, 0.7)`;
    });
    
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.counts,
                backgroundColor: backgroundColors,
                borderColor: backgroundColors.map(color => color.replace('0.7', '1')),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: '发票类型分布'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw;
                            const total = context.dataset.data.reduce((acc, val) => acc + val, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// 初始化折叠项目功能
document.addEventListener('click', function(e) {
    if (e.target.closest('.toggle-items')) {
        e.preventDefault();
        e.stopPropagation();
        
        const row = e.target.closest('tr');
        const id = row.nextElementSibling.querySelector('.collapse').id;
        const itemsPanel = document.getElementById(id);
        
        // 切换显示状态
        bootstrap.Collapse.getOrCreateInstance(itemsPanel).toggle();
        
        // 更改图标
        const icon = e.target.closest('.toggle-items').querySelector('i');
        if (icon.classList.contains('fa-list')) {
            icon.classList.remove('fa-list');
            icon.classList.add('fa-chevron-up');
        } else {
            icon.classList.remove('fa-chevron-up');
            icon.classList.add('fa-list');
        }
    } else if (e.target.closest('.invoice-row') && !e.target.closest('button') && !e.target.closest('a')) {
        // 当点击发票行时（不包括按钮和链接）
        e.preventDefault();
        
        const row = e.target.closest('tr');
        const id = row.getAttribute('data-target');
        const itemsPanel = document.querySelector(id);
        
        // 切换显示状态
        bootstrap.Collapse.getOrCreateInstance(itemsPanel).toggle();
        
        // 更改展开/折叠按钮图标
        const toggleBtn = row.querySelector('.toggle-items i');
        if (toggleBtn.classList.contains('fa-list')) {
            toggleBtn.classList.remove('fa-list');
            toggleBtn.classList.add('fa-chevron-up');
        } else {
            toggleBtn.classList.remove('fa-chevron-up');
            toggleBtn.classList.add('fa-list');
        }
    }
}); 