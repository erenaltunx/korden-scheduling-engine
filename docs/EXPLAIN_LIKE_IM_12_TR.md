# OPTERA'u 12 yaşındaki birine nasıl anlatırsın?

Bir oyuncak araba fabrikasında beş sipariş var. Her arabanın önce kesilmesi, sonra boyanması, en son paketlenmesi gerekiyor. Ama sadece iki kesme makinesi, bir boyama makinesi var. Bazı makineler öğlen bakım için duruyor. Müşteriler de arabalarını farklı günlerde istiyor.

**Sorun:** Herkes kendi siparişini öne almak isterse makineler çakışabilir ve bazı müşterilere geç teslim edilir.

**OPTERA ne yapıyor?** Önce normal bir fabrika çalışanı gibi en yakın teslim tarihine göre bir sıra kuruyor (EDD). Sonra bir matematik bulmacası çözer gibi bütün kuralları dikkate alıp daha iyi bir sıra arıyor. Aynı makineyi iki iş için aynı anda kullanamaz, boyama kesmeden önce başlayamaz, bakımda makine çalışmaz.

Bunu okul örneğiyle düşün: 5 öğrencinin 3 ödevi var; hepsinin kullanması gereken tek bilgisayar mevcut. OPTERA herkesin ödevini sıralıyor, teslim tarihlerini ve bilgisayarın boş olduğu saatleri düşünüyor.

**Kazancı nasıl anlarız?** İki plan için geç teslim edilen işlerin toplam gecikmesini ölçeriz. Örneğin, küçük deneme fabrikamızda önceliklerle çarpılmış toplam gecikme puanı 39'dan 15'e indi. Bu **%61,54** daha az ağırlıklı gecikme demektir, para kazanıldığı veya gerçek fabrikada bu sonuç alınacağı demek değildir.

**En önemli fark:** Bir tablo çizmekle yetinmiyor; hangi işin hangi makinede saat kaçta başlayacağını hesaplıyor ve sonra tüm kurallara gerçekten uyulduğunu tekrar kontrol ediyor.

**Bilgilerin kaybolmasın diye:** Deneyleri özel bir deftere (SQLite veri tabanı) yazıyor, her kayda bütünlük damgası vuruyor, yedek oluşturabiliyor. Kodun defteri ise GitHub'da saklanacak; bu iki ayrı şey.
