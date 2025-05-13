# Spotify Web Downloader

Spotify hesabınızdaki beğendiğiniz şarkıları ve çalma listelerini kolayca indirmenizi sağlayan bir web uygulaması.

## Özellikler

- Spotify hesabıyla kimlik doğrulama
- Beğenilen şarkıları listeleme ve indirme
- Kişisel çalma listelerini görüntüleme
- Herhangi bir çalma listesini URL ile indirme
- YouTube'dan otomatik MP3 indirme (yt-dlp ile)
- 4-16 arası ayarlanabilir eş zamanlı indirme
- ZIP formatında toplu indirme
- FFmpeg ile MP3 dönüştürme
- Kullanıcı dostu arayüz

## Kurulum

### Gereksinimler

- Python 3.6+
- FFmpeg (MP3 dönüştürme için)
- Spotify Geliştirici Hesabı

### Adımlar

1. Bu repository'yi klonlayın:
```bash
git clone https://github.com/KullaniciAdiniz/spotify-web-downloader.git
cd spotify-web-downloader
```

2. Gerekli Python paketlerini yükleyin:
```bash
pip install -r requirements.txt
```

3. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) üzerinden yeni bir uygulama oluşturun:
   - Uygulamanıza bir isim verin
   - Redirect URI olarak `http://127.0.0.1:5000/callback` ekleyin
   - Client ID ve Client Secret bilgilerinizi kaydedin

4. Uygulamayı başlatın:
```bash
python app.py
```

5. Tarayıcınızda `http://127.0.0.1:5000` adresine gidin ve Spotify kimlik bilgilerinizle giriş yapın

## Kullanım

1. Giriş yaptıktan sonra, beğenilen şarkılarınızı görüntülemek için "Beğenilen Şarkıları Getir" butonuna tıklayın.
2. Çalma listelerinize erişmek için "Çalma Listeleri" sekmesine geçin.
3. Bir Spotify çalma listesi URL'si ile şarkıları indirmek için "Çalma Listesi URL" sekmesini kullanın.
4. İndirmek istediğiniz şarkıları seçin ve eş zamanlı indirme sayısını ayarlayın.
5. "İndirmeyi Başlat" butonuna tıklayın ve bittiğinde ZIP dosyasını indirin.

## Güvenlik Uyarısı

- Bu uygulama, kişisel kullanım için tasarlanmıştır.
- Spotify ve YouTube hizmet şartlarını ihlal etmemeye özen gösterin.
- Telif hakkı sahibi olmadığınız içeriği indirmek yerel yasalara aykırı olabilir.

## Sorun Giderme

- **Yetkilendirme Hatası**: Spotify API kimlik bilgilerinizin doğru olduğundan ve redirect URI'nin uygulamanızdakiyle eşleştiğinden emin olun.
- **İndirme Sorunları**: FFmpeg'in doğru şekilde kurulduğundan emin olun.
- **Şarkı Bulunamadı**: Bazı şarkılar telif hakkı veya bölge kısıtlamaları nedeniyle YouTube'da bulunmayabilir.

## Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.

## İletişim

Sorularınız veya önerileriniz için GitHub'da issue açabilirsiniz 