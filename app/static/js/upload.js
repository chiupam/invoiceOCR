document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const previewList = document.getElementById('previewList');
    const fileCount = document.getElementById('fileCount');
    const uploadButton = document.getElementById('uploadButton');
    const uploadForm = document.getElementById('uploadForm');
    const progressModal = new bootstrap.Modal(document.getElementById('uploadProgressModal'));
    const currentFileNum = document.getElementById('currentFileNum');
    const totalFileNum = document.getElementById('totalFileNum');
    const uploadProgressBar = document.getElementById('uploadProgressBar');
    
    // 存储选择的文件
    let selectedFiles = [];
    
    // 点击拖拽区域触发文件选择
    dropZone.addEventListener('click', function() {
        fileInput.click();
    });
    
    // 处理拖拽事件
    ['dragover', 'dragenter'].forEach(function(eventName) {
        dropZone.addEventListener(eventName, function(e) {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });
    
    ['dragleave', 'dragend', 'drop'].forEach(function(eventName) {
        dropZone.addEventListener(eventName, function(e) {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });
    
    // 处理文件拖放
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });
    
    // 处理文件选择
    fileInput.addEventListener('change', function() {
        if (fileInput.files.length) {
            handleFiles(fileInput.files);
        }
    });
    
    // 处理选择的文件
    function handleFiles(files) {
        // 添加新文件到选择的文件列表
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            
            // 检查文件类型
            if (!file.type.match('image.*')) {
                continue;
            }
            
            // 检查是否已经存在相同名称的文件
            const existingFile = selectedFiles.find(f => f.name === file.name);
            if (existingFile) {
                continue;
            }
            
            selectedFiles.push(file);
        }
        
        // 更新预览
        updatePreview();
    }
    
    // 更新预览
    function updatePreview() {
        // 清空预览区域
        previewList.innerHTML = '';
        
        // 更新文件计数
        fileCount.textContent = selectedFiles.length;
        
        // 根据文件数量启用或禁用上传按钮
        uploadButton.disabled = selectedFiles.length === 0;
        
        // 如果没有文件，隐藏预览容器
        if (selectedFiles.length === 0) {
            previewContainer.classList.add('d-none');
            return;
        }
        
        // 显示预览容器
        previewContainer.classList.remove('d-none');
        
        // 为每个文件创建预览
        selectedFiles.forEach((file, index) => {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                const col = document.createElement('div');
                col.className = 'col-md-4 col-sm-6 col-6 preview-item';
                
                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'img-fluid';
                img.alt = file.name;
                
                const removeBtn = document.createElement('span');
                removeBtn.className = 'remove-file';
                removeBtn.innerHTML = '<i class="fas fa-times"></i>';
                removeBtn.addEventListener('click', function() {
                    // 从选择的文件中移除
                    selectedFiles.splice(index, 1);
                    // 更新预览
                    updatePreview();
                });
                
                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = file.name;
                
                col.appendChild(img);
                col.appendChild(removeBtn);
                col.appendChild(fileName);
                previewList.appendChild(col);
            };
            
            reader.readAsDataURL(file);
        });
    }
    
    // 表单提交处理
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (selectedFiles.length === 0) {
            // 静默处理，不弹出提示
            return;
        }
        
        // 准备进度显示
        currentFileNum.textContent = '0';
        totalFileNum.textContent = selectedFiles.length;
        uploadProgressBar.style.width = '0%';
        
        // 显示进度模态框
        progressModal.show();
        
        // 获取项目ID
        const projectId = document.getElementById('project_id').value;
        
        // 批量上传处理
        uploadFiles(selectedFiles, projectId);
    });
    
    // 批量上传文件
    function uploadFiles(files, projectId) {
        let successCount = 0;
        let failCount = 0;
        let completed = 0;
        let lastInvoiceId = null;
        
        // 顺序处理每个文件
        const processNext = (index) => {
            if (index >= files.length) {
                // 所有文件处理完成
                setTimeout(() => {
                    progressModal.hide();
                    
                    // 直接重定向，不显示弹窗
                    if (lastInvoiceId) {
                        window.location.href = `/invoice/${lastInvoiceId}`;
                    } else {
                        window.location.href = '/';
                    }
                }, 500);
                return;
            }
            
            const file = files[index];
            const formData = new FormData();
            formData.append('invoice_file', file);
            if (projectId) {
                formData.append('project_id', projectId);
            }
            
            // 更新进度显示
            currentFileNum.textContent = (index + 1).toString();
            const progress = ((index + 1) / files.length) * 100;
            uploadProgressBar.style.width = `${progress}%`;
            
            // 发送请求
            fetch('/upload', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(response => {
                console.log('上传返回状态:', response.status);
                return response.json().catch(error => {
                    console.error('解析JSON失败:', error);
                    return { success: false, message: '服务器响应格式错误' };
                });
            })
            .then(data => {
                console.log('收到响应数据:', data);
                completed++;
                
                if (data.success) {
                    successCount++;
                    lastInvoiceId = data.invoice_id;
                } else {
                    failCount++;
                    console.error('上传失败:', data.message);
                }
                
                // 处理下一个文件
                processNext(index + 1);
            })
            .catch(error => {
                console.error('上传错误:', error);
                completed++;
                failCount++;
                
                // 处理下一个文件
                processNext(index + 1);
            });
        };
        
        // 开始处理第一个文件
        processNext(0);
    }
}); 