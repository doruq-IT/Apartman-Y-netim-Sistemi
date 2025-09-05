document.addEventListener('DOMContentLoaded', function () {
    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewWrapper = document.getElementById('file-preview-wrapper');
    const uploadPrompt = document.getElementById('upload-prompt');
    const uploadForm = document.getElementById('documentUploadForm');
    const submitButton = document.getElementById('submit-button');
    const loadingSpinner = document.getElementById('loading-spinner');
    const submitIcon = document.getElementById('submit-icon');
    const submitText = document.getElementById('submit-text');

    // Eğer sayfada bu elementler yoksa, JS kodunu çalıştırma.
    if (!dropZone || !fileInput || !uploadForm) {
        return;
    }

    // 1. Tıklama Olayı: dropZone'a tıklandığında gizli fileInput'u tetikle.
    dropZone.addEventListener('click', (e) => {
        // Eğer kullanıcı zaten bir dosya seçtiyse ve önizlemedeki bir linke tıklıyorsa
        // fileInput'u tekrar açma. Sadece ana yükleme alanına tıklarsa aç.
        if (e.target.id === 'file-drop-zone' || e.target.closest('#upload-prompt')) {
             fileInput.click();
        }
    });

    // 2. Dosya Seçim Olayı: Kullanıcı pencereden dosya seçtiğinde.
    fileInput.addEventListener('change', function () {
        if (this.files && this.files.length > 0) {
            handleFile(this.files[0]);
        }
    });

    // 3. Tarayıcının varsayılan "dosyayı açma" davranışını global olarak engelle.
    // Bu, en kritik adımdır.
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        window.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // 4. Sürükleme alanına görsel geri bildirim ekle.
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('border-primary', 'bg-light');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('border-primary', 'bg-light');
        }, false);
    });

    // 5. Dosya Bırakıldığında: Bırakılan dosyayı al ve işle.
    dropZone.addEventListener('drop', (e) => {
        // e.preventDefault() ve e.stopPropagation() zaten globalde çağrıldı.
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files && files.length > 0) {
            fileInput.files = files; // Bırakılan dosyayı gizli input'a atıyoruz ki form ile gönderilebilsin.
            handleFile(files[0]);
        }
    }, false);

    // Form gönderildiğinde yükleme animasyonunu göster.
    uploadForm.addEventListener('submit', () => {
        // Formun geçerli olup olmadığını kontrol et
        if(form.checkValidity()) {
            submitButton.disabled = true;
            loadingSpinner.style.display = 'inline-block';
            submitIcon.style.display = 'none';
            submitText.innerText = 'Yükleniyor...';
        }
    });

    // Seçilen dosyayı işleyen ve önizleme oluşturan fonksiyon.
    function handleFile(file) {
        uploadPrompt.style.display = 'none';
        previewWrapper.style.display = 'block';
        previewWrapper.innerHTML = ''; // Önceki önizlemeyi temizle

        const fileType = file.type;
        const fileName = file.name;
        const fileSize = (file.size / 1024 / 1024).toFixed(2); // MB cinsinden

        let previewElement;

        if (fileType.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function (e) {
                previewElement = `
                    <img src="${e.target.result}" class="img-fluid rounded" style="max-height: 150px;" alt="Dosya Önizlemesi">
                    <p class="mt-2 mb-0 fw-bold">${fileName}</p>
                    <p class="text-muted small">${fileSize} MB</p>
                `;
                previewWrapper.innerHTML = previewElement;
            }
            reader.readAsDataURL(file);
        } else if (fileType === 'application/pdf') {
            previewElement = `
                <i class="bi bi-file-earmark-pdf-fill text-danger" style="font-size: 4rem;"></i>
                <p class="mt-2 mb-0 fw-bold">${fileName}</p>
                <p class="text-muted small">${fileSize} MB</p>
            `;
            previewWrapper.innerHTML = previewElement;
        } else {
            previewElement = `
                <i class="bi bi-file-earmark-text-fill text-secondary" style="font-size: 4rem;"></i>
                <p class="mt-2 mb-0 fw-bold">${fileName}</p>
                <p class="text-muted small">${fileSize} MB</p>
            `;
            previewWrapper.innerHTML = previewElement;
        }
    }
});
