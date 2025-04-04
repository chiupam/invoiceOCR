document.addEventListener('DOMContentLoaded', function() {
    // 初始化懒加载
    initLazyLoading();
    
    // 初始化图表
    initCharts();
    
    // 处理删除模态框
    setupDeleteModal();
    
    // 处理发票项目显示
    setupItemsToggle();
    
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
});

// 图片懒加载功能
function initLazyLoading() {
    const lazyImages = document.querySelectorAll('img.lazy-load');
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const image = entry.target;
                    image.src = image.dataset.src;
                    image.classList.remove('lazy-load');
                    imageObserver.unobserve(image);
                }
            });
        });
        
        lazyImages.forEach(function(image) {
            imageObserver.observe(image);
        });
    } else {
        // 备用方案：为不支持IntersectionObserver的浏览器提供简单的滚动加载
        let lazyLoadThrottleTimeout;
        
        function lazyLoad() {
            if (lazyLoadThrottleTimeout) {
                clearTimeout(lazyLoadThrottleTimeout);
            }
            
            lazyLoadThrottleTimeout = setTimeout(function() {
                const scrollTop = window.pageYOffset;
                
                lazyImages.forEach(function(img) {
                    if (img.offsetTop < (window.innerHeight + scrollTop)) {
                        img.src = img.dataset.src;
                        img.classList.remove('lazy-load');
                    }
                });
                
                if (lazyImages.length == 0) { 
                    document.removeEventListener('scroll', lazyLoad);
                    window.removeEventListener('resize', lazyLoad);
                    window.removeEventListener('orientationChange', lazyLoad);
                }
            }, 20);
        }
        
        document.addEventListener('scroll', lazyLoad);
        window.addEventListener('resize', lazyLoad);
        window.addEventListener('orientationChange', lazyLoad);
        
        // 立即执行一次，加载视口中的图片
        lazyLoad();
    }
}

// 图表初始化
function initCharts() {
    // 月度数据图表
    try {
        const chartDataElement = document.getElementById('chartData');
        if (chartDataElement) {
            const chartData = JSON.parse(chartDataElement.textContent);
            const ctx = document.getElementById('monthlyChart').getContext('2d');
            
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: '发票数量',
                        data: chartData.counts,
                        backgroundColor: 'rgba(78, 115, 223, 0.5)',
                        borderColor: 'rgba(78, 115, 223, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            precision: 0
                        }
                    }
                }
            });
        }
    } catch (e) {
        console.error('初始化月度图表失败:', e);
    }
    
    // 发票类型分布图表
    try {
        const typeDataElement = document.getElementById('typeData');
        if (typeDataElement) {
            const typeData = JSON.parse(typeDataElement.textContent);
            const ctx = document.getElementById('typeChart').getContext('2d');
            
            if (typeData.labels.length > 0) {
                new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: typeData.labels,
                        datasets: [{
                            data: typeData.counts,
                            backgroundColor: [
                                '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b',
                                '#5a5c69', '#858796', '#6610f2', '#fd7e14', '#20c9a6'
                            ],
                            hoverBackgroundColor: [
                                '#2e59d9', '#17a673', '#2c9faf', '#dda20a', '#be2617',
                                '#3a3b45', '#60616f', '#4e0bc1', '#cc5a00', '#169b81'
                            ],
                            hoverBorderColor: "rgba(234, 236, 244, 1)",
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '70%',
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            } else {
                document.getElementById('typeChart').parentElement.innerHTML = '<div class="text-center py-4 text-muted">暂无类型数据</div>';
            }
        }
    } catch (e) {
        console.error('初始化类型图表失败:', e);
    }
}

// 设置删除模态框
function setupDeleteModal() {
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const type = button.getAttribute('data-type');
            const number = button.getAttribute('data-number');
            
            const modalBody = this.querySelector('.modal-body');
            modalBody.textContent = `您确定要删除${type || ''}发票${number || ''}吗？此操作无法撤销。`;
            
            const form = document.getElementById('deleteForm');
            form.action = `/invoice/${id}/delete`;
        });
    }
}

// 设置发票项目切换
function setupItemsToggle() {
    const toggleBtns = document.querySelectorAll('.toggle-items');
    toggleBtns.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            
            const tr = this.closest('tr');
            const id = tr.getAttribute('data-target');
            const collapse = document.querySelector(id);
            
            if (collapse) {
                const bsCollapse = new bootstrap.Collapse(collapse);
                bsCollapse.toggle();
            }
        });
    });
}

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
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: '价税总额 (元)',
                    data: data.amounts,
                    backgroundColor: 'rgba(28, 200, 138, 0.7)',
                    borderColor: 'rgba(28, 200, 138, 1)',
                    borderWidth: 1,
                    type: 'line',
                    yAxisID: 'y1',
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: 'rgba(28, 200, 138, 1)',
                    pointRadius: 4,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    beginAtZero: true,
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: '发票数量'
                    },
                    ticks: {
                        precision: 0
                    }
                },
                y1: {
                    beginAtZero: true,
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: '价税总额 (元)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.datasetIndex === 1) {
                                label += '¥' + Number(context.raw).toLocaleString('zh-CN', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                });
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