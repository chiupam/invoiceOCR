document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const uploadButton = document.getElementById('uploadButton');
    
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
            fileInput.files = e.dataTransfer.files;
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
        const file = files[0];
        
        // 检查文件类型
        if (!file.type.match('image.*')) {
            alert('请选择图片文件!');
            return;
        }
        
        // 显示预览
        const reader = new FileReader();
        reader.onload = function(e) {
            imagePreview.src = e.target.result;
            previewContainer.classList.remove('d-none');
            uploadButton.disabled = false;
        };
        reader.readAsDataURL(file);
    }
    
    // 表单提交时显示加载状态
    document.getElementById('uploadForm').addEventListener('submit', function(e) {
        uploadButton.disabled = true;
        uploadButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 处理中...';
    });
}); 