# Mimari (Özet)

ClarityAI; Streamlit tabanlı bir arayüz, Pydantic ile tanımlanan audit modeli ve plugin mimarisi üzerine kurulu, denetim odaklı bir analiz aracıdır.

Ana akış:
1) Kullanıcı CSV dosyalarını yükler (opsiyonel kolon eşleştirme + referans dosyaları).
2) Engine ilgili plugin'i çağırır ve adımları Kanıt Defteri'ne yazar.
3) Rapor ve çıktılar (PDF/CSV/JSON) run klasörüne kaydedilir.
4) Onay verilirse düzeltmeler uygulanır ve audit güncellenir.

Bileşenler:
- app/: Streamlit UI (sayfalar + stil + menü)
- core/: Audit, schema, storage, IO, LLM, engine
- plugins/: Demo kuralları ve çıktı üreten eklentiler

Basit akış diyagramı:

Kullanıcı -> UI -> Engine -> Plugin Kuralları
                       |-> Audit Trail (Kanıt Defteri)
                       |-> Çıktılar (PDF/CSV/JSON)
