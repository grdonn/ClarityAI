# ClarityAI — Kanıt Defteri (Audit Trail) Odaklı Denetim Asistanı

⚡ Denetim, onay ve rapor üretimini tek ekranda birleştiren pratik analiz platformu.

![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2ea44f)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-ff4b4b)

## 🔥 Neden farklı?

- **Kanıt Defteri odaklı:** Her adımı, kanıtı ve kararı kayıt altına alır.
- **Onaylı düzeltme:** “Öneri üretir, onay olmadan uygulamaz.”
- **Gerçek dosya uyumu:** Kolon eşleştirme + şema doğrulama ile sahaya hazır.

## 🚀 1 Dakikada Demo

Yeni Çalıştırma → Demo seç → Dosya yükle/Örnek → Kolon eşleştir → Kontrolleri çalıştır → Sonuç indir → Onayla & Uygula

## 🧾 Kanıt Defteri nedir?

- Adım adım denetim kaydı oluşturur.
- Karar + kanıt birlikte tutulur.
- Uygulama öncesi onay mekanizması sağlar.

## ✨ Özellikler

- Kanıt Defteri (Audit Trail)
- Kolon eşleştirme + şema doğrulama
- PDF/CSV çıktıları
- Offline/OpenAI opsiyonel kullanım
- Plugin tabanlı mimari

## 🖼️ Ekran Görüntüleri

> Not: Görseller `docs/screenshots/` altında durur.

### Ana Sayfa
![Ana Sayfa](docs/screenshots/home.png)

### Yeni Çalıştırma
![Yeni Çalıştırma](docs/screenshots/run.png)

### Sonuçlar
![Sonuçlar](docs/screenshots/results.png)

### Geçmiş
![Geçmiş](docs/screenshots/history.png)


## 🧰 Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## ▶️ Çalıştırma

```bash
streamlit run app/Home.py
```

Testler:

```bash
python3 -m pytest -q
```

## 🔐 OpenAI Anahtarı (Opsiyonel)

```bash
cp .env.example .env
```

`.env` içine:

```
OPENAI_API_KEY=your_key_here
```

- Varsayılan mod: Offline
- OpenAI, ayarlardan opsiyonel açılır.
- **Güvenlik:** `.env` git’e girmez, anahtar asla repoya konmaz.
- Deploy aşamasında secrets kullanılması önerilir.

## 📄 Veri Formatları

**Ticket Demo (zorunlu):**
- `ticket_id`, `created_at`, `channel`, `customer_text`
- Opsiyonel: `category`, `order_id`, `amount`

**e-Belge Demo:**
- `invoices.csv`, `purchase_orders.csv`, `delivery_notes.csv`
- Kolon eşleştirme ile farklı isimler desteklenir.

## 🧠 Mimari

- `core/`: audit, schema, storage, LLM, engine
- `plugins/`: demo kuralları ve çıktı üretimi
- `app/`: Streamlit arayüzü

Detay: `docs/architecture.md`

## 📌 CV’ye yazmalık

- Kanıt Defteri temelli denetim akışı ve onaylı düzeltme tasarımı
- Pydantic şema doğrulama + kolon eşleştirme ile veri uyumluluğu
- Streamlit tabanlı, rapor üreten, modüler plugin mimarisi

Lisans: No license / all rights reserved
