# Gereksinimler — EventHub Katkı Aracı

Sürüm: 1.1 · Kapsam: v1 (nicel değerlendirme)

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
Başlangıç ve bitiş günleri aralığa dahildir.

**REQ-1.4** Bot hesaplarının (`[bot]` ile biten adlar) etkinlikleri sayılmaz.

**REQ-1.5** Durumu "Reddedildi" olan hata kayıtları sayılmaz.

**REQ-1.6** Bir öğrencinin kendi PR'ına yaptığı inceleme, kod incelemesi olarak sayılmaz.

## 2. Öğrenci eşleme

**REQ-2.1** Öğrenci listesinde her öğrenci için ad soyad zorunludur. Diğer sütunlar
e-posta veya kullanıcı adı içerebilir; araç hangisi olduğunu kendisi ayırt eder.

**REQ-2.2** E-posta adresi, depodaki commit'lerde o adresi kullanan GitHub hesabıyla
eşleştirilir.

**REQ-2.3** Taiga hesabı şu sırayla aranır: kullanıcı adı, ad soyad (Türkçe karakter
ve büyük-küçük harf farkı gözetilmeden), e-postanın @ öncesi kısmı.

**REQ-2.4** Hiçbir hesapla eşleşmeyen öğrenci, raporda açıkça "eşleşmedi" olarak
işaretlenir. Eşleşmeyen bir öğrenci sessizce 0 puan almaz.
*Kaynak: 1. rol dönemi değerlendirmesinde bir öğrencinin bildirdiği hata.*

**REQ-2.5** Etkinliği olup hiçbir öğrenciye bağlanamayan hesaplar raporda ayrıca
listelenir.

## 3. Puanlama

**REQ-3.1** Her ölçütün her rol için ayrı bir ağırlığı vardır. Ağırlıklar çıktı
dosyasında değiştirilebilir ve puanlar yeniden hesaplanır.

**REQ-3.2** Bir öğrencinin puanı, ölçüt sayılarının kendi rolünün ağırlıklarıyla
çarpılıp toplanmasıdır.

**REQ-3.3** Bir rolün hedef puanı, o roldeki öğrencilerin puan medyanının hedef
katsayısıyla çarpımıdır. Varsayılan katsayı 1,0'dır; yani medyandaki öğrenci 100 alır.
Katsayı değiştirilebilir ve sıfırdan büyük olmalıdır.

**REQ-3.4** Not, puanın hedef puana oranının 100 ile çarpımıdır, en yakın tam sayıya
yuvarlanır ve 100'ü geçmez.

**REQ-3.5** Hiç katkısı olmayan öğrencinin notu 0'dır. Roldeki herkesin puanı 0 ise,
o roldeki herkesin notu 0'dır.

**REQ-3.6** Rolü boş veya tanınmayan öğrenci "Diğer" rolüyle puanlanır ve araç bunun
için uyarı verir.

**REQ-3.7** Bir rolde tek öğrenci varsa araç uyarı verir, çünkü o öğrenci yalnızca
kendisiyle karşılaştırılır.

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

## 6. Gizlilik ve güvenlik

**REQ-6.1** Öğrenci listesi, çıktı dosyaları ve token depoya commit'lenemez.

**REQ-6.2** GitHub token'ı koddan değil, ortam değişkeninden okunur.

**REQ-6.3** Depodaki test verisi tamamen uydurmadır; gerçek öğrenci adı veya
e-postası içermez.

## Kapsam dışı (v1)

- Yerel dil modeliyle nitel değerlendirme (v2'de ele alınacak)
- Web arayüzü
- Taiga API'sine doğrudan bağlanma (CSV dışa aktarımı kullanılır)

## Değişiklik geçmişi

| Sürüm | Değişiklik | Neden |
|---|---|---|
| 1.0 | İlk sürüm | — |
| 1.1 | REQ-3.3: hedef katsayısı 1,2'den 1,0'a indirildi ve ayarlanabilir yapıldı | Öğretim üyesi kararı: daha cömert puanlama |
