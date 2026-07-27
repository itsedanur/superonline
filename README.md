# Superonline AI Complaint Intelligence Platform

Kurumsal şikâyet yönetimi, AI destekli ürün & duygu analizi, otomatik tarama (scraping) ve C-Level Yönetici Paneli sunan uçtan uca müşteri deneyimi ve operasyonel risk analiz platformudur.

---

## 📌 Proje Özeti

Turkcell Superonline müşteri geri bildirimlerini ve kamuya açık müşteri şikâyetlerini (PoC kapsamında Şikayetvar vb.) otomatik toplayıp işleyen bu platform; **Fiber**, **ADSL** ve **Superbox** ana ürün grupları bazında kategorizasyon, duygu (sentiment) tespiti, aciliyet derecelendirmesi ve çoklu ürün çelişki tespitleri gerçekleştirir.

---

## 🔥 Temel Özellikler

* **Ürün Bazlı Otomatik Sınıflandırma (Fiber / ADSL / Superbox)**:
  * Şikâyet metni, başlığı ve kaynak sayfa verilerinden ürün tespiti.
  * Hibrid Kural Motoru + LLM Bağlam Analizi ile %95+ doğruluk.
* **Mod Bazlı Veri Toplama (INCREMENTAL & BACKFILL)**:
  * **INCREMENTAL Modu**: Her zaman 1. sayfadan başlayarak en son gelen yeni şikâyetleri tarar. Önceden veritabanına eklenmiş kayıtları duplicate olarak işaretler ve veritabanını güncel tutar.
  * **BACKFILL Modu**: Geçmişe dönük veri tamamlama talamalarında checkpoint (`next_page`) mekanizmasını kullanarak kaldığı sayfadan devam eder, tekrarlı taramayı önler.
* **Manuel İnceleme Kuyruğu (Review Queue - Phase 2.2)**:
  * AI tespit güven puanı düşük (`confidence < 0.70`) veya ürün kaynak çelişkisi (`product_conflict=true`) bulunan kayıtları operatör onayına yönlendirir.
* **Detaylı Scrape Run İzlenebilirliği (Run Detail Ekranı)**:
  * Her bir tarama turunda HTTP durum kodları, taranan benzersiz URL'ler, DB duplication sebepleri (`DB_CANONICAL_URL_MATCH`, `DB_EXTERNAL_ID_MATCH`, `CROSS_PAGE_DUPLICATE`) ve durma nedenleri (`STOPPED_DUPLICATE_THRESHOLD`, `COMPLETED_PAGE_LIMIT`) raporlanır.
* **Yönetici Paneli & AI İçgörü Motoru (Executive Dashboard - Phase 3)**:
  * C-Level yöneticiler için dönemsel (% günlük/haftalık/aylık) şikâyet artış oranları.
  * En çok ivme kazanan sorun başlıkları (*Top 5 Surging Issues*).
  * NLP motoru tarafından üretilen otomatik risk uyarıları ve stratejik eylem önerileri.

---

## 🏗️ Proje Dizin Yapısı

```
.
├── Dockerfile                  # Container imaj yapısı
├── docker-compose.yml          # Multi-container orchestration (App & Postgres)
├── app.js                      # Modern Frontend Vanilla JS SPA mantığı
├── index.html                  # Single Page Application HTML yapısı
├── styles.css                  # Modern Dark-Mode & Glassmorphism stil sistemi
├── server.py                   # Python REST API Server (http.server / WSGI)
├── database.py                 # SQLite / PostgreSQL Veritabanı Erişim & Migration Katmanı
├── scraper.py                  # HTTP Resilient Multi-strategy Scraper Engine
├── nlp_engine.py               # Hybrid Rule-Based & LLM AI Classification Engine
├── requirements.txt            # Python bağımlılıkları
├── run.sh                      # Uygulama başlatma betiği
├── .env.example                # Örnek ortam değişkenleri şablonu
└── .gitignore                  # Git dışlama kuralları
```

---

## ⚙️ Docker ile Kurulum ve Çalıştırma

### 1. Yerel Kurulum (Python)

```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Uygulama sunucusunu başlatın (Port: 8080)
python3 server.py
```

Tarayıcınızdan `http://localhost:8080` adresine gidin.

### 2. Docker & Docker Compose ile Kurulum

```bash
# Docker imajını derleyin ve başlatın
docker-compose up -d --build
```

Kapsayıcı çalıştıktan sonra uygulama veritabanı schema ve migration adımlarını otomatik olarak çalıştırır.

---

## 🌐 Ortam Değişkenleri (.env)

Projede varsayılan konfigürasyonlar `.env.example` dosyasında tanımlanmıştır:

| Değişken | Açıklama | Varsayılan |
| :--- | :--- | :--- |
| `APP_ENV` | Çalışma ortamı (`development` / `production`) | `development` |
| `APP_PORT` | HTTP Port numarası | `8080` |
| `DB_TYPE` | Veritabanı türü (`sqlite` / `postgres`) | `sqlite` |
| `DATABASE_PATH` | SQLite veritabanı dosya yolu | `superonline_enterprise.db` |
| `ENABLE_PUBLIC_WEB_PROTOTYPE` | Web canlı analiz sekmesi izni | `false` |
| `OPENAI_API_KEY` | Opsiyonel LLM Bağlam Analizi API Anahtarı | `-` |

---

## 🔌 REST API Endpoint Özeti

* `GET /api/v1/stats`: Genel KPI istatistikleri ve ürün dağılımları.
* `GET /api/v1/complaints`: Filtrelenebilir ve sayfalanabilir şikâyet listesi.
* `POST /api/v1/prototype-scrape`: Asenkron tarama (scraper) başlatma endpoint'i.
* `GET /api/v1/scrape-runs/{run_id}`: Tarama detay raporu ve sayfa bazlı URL metrikleri.
* `GET /api/v1/review-queue`: İnceleme bekleyen şikâyet kayıtları.
* `POST /api/v1/review-queue/{id}/approve`: AI kararını onaylama.
* `POST /api/v1/review-queue/{id}/correct`: Manuel ürün düzeltme.
* `POST /api/v1/analyze`: Metin bazlı canlı AI sınıflandırma ve bağlam analizi.
* `GET /api/v1/executive/summary`: Yönetici Paneli dönemsel büyüme ve AI içgörü özeti.
* `GET /api/v1/executive/trends`: 30 günlük zaman serisi trend verileri.

---

## 🧪 Test Komutları

Uygulamanın e2e ve modül testlerini çalıştırmak için:

```bash
# Uçtan uca tarama ve pagination testi
python3 test_e2e_pagination.py

# Mod bazlı checkpoint ve incremental/backfill testi
python3 verify_modes_checkpoint.py

# AI Ürün Sınıflandırıcı doğrulaması
python3 test_product_classifier.py
```

---

## 🚨 Önemli Yasal ve Teknik Uyarılar (KVKK & PoC Kapsamı)

1. **PoC (Proof of Concept) Amacı**:
   Bu projedeki Web Scraper modülü yalnızca konsept kanıtlama (PoC) ve gösterim amaçlı geliştirilmiştir. Şikayetvar veya diğer kamuya açık platformlardan çekilen veriler örnek niteliğindedir.
2. **Üretim Ortamı Entegrasyonu**:
   Üretim (Production) ortamında veri toplamak için canlı web scraping yerine Turkcell Superonline kurumsal CRM, Çağrı Merkezi (IVR), Mobil Uygulama Geri Bildirim API'leri veya resmi sosyal medya API entegrasyonları kullanılmalıdır.
3. **KVKK ve Veri Gizliliği**:
   Proje GitHub deposuna gerçek veritabanı kayıtları, müşteri kişisel verileri (PII), API anahtarları veya oturum çerezleri **kesinlikle yüklenmemektedir**. Veritabanı başlatma mekanizması boş şema ile çalışır.

---

## 📄 Lisans

License: Not specified
