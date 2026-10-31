# Test Planı — EventHub Katkı Aracı

Sürüm: 1.0 · Kapsam: v1 · Dayanak: `docs/requirements.md` (sürüm 1.0)

## 1. Amaç ve kapsam

Bu plan, aracın `docs/requirements.md` dokümanındaki 26 gereksinimi karşıladığını
doğrulamak için izlenecek yaklaşımı tanımlar.

**Test edilecekler:** veri toplama, öğrenci eşleme, puanlama, rehberlik, Excel çıktısı,
gizlilik kuralları.

**Test edilmeyecekler:**
- GitHub ve Taiga'nın kendisi. Dış servislerin yanıtları sahte (mock) verilerle taklit edilir.
- Excel'in formül hesaplama motoru. Formüllerin doğru yazıldığı test edilir; Excel'in
  onları doğru hesapladığı varsayılır.
- Kapsam dışı (v1) özellikler: nitel değerlendirme, web arayüzü.

## 2. Test seviyeleri

| Seviye | Ne test edilir? | Örnek |
|---|---|---|
| Birim | Tek bir fonksiyon, dış bağımlılık olmadan | Ad soyad sadeleştirme, not hesaplama |
| Entegrasyon | Birden fazla bileşenin birlikte çalışması | Taiga CSV'si okunup sayımların doğru çıkması |
| Sistem | Aracın uçtan uca çalışması | Uydurma veriyle Excel üretilip içeriğinin kontrolü |
| Kabul | Gerçek kullanım | Öğretim üyesinin gerçek veriyle çalıştırması (depo dışında, el ile) |

Birim, entegrasyon ve sistem testleri `pytest` ile otomatik çalışır ve her PR'da CI
tarafından koşturulur. Kabul testi gerçek öğrenci verisi gerektirdiği için depoda yer almaz.

## 3. Test tasarım teknikleri

| Teknik | Nerede kullanılır? | Örnek |
|---|---|---|
| Denklik sınıfı bölümleme | Girdinin türüne göre davranış değişen yerler | REQ-2.1: değer e-posta mı, kullanıcı adı mı, boş mu? |
| Sınır değer analizi | Aralık ve eşik içeren kurallar | REQ-1.3: başlangıç − 1 gün, başlangıç, bitiş, bitiş + 1 gün |
| Karar tablosu | Birden fazla koşulun birleştiği kurallar | REQ-3.5: öğrencinin puanı 0 mı × roldeki herkesin puanı 0 mı |
| Hata tahmini | Geçmiş hatalardan ve deneyimden çıkan durumlar | REQ-2.3: "İ/ı" harfleri, fazla boşluk, büyük harfli ad |

**Örnek: REQ-3.4 için sınır değerler** (hedef puan = 10 iken)

| Puan | Beklenen not | Neden |
|---|---|---|
| 0 | 0 | Alt sınır |
| 9,95 | 100 | Yuvarlama sınırı (99,5 → 100) |
| 9,94 | 99 | Yuvarlama sınırının hemen altı |
| 10 | 100 | Hedefe eşit |
| 15 | 100 | Hedefin üstü, 100 ile sınırlanır |

## 4. Test verisi

- Tüm test verisi uydurmadır ve `tests/data/` klasöründe durur (REQ-6.3).
- Öğrenci adları açıkça uydurma olduğu anlaşılacak şekilde seçilir
  (ör. "Test Öğrenci Bir").
- GitHub yanıtları, gerçek API çağrısı yapılmadan JSON dosyalarından okunur.

## 5. Giriş ve çıkış kriterleri

**Bir özelliğin testine başlamak için (giriş):**
- İlgili gereksinimler `docs/requirements.md` dosyasında yazılı ve `main`'e birleşmiş.
- CI yeşil.

**Bir sürümü yayınlamak için (çıkış):**
- Her gereksinimin en az bir geçen testi var (izlenebilirlik tablosu tam).
- Tüm testler geçiyor.
- Açık "yüksek" önemde hata kaydı yok.
- Satır kapsaması en az %80.

## 6. Riskler

| Risk | Tür | Etki | Önlem |
|---|---|---|---|
| Öğrenci yanlış eşleşir, yanlış not alır | Ürün | Yüksek | REQ-2.4 ve REQ-2.5 için testler; her çalıştırmada eşleşme raporu |
| Puanlama formülü hatalı | Ürün | Yüksek | Sınır değer ve karar tablosu testleri |
| Gerçek öğrenci verisi depoya girer | Ürün | Yüksek | `.gitignore`, PR kontrol listesi, REQ-6.x testleri |
| Taiga CSV sütun adları değişir | Ürün | Orta | Sütun adları tek bir yerde tanımlanır; eksik sütun açık hata verir |
| Tek geliştirici olduğu için bağımsız inceleme yok | Proje | Orta | Testler koddan önce gereksinimlerden yazılır; CI zorunlu; PR'da öz inceleme |

## 7. Hata yönetimi

- Her hata bir GitHub issue olarak `bug` etiketiyle açılır: adımlar, beklenen sonuç,
  gerçekleşen sonuç, önem derecesi.
- **Önem dereceleri:** *Yüksek* (yanlış not üretir veya veri sızdırır),
  *Orta* (yanlış rapor ama not doğru), *Düşük* (görünüm, metin).
- Her hata düzeltmesi, o hatayı yakalayan bir regresyon testiyle birlikte birleştirilir.

## 8. İzlenebilirlik

| Gereksinim | Teknik | Test dosyası | Durum |
|---|---|---|---|
| REQ-1.1 | Denklik sınıfı | `tests/test_github_collect.py` | Planlandı |
| REQ-1.2 | Denklik sınıfı | `tests/test_taiga_collect.py` | Planlandı |
| REQ-1.3 | Sınır değer | `tests/test_date_range.py` | Planlandı |
| REQ-1.4 | Denklik sınıfı | `tests/test_github_collect.py` | Planlandı |
| REQ-1.5 | Denklik sınıfı | `tests/test_taiga_collect.py` | Planlandı |
| REQ-1.6 | Hata tahmini | `tests/test_github_collect.py` | Planlandı |
| REQ-2.1 | Denklik sınıfı | `tests/test_students.py` | [x] |
| REQ-2.2 | Denklik sınıfı | `tests/test_matching.py` | [x] |
| REQ-2.3 | Denklik sınıfı, hata tahmini | `tests/test_matching.py` | [x] |
| REQ-2.4 | Hata tahmini (regresyon) | `tests/test_matching.py` | [x] |
| REQ-2.5 | Denklik sınıfı | `tests/test_matching.py` | [x] |
| REQ-3.1 | Sistem testi | `tests/test_excel_output.py` | Planlandı |
| REQ-3.2 | Denklik sınıfı | `tests/test_scoring.py` | Planlandı |
| REQ-3.3 | Sınır değer | `tests/test_scoring.py` | Planlandı |
| REQ-3.4 | Sınır değer | `tests/test_scoring.py` | Planlandı |
| REQ-3.5 | Karar tablosu | `tests/test_scoring.py` | Planlandı |
| REQ-3.6 | Denklik sınıfı | `tests/test_scoring.py` | Planlandı |
| REQ-3.7 | Sınır değer | `tests/test_scoring.py` | Planlandı |
| REQ-4.1 | Denklik sınıfı | `tests/test_guidance.py` | Planlandı |
| REQ-4.2 | Sınır değer | `tests/test_guidance.py` | Planlandı |
| REQ-4.3 | Hata tahmini | `tests/test_guidance.py` | Planlandı |
| REQ-5.1 | Sistem testi | `tests/test_excel_output.py` | Planlandı |
| REQ-5.2 | Sistem testi | `tests/test_excel_output.py` | Planlandı |
| REQ-6.1 | Denklik sınıfı | `tests/test_privacy.py` | Planlandı |
| REQ-6.2 | Denklik sınıfı | `tests/test_privacy.py` | Planlandı |
| REQ-6.3 | Hata tahmini | `tests/test_privacy.py` | Planlandı |

Test yazıldıkça "Durum" sütunu [x] olarak güncellenir.
