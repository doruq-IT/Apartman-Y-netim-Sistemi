// Bu kod, web sayfası tamamen yüklendiğinde otomatik olarak çalışır.
document.addEventListener('DOMContentLoaded', function() {
    
    // Moment.js kütüphanesinin dilini Türkçe olarak ayarlıyoruz.
    // Bu sayede "August" yerine "Ağustos" gibi Türkçe aylar kullanılır.
    moment.locale('tr');

    // HTML içinde "utc-date" sınıfına sahip tüm elementleri bulup bir listeye atıyoruz.
    const dateElements = document.querySelectorAll('.utc-date');

    // Bulduğumuz her bir tarih elementi için aşağıdaki işlemleri sırayla yapıyoruz.
    dateElements.forEach(function(element) {
        
        // Elementin içindeki UTC tarih metnini alıyoruz. Örnek: "2025-08-14T20:08:22.123456"
        const utcDateString = element.textContent.trim();

        // Eğer elementin içinde bir tarih metni varsa...
        if (utcDateString) {
            
            // Moment.js kullanarak UTC formatındaki tarihi alıp, .local() fonksiyonu ile
            // kullanıcının tarayıcısının anlık saat dilimine dönüştürüyoruz.
            const localDate = moment.utc(utcDateString).local();

            // Dönüştürdüğümüz bu yerel tarihi, herkesin anlayacağı güzel bir formata çeviriyoruz.
            // Örnek Çıktı: "14 Ağustos 2025 Perşembe, 23:08"
            const formattedDate = localDate.format('DD MMMM YYYY dddd, HH:mm');

            // Son olarak, eski UTC tarihinin yerine bu yeni, formatlanmış yerel tarihi yazıyoruz.
            element.textContent = formattedDate;
        }
    });
});