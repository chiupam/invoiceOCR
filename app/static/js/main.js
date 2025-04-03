document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('file');
            if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                showAlert('请选择要上传的文件', 'danger');
                return;
            }
            
            const file = fileInput.files[0];
            
            // 验证文件类型
            const allowedTypes = ['image/jpeg', 'image/png', 'application/pdf'];
            if (!allowedTypes.includes(file.type)) {
                showAlert('请上传 JPG、PNG 或 PDF 格式的文件', 'danger');
                return;
            }
            
            // 验证文件大小（10MB）
            const maxSize = 10 * 1024 * 1024; // 10MB
            if (file.size > maxSize) {
                showAlert('文件大小不能超过 10MB', 'danger');
                return;
            }
            
            const formData = new FormData();
            formData.append('invoice_file', file);
            
            // 获取项目ID
            const projectSelect = document.getElementById('project');
            if (projectSelect && projectSelect.value) {
                formData.append('project_id', projectSelect.value);
            }
            
            // 显示加载状态
            const submitButton = this.querySelector('button[type="submit"]');
            const originalText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = '处理中...';
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`服务器响应错误: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showAlert('发票上传成功！', 'success');
                    // 重定向到发票详情页
                    if (data.invoice_id) {
                        setTimeout(() => {
                            window.location.href = `/invoice/${data.invoice_id}`;
                        }, 1500);
                    } else {
                        // 如果没有获得发票ID，则刷新页面
                        setTimeout(() => window.location.reload(), 1500);
                    }
                } else {
                    showAlert(data.message || '上传失败，请重试', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('上传失败: ' + error.message, 'danger');
            })
            .finally(() => {
                // 恢复按钮状态
                submitButton.disabled = false;
                submitButton.textContent = originalText;
            });
        });
    }
    
    // 显示提示消息
    window.showAlert = function(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        const container = document.querySelector('.container-fluid');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            setTimeout(() => {
                alertDiv.remove();
            }, 3000);
        }
    };
}); 