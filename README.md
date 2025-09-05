# FlatNet - Apartman Yönetim Sistemi (AYS) 🏢

**Modern, Şeffaf ve Kolay Apartman Yönetimi**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-black?style=for-the-badge&logo=flask)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

[cite_start]Bu proje, apartman ve sitelerdeki finansal ve sosyal süreçleri dijitalleştiren, yönetici ile sakinler arasındaki iletişimi güçlendiren modern bir web uygulamasıdır. [cite: 3] [cite_start]Aidat takibi, masraf yönetimi, online makbuz onayı, talep/şikayet yönetimi ve anket gibi temel işlevleri tek bir çatı altında toplar. [cite: 4]

---

## ✨ Görsel Galerisi

<table>
  <tr>
    <td align="center"><strong>Ana Sayfa</strong></td>
    <td align="center"><strong>Yönetici Paneli</strong></td>
  </tr>
  <tr>
    <td><img src="https://i.imgur.com/G5n9Ndq.png" alt="Ana Sayfa Ekran Görüntüsü"></td>
    <td><img src="https://i.imgur.com/UfT3Y7q.png" alt="Yönetici Paneli Ekran Görüntüsü"></td>
  </tr>
  <tr>
    <td align="center"><strong>Sakin Paneli</strong></td>
    <td align="center"><strong>Anket Sonuçları</strong></td>
  </tr>
  <tr>
    <td><img src="https://i.imgur.com/pA1191z.png" alt="Sakin Paneli Ekran Görüntüsü"></td>
    <td><img src="https://i.imgur.com/gK6kGg0.png" alt="Anket Sonuçları Ekran Görüntüsü"></td>
  </tr>
</table>

---

## 🚀 Temel Özellikler

[cite_start]Proje, görev ve yetki ayrımını sağlamak için üç farklı kullanıcı rolü üzerine kurulmuştur: **Süper Yönetici**, **Yönetici** ve **Sakin**. [cite: 44]

### 👑 Yönetici (Admin) Özellikleri
- [cite_start]**📊 Kapsamlı Dashboard:** Bekleyen talepler, toplam sakin sayısı, onay bekleyen makbuzlar ve aylık gelir gibi önemli istatistikleri tek bakışta görme. [cite: 68]
- [cite_start]**📈 Finansal Grafik:** Son 6 ayın gelir-gider durumunu gösteren interaktif çubuk grafik. [cite: 69]
- [cite_start]**💰 Aidat ve Ödeme Yönetimi:** Tüm sakinler veya tek bir sakin için aidat borcu oluşturma ve e-posta ile bildirim gönderme. [cite: 79, 80]
- [cite_start]**🧾 Makbuz Onay Sistemi:** Sakinlerin yüklediği ödeme makbuzlarını inceleme ve tek tıkla onaylama. [cite: 81] [cite_start]Onaylanan ödeme otomatik olarak kasaya gelir olarak işlenir. [cite: 82]
- [cite_start]**💸 Masraf Yönetimi:** Apartman için yapılan ortak harcamaları (faturasıyla birlikte) sisteme kaydetme. [cite: 84]
- [cite_start]**📋 PDF Raporlama:** Belirtilen tarih aralığı için tüm gelir-gider kalemlerini içeren detaylı ve resmi finansal raporu PDF formatında oluşturma. [cite: 88]
- [cite_start]**📢 Duyuru ve Anket Yönetimi:** Site geneli için duyurular yayınlama ve ortak kararlar için anketler oluşturup sonuçlarını takip etme. [cite: 95, 96]
- [cite_start]**💬 Talep Yönetimi:** Sakinlerden gelen istek/şikayet taleplerini yanıtlama ve durumunu ("İşlemde", "Tamamlandı" vb.) güncelleme. [cite: 76]

### 🏠 Sakin (Resident) Özellikleri
- [cite_start]**💳 Aidat Takibi:** Kendisine atanan tüm aidat borçlarını, son ödeme tarihlerini ve ödeme durumlarını görüntüleme. [cite: 108]
- [cite_start]**📄 Makbuz Yükleme:** Yapılan ödemelere ait dekontları (PDF veya resim) sisteme kolayca yükleme. [cite: 109]
- [cite_start]**💡 Talep Oluşturma ve Takip:** Yönetime iletmek istediği istek, şikayet veya önerileri oluşturma ve kendi taleplerinin güncel durumunu takip etme. [cite: 113, 114]
- **🔍 Tam Şeffaflık:**
    - [cite_start]**Genel Giderler:** Yönetimin yaptığı tüm ortak harcamaları ve faturalarını şeffaf bir şekilde görme. [cite: 118]
    - [cite_start]**Kasa Durumu:** Apartmanın anlık kasa bakiyesini ve tüm para giriş-çıkış işlemlerini bir "işlem defteri" gibi görüntüleme. [cite: 119]
    - [cite_start]**Aidat Panosu:** Apartmandaki tüm sakinlerin aidat ödeme durumlarını "ÖDENDİ" / "ÖDENMEDİ" şeklinde gösteren panoyu görme. [cite: 120]
- [cite_start]**🗳️ Anketlere Katılım:** Yönetim tarafından oluşturulan anketlere oy verme ve sonuçlarını şeffaf bir şekilde görüntüleme. [cite: 143, 147]

### 🔑 Süper Yönetici (Superadmin) Özellikleri
- [cite_start]**👤 Kullanıcı ve Rol Yönetimi:** Sistemdeki tüm kullanıcıları listeleme ve kullanıcıların rollerini `admin` veya `resident` olarak atama/değiştirme. [cite: 56, 58]

---

## 🛠️ Kullanılan Teknolojiler

| Kategori | Teknoloji |
|---|---|
| **Backend** | `Python`, `Flask` |
| **Veritabanı** | `Google Cloud MySQL` |
| **Frontend** | `HTML`, `CSS`, `JavaScript`, `Bootstrap` |
| **Deployment** | `Google Cloud App Engine`, `Gunicorn` |
| **Servisler** | `Firebase (Push Bildirimleri)`, `Google Cloud Cron (Zamanlanmış Görevler)` |

---

## 🔌 Kurulum ve Çalıştırma (Yerel Ortam İçin)

Projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyebilirsiniz:

1.  **Repoyu klonlayın:**
    ```bash
    git clone [https://github.com/doruq-IT/Apartman-Yonetim-Sistemi(https://github.com/doruq-IT/Apartman-Yonetim-Sistemi.git)
    cd PROJE-ADI
    ```
    2.  **Sanal ortam oluşturun ve aktif edin:**
    ```bash
    python -m venv venv
    # Windows için
    venv\Scripts\activate
    # macOS/Linux için
    source venv/bin/activate
    ```

3.  **Gerekli kütüphaneleri yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ortam değişkenlerini ayarlayın:**
    - `.env.example` adında bir dosya oluşturarak gerekli değişkenleri (veritabanı bağlantısı, secret key vb.) belirtin.
    - Bu dosyayı `.env` olarak kopyalayıp kendi yerel bilgilerinizle doldurun.

5.  **Uygulamayı çalıştırın:**
    ```bash
    flask run
    ```

---

## 📬 İletişim

**Okan Kurtar**

- **GitHub:** [okankurtar](https://github.com/doruq-IT)
- **LinkedIn:** [Okan Kurtar](https://www.linkedin.com/in/okan-k-224646138)
