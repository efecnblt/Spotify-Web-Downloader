import os
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect, render_template, jsonify, send_from_directory
import yt_dlp
import threading
import json
from urllib.parse import urlparse, parse_qs
import uuid
import zipfile
import io
import re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = "spotifydownloaderwebapp"
app.config['SESSION_COOKIE_NAME'] = 'spotify-downloader-session'
app.config['DOWNLOAD_FOLDER'] = 'downloads'

# İndirme klasörünü oluştur
os.makedirs(os.path.join(os.path.dirname(__file__), app.config['DOWNLOAD_FOLDER']), exist_ok=True)

# Session anahtarları
TOKEN_INFO = "token_info"
CLIENT_INFO = "client_info"
USER_ID = "user_id"

# Varsayılan (demo) kimlik bilgileri
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""

# Sabit redirect URI
REDIRECT_URI = "http://127.0.0.1:5000/callback"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set-credentials', methods=['POST'])
def set_credentials():
    client_id = request.form.get('client_id')
    client_secret = request.form.get('client_secret')
    
    # Session'da kimlik bilgilerini sakla - sabit redirect URI kullan
    session[CLIENT_INFO] = {
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    # Spotify login sayfasına yönlendir
    return redirect(url_for('login'))

@app.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    sp_oauth = create_spotify_oauth()
    session.pop(TOKEN_INFO, None)  # Önceki token'ı temizle
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('download_options'))

@app.route('/callback')
def callback():
    sp_oauth = create_spotify_oauth()
    session.pop(TOKEN_INFO, None)  # Önceki token'ı temizle
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('download_options'))

@app.route('/download-options')
def download_options():
    if not is_authenticated():
        return redirect(url_for('login'))
    return render_template('download_options.html')

@app.route('/get-liked-songs')
def get_liked_songs():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    try:
        sp = get_spotify_client()
        
        results = []
        offset = 0
        limit = 50
        
        # Beğenilen şarkıları al
        while True:
            items = sp.current_user_saved_tracks(limit=limit, offset=offset)['items']
            if not items:
                break
                
            for item in items:
                track = item['track']
                results.append({
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'id': track['id']
                })
                
            offset += limit
            if len(items) < limit:
                break
        
        # Kullanıcı bilgilerini al
        user_info = sp.me()
        user_id = user_info['id']
        session[USER_ID] = user_id
        
        # Şarkı listesini dosyada sakla
        songs_dir = os.path.join(os.path.dirname(__file__), 'song_data')
        os.makedirs(songs_dir, exist_ok=True)
        
        # Kullanıcı için benzersiz bir dosya adı oluştur
        songs_file = os.path.join(songs_dir, f"{user_id}_liked_{int(time.time())}.json")
        
        # Şarkı listesini dosyaya kaydet
        with open(songs_file, 'w', encoding='utf-8') as f:
            json.dump(results, f)
        
        # Dosya yolunu session'da sakla
        session['songs_file'] = songs_file
        
        return jsonify({
            'status': 'success', 
            'count': len(results),
            'songs': results
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Hata detayları: {error_details}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-playlists')
def get_playlists():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    try:
        sp = get_spotify_client()
        
        # Kullanıcının çalma listelerini al
        offset = 0
        limit = 50
        playlists = []
        
        while True:
            results = sp.current_user_playlists(limit=limit, offset=offset)
            
            if not results['items']:
                break
                
            for playlist in results['items']:
                # Sadece kullanıcının kendi çalma listelerini al
                playlist_info = {
                    'id': playlist['id'],
                    'name': playlist['name'],
                    'tracks_count': playlist['tracks']['total'],
                    'image_url': playlist['images'][0]['url'] if playlist['images'] else None
                }
                playlists.append(playlist_info)
            
            offset += limit
            if len(results['items']) < limit:
                break
        
        return jsonify({
            'status': 'success',
            'count': len(playlists),
            'playlists': playlists
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Çalma listeleri hata detayları: {error_details}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-playlist-tracks/<playlist_id>')
def get_playlist_tracks(playlist_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    
    try:
        sp = get_spotify_client()
        
        results = []
        offset = 0
        limit = 100
        
        # Çalma listesi şarkılarını al
        while True:
            items = sp.playlist_items(playlist_id, offset=offset, limit=limit, 
                                     fields='items(track(id,name,artists))')['items']
            if not items:
                break
                
            for item in items:
                if item['track']:  # Bazen track null olabilir
                    track = item['track']
                    results.append({
                        'name': track['name'],
                        'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown Artist',
                        'id': track['id']
                    })
                
            offset += limit
            if len(items) < limit:
                break
        
        # Kullanıcı ID'si
        user_id = session.get(USER_ID, str(uuid.uuid4())[:8])
        
        # Şarkı listesini dosyada sakla
        songs_dir = os.path.join(os.path.dirname(__file__), 'song_data')
        os.makedirs(songs_dir, exist_ok=True)
        
        # Playlist şarkıları için benzersiz bir dosya adı oluştur
        songs_file = os.path.join(songs_dir, f"{user_id}_playlist_{playlist_id}_{int(time.time())}.json")
        
        # Şarkı listesini dosyaya kaydet
        with open(songs_file, 'w', encoding='utf-8') as f:
            json.dump(results, f)
        
        # Dosya yolunu session'da sakla
        session['playlist_songs_file'] = songs_file
        
        return jsonify({
            'status': 'success', 
            'count': len(results),
            'songs': results
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Çalma listesi şarkıları hata detayları: {error_details}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get-playlist-by-url', methods=['POST'])
def get_playlist_by_url():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    try:
        # URL'den playlist ID'sini çıkar
        data = request.json
        playlist_url = data.get('playlist_url', '')
        
        # URL'den playlist ID'sini çıkarmak için regex kullan
        import re
        playlist_id_match = re.search(r'playlist/([a-zA-Z0-9]+)', playlist_url)
        
        if not playlist_id_match:
            return jsonify({'status': 'error', 'message': 'Geçersiz çalma listesi URL\'si'})
        
        playlist_id = playlist_id_match.group(1)
        
        # Çalma listesi şarkılarını getir
        return get_playlist_tracks(playlist_id)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"URL ile çalma listesi hata detayları: {error_details}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/download-playlist-songs')
def download_playlist_songs():
    if not is_authenticated():
        return redirect(url_for('login'))
        
    # Şarkı listesini dosyadan al
    songs_file = session.get('playlist_songs_file')
    
    if not songs_file or not os.path.exists(songs_file):
        return jsonify({'status': 'error', 'message': 'Çalma listesi şarkıları bulunamadı'})
    
    try:
        # Şarkı listesini dosyadan oku
        with open(songs_file, 'r', encoding='utf-8') as f:
            songs = json.load(f)
        
        # Kullanıcı ID'sini al veya oluştur
        user_id = session.get(USER_ID, str(uuid.uuid4())[:8])
        
        # Eş zamanlı indirme sayısını al
        max_workers = request.args.get('max_workers', '8')
        try:
            max_workers = int(max_workers)
            # Makul sınırlar içinde tut
            max_workers = min(max(4, max_workers), 16)
        except ValueError:
            max_workers = 8
        
        # İndirme klasörünü oluştur
        download_dir = os.path.join(app.config['DOWNLOAD_FOLDER'], f"user_{user_id}_playlist_{int(time.time())}")
        os.makedirs(os.path.join(os.path.dirname(__file__), download_dir), exist_ok=True)
        
        # İndirme işlemi için arka plan işi başlat
        thread = threading.Thread(target=download_songs_task, args=(songs, download_dir, max_workers))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success', 
            'message': 'İndirme işlemi başlatıldı',
            'download_id': os.path.basename(download_dir)
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Çalma listesi indirme hatası: {error_details}")
        return jsonify({'status': 'error', 'message': f'Hata: {str(e)}'})

@app.route('/download-songs')
def download_songs():
    if not is_authenticated():
        return redirect(url_for('login'))
        
    # Şarkı listesini dosyadan al
    songs_file = session.get('songs_file')
    
    if not songs_file or not os.path.exists(songs_file):
        return jsonify({'status': 'error', 'message': 'Şarkı listesi bulunamadı'})
    
    try:
        # Şarkı listesini dosyadan oku
        with open(songs_file, 'r', encoding='utf-8') as f:
            songs = json.load(f)
        
        # Kullanıcı ID'sini al veya oluştur
        user_id = session.get(USER_ID, str(uuid.uuid4())[:8])
        
        # Eş zamanlı indirme sayısını al
        max_workers = request.args.get('max_workers', '8')
        try:
            max_workers = int(max_workers)
            # Makul sınırlar içinde tut
            max_workers = min(max(4, max_workers), 16)
        except ValueError:
            max_workers = 8
        
        # İndirme klasörünü oluştur
        download_dir = os.path.join(app.config['DOWNLOAD_FOLDER'], f"user_{user_id}_{int(time.time())}")
        os.makedirs(os.path.join(os.path.dirname(__file__), download_dir), exist_ok=True)
        
        # İndirme işlemi için arka plan işi başlat
        thread = threading.Thread(target=download_songs_task, args=(songs, download_dir, max_workers))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success', 
            'message': 'İndirme işlemi başlatıldı',
            'download_id': os.path.basename(download_dir)
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"İndirme hatası detayları: {error_details}")
        return jsonify({'status': 'error', 'message': f'Hata: {str(e)}'})

@app.route('/download-status/<download_id>')
def download_status(download_id):
    download_dir = os.path.join(app.config['DOWNLOAD_FOLDER'], download_id)
    status_file = os.path.join(os.path.dirname(__file__), download_dir, 'status.json')
    
    if not os.path.exists(status_file):
        return jsonify({'status': 'pending', 'progress': 0, 'total': 0})
    
    with open(status_file, 'r') as f:
        status = json.load(f)
    
    return jsonify(status)

@app.route('/get-download/<download_id>')
def get_download(download_id):
    download_dir = os.path.join(app.config['DOWNLOAD_FOLDER'], download_id)
    full_download_path = os.path.join(os.path.dirname(__file__), download_dir)
    
    if not os.path.exists(full_download_path):
        return "İndirme bulunamadı", 404
    
    # ZIP dosyası için benzersiz bir isim oluştur
    zip_filename = f"spotify_songs_{download_id}.zip"
    zip_full_path = os.path.join(os.path.dirname(full_download_path), zip_filename)
    
    try:
        # MP3 dosyalarını kontrol et
        mp3_files = [f for f in os.listdir(full_download_path) if f.endswith('.mp3')]
        if not mp3_files:
            return "İndirilebilecek şarkı bulunamadı", 404
        
        # ZIP dosyası oluştur
        with zipfile.ZipFile(zip_full_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in mp3_files:
                file_path = os.path.join(full_download_path, file)
                zipf.write(file_path, file)  # ZIP içinde dosya adını koru
        
        # ZIP dosyasını indir
        response = send_from_directory(
            os.path.dirname(zip_full_path),
            zip_filename,
            as_attachment=True
        )
        
        # İndirildikten sonra dosyaları temizle
        def cleanup_files():
            try:
                time.sleep(60)  # 1 dakika bekle
                if os.path.exists(zip_full_path):
                    os.remove(zip_full_path)
            except Exception as e:
                print(f"Dosya temizleme hatası: {str(e)}")
        
        # Arka planda temizlik işlemini başlat
        cleanup_thread = threading.Thread(target=cleanup_files)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        return response
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ZIP oluşturma hatası: {error_details}")
        
        # Hata durumunda klasörü direkt döndür
        return send_from_directory(
            os.path.dirname(full_download_path),
            os.path.basename(download_dir),
            as_attachment=True
        )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# FFmpeg kontrolü için fonksiyon
def check_ffmpeg():
    try:
        import subprocess
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False

def download_songs_task(songs, download_dir, max_workers):
    total = len(songs)
    completed = 0
    failed = []
    
    status_path = os.path.join(os.path.dirname(__file__), download_dir, 'status.json')
    full_download_path = os.path.join(os.path.dirname(__file__), download_dir)
    
    # FFmpeg kontrolü
    has_ffmpeg = check_ffmpeg()
    if not has_ffmpeg:
        print("UYARI: FFmpeg bulunamadı. MP3 dönüştürme işlemi çalışmayabilir.")
    
    # İlk durumu kaydet
    with open(status_path, 'w') as f:
        json.dump({
            'status': 'in_progress',
            'progress': completed,
            'total': total,
            'failed': failed
        }, f)
    
    # İndirme mutex'i (thread-safe durum güncellemesi için)
    progress_lock = threading.Lock()
    
    # Bir şarkıyı indirme fonksiyonu
    def download_song(song):
        nonlocal completed, failed
        
        try:
            artist = song.get('artist', 'Unknown Artist')
            name = song.get('name', 'Unknown Song')
            query = f"{name} {artist} official audio"
            filename = f"{artist} - {name}.mp3"
            safe_filename = re.sub(r'[\\/*?:"<>|]', '', filename).strip()
            
            print(f"İndiriliyor: {safe_filename}")
            
            # yt-dlp ile indir
            output_template = os.path.join(full_download_path, safe_filename)
            
            # yt-dlp ayarları
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True
            }
            
            # FFmpeg varsa post-processing ekle
            if has_ffmpeg:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            # yt-dlp ile YouTube araması yap ve indir
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Video ara
                search_results = ydl.extract_info(f"ytsearch1:{query}", download=False)
                
                if 'entries' in search_results and len(search_results['entries']) > 0:
                    # İlk sonucu seç ve indir
                    info = search_results['entries'][0]
                    video_url = info['webpage_url']
                    ydl.extract_info(video_url, download=True)
                    
                    with progress_lock:
                        nonlocal completed
                        completed += 1
                        print(f"Tamamlandı: {safe_filename} [{completed}/{total}]")
                        
                        # Durumu güncelle
                        with open(status_path, 'w') as f:
                            json.dump({
                                'status': 'in_progress',
                                'progress': completed,
                                'total': total,
                                'failed': [f"{s['artist']} - {s['name']}" for s in failed]
                            }, f)
                else:
                    print(f"{safe_filename} için sonuç bulunamadı")
                    with progress_lock:
                        failed.append(song)
            
            return True
            
        except Exception as e:
            print(f"Video indirme hatası - {safe_filename if 'safe_filename' in locals() else song.get('name', 'unknown')}: {str(e)}")
            with progress_lock:
                failed.append(song)
            return False
    
    # Eş zamanlı indirme için ThreadPoolExecutor kullan
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Tüm şarkılar için indirme işini başlat
        futures = [executor.submit(download_song, song) for song in songs]
        
        # Tüm indirmeler tamamlanana kadar bekle
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Beklenmeyen indirme hatası: {str(e)}")
    
    # Final durumunu kaydet
    with open(status_path, 'w') as f:
        json.dump({
            'status': 'completed',
            'progress': completed,
            'total': total,
            'failed': [f"{s['artist']} - {s['name']}" for s in failed]
        }, f)
    
    print(f"İndirme tamamlandı: {completed}/{total} başarılı, {len(failed)}/{total} başarısız")

def is_authenticated():
    return TOKEN_INFO in session

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        return None
        
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    
    if is_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session[TOKEN_INFO] = token_info
    
    return token_info

def get_spotify_client():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))
    
    return spotipy.Spotify(auth=token_info['access_token'])

def create_spotify_oauth():
    # Session'dan kimlik bilgilerini al veya varsayılan değerleri kullan
    client_info = session.get(CLIENT_INFO, None)
    
    if client_info:
        client_id = client_info.get('client_id')
        client_secret = client_info.get('client_secret')
    else:
        # Varsayılan (demo) değerleri kullan
        client_id = DEFAULT_CLIENT_ID
        client_secret = DEFAULT_CLIENT_SECRET
    
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,  # Her zaman sabit redirect URI kullan
        scope="user-library-read"
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000) 