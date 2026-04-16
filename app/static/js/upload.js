document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const previewList = document.getElementById('previewList');
    const fileCount = document.getElementById('fileCount');
    const uploadButton = document.getElementById('uploadButton');
    const uploadForm = document.getElementById('uploadForm');
    const progressModal = new bootstrap.Modal(document.getElementById('uploadProgressModal'));
    const uploadProgressBar = document.getElementById('uploadProgressBar');
    const fileListContainer = document.getElementById('fileListContainer');

    let selectedFiles = [];

    dropZone.addEventListener('click', function() {
        fileInput.click();
    });

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

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', function() {
        if (fileInput.files.length) {
            handleFiles(fileInput.files);
        }
    });

    function handleFiles(files) {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fileType = file.type;
            if (!fileType.match('image.*') && fileType !== 'application/pdf') {
                continue;
            }
            const existingFile = selectedFiles.find(f => f.name === file.name);
            if (existingFile) {
                continue;
            }
            selectedFiles.push(file);
        }
        updatePreview();
    }

    function updatePreview() {
        previewList.innerHTML = '';
        fileCount.textContent = selectedFiles.length;
        uploadButton.disabled = selectedFiles.length === 0;

        if (selectedFiles.length === 0) {
            previewContainer.classList.add('d-none');
            return;
        }

        previewContainer.classList.remove('d-none');

        selectedFiles.forEach((file, index) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 col-sm-6 col-6 preview-item';

            if (file.type === 'application/pdf') {
                col.innerHTML = '<div class="card"><div class="card-body text-center">' +
                    '<i class="fas fa-file-pdf fa-3x text-danger"></i>' +
                    '<div class="file-name mt-2">' + file.name + '</div>' +
                    '</div></div><span class="remove-file"><i class="fas fa-times"></i></span>';
            } else {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.className = 'img-fluid';
                    img.alt = file.name;
                    img.onerror = function() {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'alert alert-danger p-2 text-center';
                        errorDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> \u9884\u89c8\u5931\u8d25';
                        img.replaceWith(errorDiv);
                    };
                    const removeBtn = document.createElement('span');
                    removeBtn.className = 'remove-file';
                    removeBtn.innerHTML = '<i class="fas fa-times"></i>';
                    const fileName = document.createElement('div');
                    fileName.className = 'file-name';
                    fileName.textContent = file.name;
                    col.appendChild(img);
                    col.appendChild(removeBtn);
                    col.appendChild(fileName);
                };
                reader.readAsDataURL(file);
            }

            col.querySelector('.remove-file').addEventListener('click', function() {
                selectedFiles.splice(index, 1);
                updatePreview();
            });

            previewList.appendChild(col);
        });
    }

    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        if (selectedFiles.length === 0) {
            return;
        }

        const projectId = document.getElementById('project_id').value;

        if (selectedFiles.length === 1) {
            uploadSingleFile(selectedFiles[0], projectId);
        } else {
            uploadProgressBar.style.width = '0%';
            fileListContainer.innerHTML = '';
            progressModal.show();
            uploadFiles(selectedFiles, projectId);
        }
    });

    function uploadSingleFile(file, projectId) {
        const formData = new FormData();
        formData.append('invoice_file', file);
        if (projectId) {
            formData.append('project_id', projectId);
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]')
            ? document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            : (document.querySelector('input[name="csrf_token"]')
                ? document.querySelector('input[name="csrf_token"]').value
                : '');
        formData.append('csrf_token', csrfToken);

        uploadButton.disabled = true;
        uploadButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>\u8bc6\u522b\u4e2d...';

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(function(response) {
            if (response.redirected) {
                window.location.href = response.url;
                return;
            }
            return response.text().then(function(html) {
                document.open();
                document.write(html);
                document.close();
            });
        })
        .catch(function(error) {
            uploadButton.disabled = false;
            uploadButton.innerHTML = '<i class="fas fa-upload me-2"></i>\u4e0a\u4f20\u5e76\u8bc6\u522b';
            alert('\u4e0a\u4f20\u5931\u8d25\uff1a\u7f51\u7edc\u9519\u8bef');
        });
    }

    function createFileStatusItem(fileName, status) {
        const item = document.createElement('div');
        item.className = 'd-flex align-items-center py-1 file-status-item';
        item.id = 'file-status-' + fileName.replace(/[^a-zA-Z0-9]/g, '_');

        let icon = '';
        let textClass = '';
        if (status === 'waiting') {
            icon = '<i class="fas fa-clock text-muted mr-2"></i>';
            textClass = 'text-muted';
        } else if (status === 'processing') {
            icon = '<i class="fas fa-spinner fa-spin text-primary mr-2"></i>';
            textClass = 'text-primary';
        } else if (status === 'success') {
            icon = '<i class="fas fa-check-circle text-success mr-2"></i>';
            textClass = 'text-success';
        } else if (status === 'error') {
            icon = '<i class="fas fa-times-circle text-danger mr-2"></i>';
            textClass = 'text-danger';
        }

        item.innerHTML = icon + '<span class="' + textClass + ' small">' + fileName + '</span>';
        return item;
    }

    function updateFileStatus(fileName, status, detail) {
        const safeId = 'file-status-' + fileName.replace(/[^a-zA-Z0-9]/g, '_');
        const item = document.getElementById(safeId);
        if (!item) return;

        const newItem = createFileStatusItem(fileName, status);
        if (detail) {
            const detailSpan = document.createElement('span');
            detailSpan.className = 'small ml-2';
            if (status === 'success') {
                detailSpan.classList.add('text-secondary');
            } else {
                detailSpan.classList.add('text-danger');
            }
            detailSpan.textContent = detail;
            newItem.appendChild(detailSpan);
        }
        item.replaceWith(newItem);
    }

    function uploadFiles(files, projectId) {
        let successCount = 0;
        let failCount = 0;
        let lastInvoiceId = null;

        files.forEach(function(file) {
            fileListContainer.appendChild(createFileStatusItem(file.name, 'waiting'));
        });

        const processNext = (index) => {
            if (index >= files.length) {
                setTimeout(function() {
                    const summary = document.createElement('div');
                    summary.className = 'mt-3 pt-2 border-top';
                    const successText = successCount > 0 ? '<span class="text-success">' + successCount + ' \u6210\u529f</span>' : '';
                    const failText = failCount > 0 ? '<span class="text-danger">' + failCount + ' \u5931\u8d25</span>' : '';
                    summary.innerHTML = '<div class="d-flex justify-content-between align-items-center">' +
                        '<div>\u5904\u7406\u5b8c\u6210: ' + successText + (successText && failText ? ' / ' : '') + failText + '</div>' +
                        '<a href="/" class="btn btn-sm btn-primary">\u524d\u5f80\u53d1\u7968\u5217\u8868</a></div>';
                    fileListContainer.appendChild(summary);
                }, 300);
                return;
            }

            const file = files[index];
            updateFileStatus(file.name, 'processing');

            const formData = new FormData();
            formData.append('invoice_file', file);
            if (projectId) {
                formData.append('project_id', projectId);
            }

            const progress = ((index + 1) / files.length) * 100;
            uploadProgressBar.style.width = progress + '%';

            fetch('/upload', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute('content') : (document.querySelector('input[name="csrf_token"]') ? document.querySelector('input[name="csrf_token"]').value : '')
                },
                body: formData
            })
            .then(function(response) {
                return response.json().catch(function() {
                    return { success: false, message: '\u670d\u52a1\u5668\u54cd\u5e94\u683c\u5f0f\u9519\u8bef' };
                });
            })
            .then(function(data) {
                if (data.success) {
                    successCount++;
                    lastInvoiceId = data.invoice_id;
                    var detail = data.invoice_code ? data.invoice_code + data.invoice_number : '';
                    updateFileStatus(file.name, 'success', detail);
                } else {
                    failCount++;
                    var msg = data.message || '\u8bc6\u522b\u5931\u8d25';
                    if (msg.indexOf('\u5df2\u5b58\u5728') !== -1) {
                        msg = '\u53d1\u7968\u5df2\u5b58\u5728';
                    }
                    updateFileStatus(file.name, 'error', msg);
                }
                processNext(index + 1);
            })
            .catch(function(error) {
                failCount++;
                updateFileStatus(file.name, 'error', '\u7f51\u7edc\u9519\u8bef');
                processNext(index + 1);
            });
        };

        processNext(0);
    }
});
