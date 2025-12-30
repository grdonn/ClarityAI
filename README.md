# ClarityAI

Denetim odaklı dosya inceleme ve onaylı düzeltme platformu.

## Neler yapar?

- Kanıt Defteri: her adımı, kanıtı ve gerekçeyi kaydeder.
- Kolon Eşleme: gerçek dünya CSV'leriyle hızlı uyum sağlar.
- Onayla ve Uygula: otomatik öneri, insan onayı ile düzeltme.
- PDF/CSV/JSON: rapor, issue listesi ve özet çıktılar üretir.
- Offline/OpenAI: API anahtarı yoksa offline çalışır, opsiyonel LLM desteği sunar.
- Demo mimarisi: Ticket ve e-Belge denetimi için eklenti yapısı.

## Ekran görüntüleri

Ekran görüntülerini `docs/screenshots/` altına koyabilirsiniz.

- `docs/screenshots/home.png` (Ana Sayfa)
- `docs/screenshots/run.png` (Yeni Çalıştırma + Eşleme)
- `docs/screenshots/results.png` (Sonuçlar + Çıktılar)
- `docs/screenshots/history.png` (Geçmiş + Kanıt Defteri)

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/Home.py
```

## Kullanım

### Demo 1: Talep / İade / İstek İncelemesi

1) Ana Sayfa'da demo seçin.
2) `tickets.csv` yükleyin veya örnek veri seçin.
3) (Varsa) Kolon Eşleme yapın.
4) Kontrolleri çalıştırın ve raporu indirin.

### Demo 2: e-Belge Denetimi

1) Ana Sayfa'da demo seçin.
2) `invoices.csv`, `purchase_orders.csv`, `delivery_notes.csv` yükleyin.
3) (Opsiyonel) Referans dosyalarını ekleyin.
4) Kontrolleri çalıştırın ve issue/raporu indirin.

## OpenAI modu

- Varsayılan: Offline (API anahtarı yoksa otomatik).
- Opsiyonel: OpenAI aktif etmek için Settings sayfasından toggle açın.
- `.env` dosyasına `OPENAI_API_KEY` ekleyin.

## Güvenlik notları

- `.env` asla repoya eklenmez.
- `runs/` klasörü lokaldir ve çalışma verilerini içerir.

## Mimari

- Kısa özet için: `docs/architecture.md`

## Roadmap

- Basit deployment (Docker + tek komut yayın)
- LLM provider seçimi ve yönetimi
- Ek kurallar ve sektör bazlı kontrol paketleri
