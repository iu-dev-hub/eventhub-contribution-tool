# Gereksinimler — EventHub Katkı Aracı

Sürüm: 1.10 · Kapsam: v1 (nicel değerlendirme)

Bu doküman, aracın ne yapması gerektiğini tanımlar. Her gereksinim test edilebilir
yazılmıştır ve bir kimlik numarası (REQ-x.y) taşır. Testler bu numaralara atıf yapar.

## Terimler

- **Öğrenci listesi:** Öğretim üyesinin hazırladığı, öğrenci başına ad soyad, rol ve
  e-posta ya da kullanıcı adı içeren CSV dosyası.
- **Hesap:** Bir öğrencinin GitHub veya Taiga kullanıcı adı. Bir öğrencinin birden
  fazla hesabı olabilir.
- **Rol:** Product Owner, Scrum Master, Back, Front, Testçi. Rol her rol döneminde değişir.
- **Rol medyanı:** Aynı roldeki öğrencilerin bir ölçüt veya puan için medyan değeri.

## 1. Veri toplama

**REQ-1.1** Araç, GitHub'daki depodan şunları okur: açılan ve birleşen PR'lar, PR
incelemeleri, inceleme yorumları, Discussions konu, yorum ve yanıtları.

**REQ-1.2** Araç, Taiga'nın CSV dışa aktarımından kullanıcı hikâyelerini, görevleri ve
hata kayıtlarını okur. CSV bir dosya yolu veya bağlantı olarak verilebilir.

**REQ-1.3** Bir tarih aralığı verildiğinde yalnızca o aralıktaki etkinlikler sayılır.
Başlangıç ve bitiş günleri aralığa dahildir. Tarihler Türkiye saatine (UTC+3) göre
değerlendirilir.

**REQ-1.4** Bot hesaplarının (`[bot]` ile biten adlar) etkinlikleri sayılmaz.

**REQ-1.5** Durumu "Reddedildi" olan hata kayıtları sayılmaz.

**REQ-1.6** Bir öğrencinin kendi PR'ına yaptığı inceleme, kod incelemesi olarak sayılmaz.

**REQ-1.7** Araç, Taiga CSV dışa aktarımındaki her kullanıcı hikâyesi, görev ve hata
kaydının değişiklik geçmişini Taiga API'sinden indirir. Kayıtlar CSV'deki `id`
sütunuyla bulunur.

**REQ-1.8** Bir kullanıcı hikâyesinin durumunu "bitti" grubundaki bir duruma (Bitti,
Done, Kapandı, Closed) geçiren kullanıcı için bir hikâye kabulü sayılır. Bitti
grubundaki bir durumdan bu gruptaki başka bir duruma geçiş sayılmaz. Görev ve hata
kayıtlarının durum değişiklikleri bu ölçüte girmez.
*Kaynak: kabul testinde, hikâyeleri test edip "Done" durumuna alan bir testçinin Taiga
CSV'sinde hiç görünmediği bulundu.*

**REQ-1.9** Kullanıcı hikâyesi, görev ve hata kayıtlarına yazılan yorumlar, yorumu
yazan kullanıcı için sayılır. Boş ve silinmiş yorumlar sayılmaz.

## 2. Öğrenci eşleme

**REQ-2.1** Öğrenci listesinde her öğrenci için ad soyad zorunludur. Diğer sütunlar
e-posta veya kullanıcı adı içerebilir; araç hangisi olduğunu kendisi ayırt eder.

**REQ-2.2** E-posta adresi, depodaki commit'lerde o adresi kullanan GitHub hesabıyla
eşleştirilir.

**REQ-2.3** Taiga hesabı şu sırayla aranır: kullanıcı adı, ad soyad (Türkçe karakter
ve büyük-küçük harf farkı gözetilmeden), e-postanın @ öncesi kısmı.

**REQ-2.4** Hiçbir hesapla eşleşmeyen öğrenci, raporda açıkça "eşleşmedi" olarak
işaretlenir. Eşleşmeyen bir öğrenci sessizce 0 puan almaz. Yalnızca GitHub'la veya
yalnızca Taiga'yla eşleşen öğrenci için, eksik kaynağı belirten bir uyarı verilir.
Taiga verisi verilmediyse Taiga için uyarı verilmez.
*Kaynak: 1. rol dönemi değerlendirmesinde bir öğrencinin bildirdiği hata; kısmi
eşleşme, uçtan uca kabul testinde bulundu.*

**REQ-2.5** Etkinliği olup hiçbir öğrenciye bağlanamayan hesaplar raporda ayrıca
listelenir.

**REQ-2.7** Öğrenci listesindeki bir kullanıcı adı veya e-posta hiçbir etkin GitHub ya
da Taiga hesabıyla eşleşmezse, öğrenci ve değerle birlikte uyarı verilir. Hiçbir hesapla
eşleşmeyen öğrenci için yalnızca REQ-2.4'teki uyarı verilir.
*Kaynak: kabul testinde, Taiga kullanıcı adı yerine görünen adın yazıldığı bulundu.*

## 3. Puanlama

**REQ-3.1** Her ölçütün her rol için ayrı bir ağırlığı vardır. Ağırlıklar çıktı
dosyasında değiştirilebilir ve puanlar yeniden hesaplanır.

**REQ-3.2** Bir öğrencinin puanı, ölçüt sayılarının kendi rolünün ağırlıklarıyla
çarpılıp toplanmasıdır.

**REQ-3.3** Bir rolün hedef puanı, o roldeki öğrencilerin puan medyanının hedef
katsayısıyla çarpımıdır. Varsayılan katsayı 1,0'dır; yani medyandaki öğrenci 100 alır.
Katsayı değiştirilebilir ve sıfırdan büyük olmalıdır. Hiçbir hesapla eşleşmeyen
öğrenciler (REQ-2.4) medyan hesabına katılmaz.

**REQ-3.4** Not, puanın hedef puana oranının 100 ile çarpımıdır, en yakın tam sayıya
yuvarlanır ve 100'ü geçmez.

**REQ-3.5** Hiç katkısı olmayan öğrencinin notu 0'dır. Roldeki herkesin puanı 0 ise,
o roldeki herkesin notu 0'dır.

**REQ-3.6** Rolü boş veya tanınmayan öğrenci "Diğer" rolüyle puanlanır ve araç bunun
için uyarı verir.

**REQ-3.7** Bir rolde tek öğrenci varsa araç uyarı verir, çünkü o öğrenci yalnızca
kendisiyle karşılaştırılır.

**REQ-3.11** Öğretim üyesi, ayrı bir düzeltme dosyasıyla bir öğrencinin nihai notuna
gerekçe yazarak puan ekleyebilir veya çıkarabilir. Gerekçesiz düzeltme ve listede
olmayan bir öğrenci için düzeltme kabul edilmez. Nihai not 0 ile 100 arasında kalır.
Raporda düzeltme ve gerekçesi notun yanında gösterilir. Eşleşmeyen öğrenciye düzeltme
uygulanmaz ve uyarı verilir.

## 4. Rehberlik

**REQ-4.1** Araç, her öğrenci için her ölçütte rol medyanına oranını gösterir.

**REQ-4.2** Ağırlığı belirlenen eşiğin altında olan ölçütler, o rol için oran
gösterilmeden boş bırakılır.

**REQ-4.3** Araç, her öğrenci için en zayıf önemli ölçütü, öğrencinin sayısı ve rol
medyanıyla birlikte tek cümle olarak yazar.

## 5. Çıktı

**REQ-5.1** Araç, sonuçları tek bir Excel dosyasına yazar.

**REQ-5.2** Her sayı, dayandığı kayda (PR veya Taiga kaydı) çıktıdan bağlantısıyla
izlenebilir.

**REQ-5.3** Araç tek bir komutla çalıştırılır. Öğrenci listesi, Taiga CSV klasörü
(isteğe bağlı), depo, tarih aralığı, rol sütunu ve hedef katsayısı komutta verilir.
Her öğrencinin rolü, notu, puanı ve hesapları, uyarılar ve hiçbir öğrenciye bağlanamayan
hesaplar ekrana yazılır. Taiga klasörü verildiğinde değişiklik geçmişi de indirilir ve
CSV verisiyle birleştirilir; bu adım bir seçenekle atlanabilir.

## 6. Gizlilik ve güvenlik

**REQ-6.1** Öğrenci listesi, çıktı dosyaları ve token depoya commit'lenemez.

**REQ-6.2** GitHub token'ı koddan değil,`CONTRIBUTION_TOOL_TOKEN` ortam değişkeninden okunur. Araç `GITHUB_TOKEN` değişkenini kullanmaz, çünkü bu değişken git ve gh tarafından da kullanılır.

**REQ-6.3** Depodaki test verisi tamamen uydurmadır; gerçek öğrenci adı veya e-postası içermez.

**REQ-6.4** Araç, Taiga'ya öğretim üyesinin hesabıyla her çalıştırmada yeniden giriş
yapar. Kullanıcı adı `CONTRIBUTION_TOOL_TAIGA_USERNAME` ortam değişkeninden okunur.
Şifre `CONTRIBUTION_TOOL_TAIGA_PASSWORD` değişkeninden okunur; yoksa ekranda gösterilmeden
sorulur. Şifre ve erişim anahtarı hiçbir dosyaya yazılmaz.

## Kapsam dışı (v1)

- Yerel dil modeliyle nitel değerlendirme (v2'de ele alınacak)
- Web arayüzü
- Taiga API'sine doğrudan bağlanma (CSV dışa aktarımı kullanılır)

## Değişiklik geçmişi

| Sürüm | Değişiklik | Neden |
|---|---|---|
| 1.0 | İlk sürüm | — |
| 1.1 | REQ-3.3: hedef katsayısı 1,2'den 1,0'a indirildi ve ayarlanabilir yapıldı | Öğretim üyesi kararı: daha cömert puanlama |
| 1.2 | REQ-1.3: tarihlerin Türkiye saatine göre değerlendirileceği netleştirildi | GitHub ve Taiga saatleri UTC olarak kaydediyor; gece yarısından sonraki iş bir önceki güne sayılıyordu |
| 1.3 | REQ-3.3: eşleşmeyen öğrencilerin medyana katılmayacağı netleştirildi | Eşleşmeyen öğrenci 0 puanla medyanı düşürüp diğerlerinin notunu haksız şekilde yükseltiyordu |
| 1.4 | REQ-5.3 eklendi (tek komutla çalıştırma); REQ-6.2: token değişkeninin adı belirlendi | Kabul testinde GITHUB_TOKEN değişkeninin git push'u bozduğu görüldü |
| 1.5 | REQ-3.11 eklendi: gerekçeli not düzeltmesi (kanaat notu) | Kabul testinde, işini yapan bir PO'nun hikâyeleri SM tarafından açıldığı için en düşük puanı aldığı görüldü |
| 1.6 | REQ-2.4: kısmi eşleşmede uyarı | Kabul testinde, Taiga kullanıcı adı listedekinden farklı olan bir öğrencinin Taiga katkıları sayılmadı ve uyarı verilmedi |
| 1.7 | REQ-1.8 ve REQ-1.9 eklendi: Taiga değişiklik geçmişinden hikâye kabulü ve yorum sayımı | Taiga CSV'si durumu kimin değiştirdiğini içermiyor; testçi ve PO işleri görünmüyordu |
| 1.8 | REQ-1.7 ve REQ-6.4 eklendi: Taiga geçmişinin indirilmesi ve Taiga girişi | Taiga projesi özel; geçmişi okumak için öğretim üyesinin hesabıyla giriş gerekiyor |
| 1.9 | REQ-5.3: Taiga değişiklik geçmişi komuta bağlandı | Testçi ve PO işlerinin nota yansıması |
| 1.10 | REQ-2.7 eklendi: listede hiçbir hesapla eşleşmeyen değer için uyarı | Kabul testinde listeye Taiga görünen adı yazılmıştı; araç bunu sessizce yok saydı |

