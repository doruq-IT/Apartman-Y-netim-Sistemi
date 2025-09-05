document.addEventListener("DOMContentLoaded", function () {
    // Form elemanlarını seç
    const form = document.getElementById("signupForm");
    const passwordInput = document.getElementById("password");
    const confirmPasswordInput = document.getElementById("confirm_password");
    const passwordMismatchMsg = document.getElementById("password-mismatch"); // Bu ID'li bir element HTML'de olmalı
    const acceptTerms = document.getElementById("accept_terms");
    const acceptKvkk = document.getElementById("accept_kvkk");
    const signupBtn = document.getElementById("signupBtn");

    const togglePasswordBtn = document.getElementById('togglePassword');
    const toggleConfirmPasswordBtn = document.getElementById('toggleConfirmPassword');

    // Şifre gösterme/gizleme fonksiyonu
    const setupToggle = (button, input) => {
        if (button && input) {
            button.addEventListener('click', function () {
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                // İkonu değiştir
                const icon = this.querySelector('i');
                icon.classList.toggle('bi-eye');
                icon.classList.toggle('bi-eye-slash');
            });
        }
    };

    setupToggle(togglePasswordBtn, passwordInput);
    setupToggle(toggleConfirmPasswordBtn, confirmPasswordInput);

    // Formun geçerliliğini ve submit butonunun durumunu kontrol eden ana fonksiyon
    const validateForm = () => {
        // Tüm zorunlu text inputların dolu olup olmadığını kontrol et
        let allInputsFilled = true;
        form.querySelectorAll('input[type="text"], input[type="email"], input[type="password"]').forEach(input => {
            if (input.value.trim() === '') {
                allInputsFilled = false;
            }
        });

        const pw = passwordInput.value;
        const cpw = confirmPasswordInput.value;
        const termsChecked = acceptTerms.checked;
        const kvkkChecked = acceptKvkk.checked;

        // Şifreler eşleşiyor mu kontrolü
        const passwordsMatch = pw === cpw;
        // Sadece şifre tekrar alanı doluysa ve eşleşmiyorsa hata göster
        if (cpw.length > 0 && !passwordsMatch) {
            confirmPasswordInput.classList.add("is-invalid");
        } else {
            confirmPasswordInput.classList.remove("is-invalid");
        }

        // Butonun aktif/pasif olma durumu
        // Tüm text alanları dolu, şifreler eşleşiyor ve tüm onay kutuları işaretliyse butonu aktif et
        if (allInputsFilled && passwordsMatch && termsChecked && kvkkChecked) {
            signupBtn.disabled = false;
        } else {
            signupBtn.disabled = true;
        }
    };

    // Formdaki tüm input ve checkbox'lar için olay dinleyicileri ekle
    form.querySelectorAll('input').forEach(element => {
        element.addEventListener('input', validateForm); // Yazı yazarken
        element.addEventListener('change', validateForm); // Checkbox değiştiğinde
    });

    // Sayfa ilk yüklendiğinde de bir kontrol yap
    validateForm();
});
